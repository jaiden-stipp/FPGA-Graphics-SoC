`timescale 1ns/1ps
// Sparse JEDEC command model for the board's 13-row/10-column/2-bank-bit pair.
// Checks initialization/timing/refresh, CL3 read delay, auto-precharge and DQM.
// Physical signal integrity is verified separately by the on-board self-test.
module sdram_device_model (
    input wire DRAM_CLK, DRAM_CKE, DRAM_CS_N, DRAM_RAS_N, DRAM_CAS_N, DRAM_WE_N,
    input wire [12:0] DRAM_ADDR,
    input wire [1:0] DRAM_BA,
    input wire [3:0] DRAM_DQM,
    inout wire [31:0] DRAM_DQ
);
    logic [31:0] memory[int unsigned];
    logic [12:0] row[0:3];
    bit opened[0:3];
    integer available[0:3], activated[0:3];
    integer cycle=0, refreshes=0, last_refresh=0, read_delay=0;
    bit mode_set=0, precharged=0, drive=0;
    logic [31:0] output_data, pending_data;
    integer unsigned key;
    assign DRAM_DQ=drive ? output_data : 32'bz;
    initial for (integer i=0;i<4;i=i+1) begin opened[i]=0; available[i]=0; activated[i]=0; end
    always @(posedge DRAM_CLK) begin
        cycle=cycle+1;
        if (drive) begin drive<=#2.7 0; end
        if (read_delay!=0) begin
            if (read_delay==1) begin output_data<=#6.4 pending_data; drive<=#6.4 1; end
            read_delay=read_delay-1;
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
                if (refreshes<8 || DRAM_ADDR!=13'h230 || DRAM_BA!=0) $fatal(1,"Bad SDRAM mode/init sequence");
                mode_set=1; last_refresh=cycle;
            end
            3'b011: begin // activate
                if (!mode_set || opened[DRAM_BA] || cycle<available[DRAM_BA]) $fatal(1,"Bad SDRAM activate");
                row[DRAM_BA]=DRAM_ADDR; opened[DRAM_BA]=1; activated[DRAM_BA]=cycle;
            end
            3'b101,3'b100: begin
                if (!opened[DRAM_BA] || cycle-activated[DRAM_BA]<2 || !DRAM_ADDR[10]) $fatal(1,"Bad SDRAM column command/tRCD");
                key={row[DRAM_BA],DRAM_BA,DRAM_ADDR[9:0]};
                if (DRAM_WE_N) begin
                    pending_data=memory.exists(key) ? memory[key] : 0; read_delay=3;
                    available[DRAM_BA]=cycle+6;
                end else begin
                    if (!memory.exists(key)) memory[key]=0;
                    for (integer b=0;b<4;b=b+1) if (!DRAM_DQM[b]) begin
                        if ($isunknown(DRAM_DQ[b*8+:8])) $fatal(1,"Unknown SDRAM write data");
                        memory[key][b*8+:8]=DRAM_DQ[b*8+:8];
                    end
                    available[DRAM_BA]=cycle+3;
                end
                opened[DRAM_BA]=0;
            end
            default: ;
        endcase
    end
endmodule
