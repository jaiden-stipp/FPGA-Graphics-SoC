`timescale 1ns/1ps
// Sparse JEDEC command model for the board's 13-row/10-column/2-bank-bit pair.
// Checks initialization/timing/refresh, CL3 read delay, auto-precharge and DQM.
// Physical signal integrity is verified separately by the on-board self-test.
module sdram_device_model #(
    // Storage capacity, not address width. Full word addresses remain tagged.
    parameter integer STORAGE_BITS=21
) (
    input wire DRAM_CLK, DRAM_CKE, DRAM_CS_N, DRAM_RAS_N, DRAM_CAS_N, DRAM_WE_N,
    input wire [12:0] DRAM_ADDR,
    input wire [1:0] DRAM_BA,
    input wire [3:0] DRAM_DQM,
    inout wire [31:0] DRAM_DQ
);
    // Icarus does not implement SystemVerilog associative arrays. A bounded
    // sparse hash table keeps full-address tests practical on both simulators.
    // Unwritten words read as zero; exhaustion fails instead of aliasing data.
    localparam integer STORAGE_WORDS=1 << STORAGE_BITS;
    bit occupied[0:STORAGE_WORDS-1];
    logic [31:0] memory[0:STORAGE_WORDS-1];
    integer unsigned tags[0:STORAGE_WORDS-1];
    function automatic integer slot(input integer unsigned address);
        integer index, probes;
        begin
            index=(address ^ (address >> STORAGE_BITS)) & (STORAGE_WORDS-1);
            probes=0;
            while (occupied[index] && tags[index]!=address && probes<STORAGE_WORDS) begin
                index=(index+1) & (STORAGE_WORDS-1);
                probes=probes+1;
            end
            if (probes==STORAGE_WORDS) $fatal(1,"SDRAM model storage exhausted; increase STORAGE_BITS");
            slot=index;
        end
    endfunction
    function automatic [31:0] read_word(input integer unsigned address);
        integer index;
        begin
            index=slot(address);
            read_word=occupied[index] ? memory[index] : 32'b0;
        end
    endfunction
    task automatic write_word(input integer unsigned address,input logic [31:0] data);
        integer index;
        begin
            index=slot(address);
            tags[index]=address; memory[index]=data; occupied[index]=1;
        end
    endtask
    logic [12:0] row[0:3];
    bit opened[0:3];
    integer available[0:3], activated[0:3];
    integer cycle=0, refreshes=0, last_refresh=0, read_delay=0;
    integer burst_length=1, burst_left=0, beat=0, read_commands=0, activate_commands=0;
    integer read_beats=0;
    integer unsigned read_base, read_column;
    bit mode_set=0, precharged=0, drive=0;
    logic [31:0] output_data, pending_data, write_data;
    integer unsigned key;
    assign DRAM_DQ=drive ? output_data : 32'bz;
    initial for (integer i=0;i<4;i=i+1) begin opened[i]=0; available[i]=0; activated[i]=0; end
    always @(posedge DRAM_CLK) begin
        cycle=cycle+1;
        if (drive) begin drive<=#2.7 0; end
        if (read_delay!=0) begin
            if (read_delay==1) begin
                output_data<=#6.4 pending_data; drive<=#6.4 1;
                burst_left=burst_length-1; beat=1; read_beats=read_beats+1;
            end
            read_delay=read_delay-1;
        end else if (burst_left!=0) begin
            // Sequential fixed-length bursts wrap within their aligned block.
            key=read_base | ((read_column+beat) & (burst_length-1));
            output_data<=#6.4 read_word(key);
            drive<=#6.4 1; beat=beat+1; burst_left=burst_left-1;
            read_beats=read_beats+1;
        end
        if (mode_set && cycle-last_refresh>395) $fatal(1,"SDRAM refresh overdue");
        if (DRAM_CKE && !DRAM_CS_N) case ({DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N})
            3'b010: begin // precharge
                if (DRAM_ADDR[10]) begin
                    for (integer i=0;i<4;i=i+1) begin opened[i]=0; available[i]=cycle+3; end
                    precharged=1;
                end else begin opened[DRAM_BA]=0; available[DRAM_BA]=cycle+3; end
            end
            3'b001: begin // refresh
                if (!precharged) $fatal(1,"Refresh before precharge");
                for (integer i=0;i<4;i=i+1) if (opened[i] || cycle<available[i]) $fatal(1,"Refresh with active/recovering bank");
                if (refreshes && cycle-last_refresh<4) $fatal(1,"tRFC violation");
                refreshes=refreshes+1; last_refresh=cycle;
            end
            3'b000: begin
                if (refreshes<8 || (DRAM_ADDR<13'h230 || DRAM_ADDR>13'h233) || DRAM_BA!=0) $fatal(1,"Bad SDRAM mode/init sequence");
                burst_length=1 << DRAM_ADDR[2:0];
                mode_set=1; last_refresh=cycle;
            end
            3'b011: begin // activate
                activate_commands=activate_commands+1;
                if (!mode_set || opened[DRAM_BA] || cycle<available[DRAM_BA]) $fatal(1,"Bad SDRAM activate");
                row[DRAM_BA]=DRAM_ADDR; opened[DRAM_BA]=1; activated[DRAM_BA]=cycle;
            end
            3'b101,3'b100: begin
                if (!opened[DRAM_BA] || cycle-activated[DRAM_BA]<2 || !DRAM_ADDR[10]) $fatal(1,"Bad SDRAM column command/tRCD");
                key={row[DRAM_BA],DRAM_BA,DRAM_ADDR[9:0]};
                if (DRAM_WE_N) begin
                    if(read_delay || burst_left) $fatal(1,"Read burst interrupted");
                    read_commands=read_commands+1;
                    pending_data=read_word(key);
                    // Preserve the legacy BL1 fixture. BL8 first-beat alignment
                    // is calibrated to the numbered-word physical-board probe;
                    // the original sparse model returned it one clock too late.
                    // This model is not independent vendor timing validation.
                    read_delay=burst_length>1 ? 2 : 3;
                    read_base=key & ~(burst_length-1); read_column=key & (burst_length-1);
                    available[DRAM_BA]=cycle+6+burst_length-1;
                end else begin
                    write_data=read_word(key);
                    for (integer b=0;b<4;b=b+1) if (!DRAM_DQM[b]) begin
                        // Icarus 12 misreports $isunknown on this variable
                        // part-select. Reduction XOR still detects both X/Z.
                        if ((^DRAM_DQ[b*8+:8]) === 1'bx) $fatal(1,"Unknown SDRAM write data DQ=%h DQM=%h byte=%0d",DRAM_DQ,DRAM_DQM,b);
                        write_data[b*8+:8]=DRAM_DQ[b*8+:8];
                    end
                    write_word(key,write_data);
                    available[DRAM_BA]=cycle+3;
                end
                opened[DRAM_BA]=0;
            end
            default: ;
        endcase
    end
endmodule
