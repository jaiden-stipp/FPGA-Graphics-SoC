`timescale 1ns/1ps
module sdram_cache_tb #(parameter BURST_ENABLED=1, CACHE_LINE_BYTES=32);
    localparam LINE_WORDS=CACHE_LINE_BYTES/4;
    localparam TEST_WORD=LINE_WORDS-1;
    localparam FILL_TRANSACTIONS=BURST_ENABLED?1:LINE_WORDS;
    logic clk=0,reset=1,bypass=0,invalidate=0;
    always #10 clk=~clk;
    logic request_valid=0,request_write=0,request_ready,response_valid;
    logic [24:0] request_address=0,memory_address;
    logic [31:0] request_data=0,response_data,memory_data,memory_response_data;
    logic [3:0] request_byte_enable=15,memory_byte_enable;
    logic memory_valid,memory_write,memory_burst,memory_ready,memory_response_valid=0;
    logic [31:0] read_hits,read_misses,fill_words,write_requests,busy_cycles;
    sdram_cache #(.ENABLE_BURST(BURST_ENABLED),.CACHE_LINE_BYTES(CACHE_LINE_BYTES)) dut(.*);
    logic [31:0] backing [0:4095];
    logic [24:0] held_addr;
    logic [31:0] held_data;
    logic [3:0] held_bytes;
    logic held_write;
    integer countdown=0,transactions=0,remaining=0;
    assign memory_ready=countdown==0 && !memory_response_valid;
    // Deterministic handshake model. System tests also exercise the real SDRAM
    // controller/device timing and real CPU pipeline.
    always @(posedge clk) begin
        memory_response_valid<=0;
        if(reset) begin countdown<=0; transactions<=0; end
        else if(memory_valid && memory_ready) begin
            held_addr<=memory_address; held_data<=memory_data;
            held_bytes<=memory_byte_enable; held_write<=memory_write;
            remaining<=memory_burst?LINE_WORDS:1;
            countdown<=3; transactions<=transactions+1;
        end else if(countdown>1) countdown<=countdown-1;
        else if(countdown==1) begin
            if(held_write) for(integer b=0;b<4;b=b+1)
                if(held_bytes[b]) backing[held_addr][8*b +:8]<=held_data[8*b +:8];
            memory_response_data<=backing[held_addr];
            memory_response_valid<=1;
            if(remaining>1) begin remaining<=remaining-1;held_addr<=held_addr+1;end
            else countdown<=0;
        end
    end
    integer cold_cycles,hit_cycles,last_cycles,before_count;
    task automatic access(input bit wr,input [24:0] a,input [31:0] d,input [3:0] mask,input [31:0] expected);
        @(negedge clk); request_valid=1; request_write=wr;
        request_address=a; request_data=d; request_byte_enable=mask;
        @(posedge clk); #1;
        @(negedge clk); request_valid=0;
        last_cycles=0;
        while(!response_valid) begin
            @(posedge clk); #1; last_cycles=last_cycles+1;
            if(last_cycles>200) $fatal(1,"Cache request timeout");
        end
        if(!wr && response_data!==expected) $fatal(1,"Cache address=%h got=%h expected=%h",a,response_data,expected);
    endtask
    initial begin
        for(integer i=0;i<4096;i=i+1) backing[i]=32'h12340000+i;
        repeat(3) @(negedge clk); reset=0;
        access(0,TEST_WORD,0,15,32'h12340000+TEST_WORD); cold_cycles=last_cycles;
        if(transactions!=FILL_TRANSACTIONS || read_misses!=1 || fill_words!=LINE_WORDS) $fatal(1,"Cold fill counts");
        access(0,TEST_WORD,0,15,32'h12340000+TEST_WORD); hit_cycles=last_cycles;
        for(integer i=0;i<LINE_WORDS;i=i+1) access(0,i,0,15,32'h12340000+i);
        if(transactions!=FILL_TRANSACTIONS || read_hits!=LINE_WORDS+1 || hit_cycles>=cold_cycles) $fatal(1,"Hit path");
        access(1,TEST_WORD,32'h00aa0000,4'b0100,0);
        if(backing[TEST_WORD]!==32'h12aa0000+TEST_WORD) $fatal(1,"Write-through byte mask");
        access(0,TEST_WORD,0,15,32'h12aa0000+TEST_WORD);
        access(1,200,32'h89abcdef,15,0);
        before_count=transactions;
        access(0,200,0,15,32'h89abcdef);
        if(transactions-before_count!=FILL_TRANSACTIONS) $fatal(1,"Write miss must not allocate");
        access(0,1024+TEST_WORD,0,15,32'h12340400+TEST_WORD); // same index, different tag
        before_count=transactions;
        access(0,TEST_WORD,0,15,32'h12aa0000+TEST_WORD);
        if(transactions-before_count!=FILL_TRANSACTIONS) $fatal(1,"Conflict replacement");
        @(negedge clk); bypass=1; invalidate=1;
        access(1,TEST_WORD,32'hdeadbeef,15,0);
        before_count=transactions;
        access(0,TEST_WORD,0,15,32'hdeadbeef);
        if(transactions-before_count!=1 || dut.valid!=0) $fatal(1,"Loader bypass");
        @(negedge clk); bypass=0; invalidate=0;
        access(0,TEST_WORD,0,15,32'hdeadbeef);
        // Invalidate while a fill is active; draining it must not revalidate.
        fork
            access(0,64,0,15,32'h12340040);
            begin wait(dut.filling); @(negedge clk); invalidate=1;
                @(negedge clk); invalidate=0; end
        join
        if(dut.valid!=0) $fatal(1,"Invalidated fill installed stale line");
        before_count=transactions;
        access(0,64,0,15,32'h12340040);
        if(transactions-before_count!=FILL_TRANSACTIONS) $fatal(1,"Refill after invalidation");
        // Invalidate on the last returned beat, when installing the tag and
        // valid bit would otherwise occur. No partial/stale line may survive.
        fork
            access(0,80,0,15,32'h12340050);
            begin
                wait(dut.filling && dut.fill_offset==LINE_WORDS-1 && memory_response_valid);
                invalidate=1;
                @(negedge clk); @(negedge clk); invalidate=0;
            end
        join
        if(dut.valid!=0) $fatal(1,"Last-beat invalidation installed a line");
        // Deterministic mixed-address/mask workload against backing memory.
        for(integer i=0;i<128;i=i+1) begin
            access(1,(i*37)%4096,32'habcd0000+i,4'b0011,0);
            access(0,(i*37)%4096,0,15,backing[(i*37)%4096]);
        end
        $display("CACHE_MODEL cold_request_wait_cycles=%0d hit_request_wait_cycles=%0d (synthetic backing memory, not board performance)",cold_cycles,hit_cycles);
        $display("PASS sdram_cache_tb (line fills, hits, conflict replacement, byte stores, no allocation, loader bypass, in-flight invalidation, mixed requests)");
        $finish;
    end
    initial begin #2000000; $fatal(1,"Cache test timeout"); end
endmodule
