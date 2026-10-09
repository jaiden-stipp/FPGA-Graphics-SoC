`timescale 1ns/1ps
module soc_mmio_tb;
    logic clk = 0, reset = 1;
    always #5 clk = ~clk;
    logic [31:0] addr = 0, wdata = 0, rdata, scratch;
    logic [2:0] funct3 = 2;
    logic read_en = 0, write_en = 0, write_performed;
    logic [7:0] byte_data;
    logic byte_valid, byte_ready = 0;
    logic decoder_error = 0, command_error = 0, frame_done = 0;
    logic [31:0] frame_done_id = 0;
    logic [415:0] frame_statistics = 0;
    logic [7:0] buttons = 0;
    logic [23:0] look_state=0;
    logic [191:0] cache_statistics={32'h43410101,32'd11,32'd12,32'd13,32'd14,32'd15};
    logic frame_pending;
    logic [3:0] error_flags;
    soc_mmio #(.FIFO_DEPTH(3)) dut (.*);

    task automatic put(input logic [7:0] offset, input logic [31:0] data,
                       input logic accepted);
        @(negedge clk);
        addr = 32'h40000000 + offset; wdata = data; write_en = 1;
        #1;
        if (write_performed !== accepted) $fatal(1, "Write acceptance at %h", addr);
        @(posedge clk); #1; write_en = 0;
    endtask
    task automatic get(input logic [7:0] offset, input logic [31:0] expected);
        @(negedge clk);
        addr = 32'h40000000 + offset; read_en = 1;
        #1;
        if (rdata !== expected) $fatal(1, "Read %h got %h expected %h", addr, rdata, expected);
        @(posedge clk); #1; read_en = 0;
    endtask
    task automatic take(input logic [7:0] expected);
        @(negedge clk); byte_ready = 1; #1;
        if (!byte_valid || byte_data !== expected) $fatal(1, "FIFO order");
        @(posedge clk); #1; byte_ready = 0;
    endtask
    initial begin
        repeat (2) @(negedge clk); reset = 0;
        get('h1c, 32'h534f4301);
        get('h04, 3);
        put(0, 'haa, 1); put(0, 'hbb, 1); put(0, 'hcc, 1);
        get('h08, 0);
        // Hold downstream stalled: head must remain unchanged.
        repeat (4) begin
            @(negedge clk);
            if (!byte_valid || byte_data != 'haa) $fatal(1, "Backpressure changed head");
        end
        put(0, 'hdd, 0); get('h14, 1);
        take('haa); put(0, 'hdd, 1); // non-power-of-two wrap
        take('hbb); take('hcc); take('hdd);
        get('h08, 3);
        put('h14, 1, 1); get('h14, 0);
        put(0, 'h11, 1);
        @(negedge clk);
        addr = 32'h40000000; wdata = 'h22; write_en = 1; byte_ready = 1;
        @(posedge clk); #1; write_en = 0; byte_ready = 0;
        get('h08, 2); take('h22);
        funct3 = 0; put(0, 'h99, 0); funct3 = 2;
        get('h14, 8); put('h14, 8, 1);
        get('h60, 0); get('h14, 8); put('h14, 8, 1);
        get('h5c, 50000000);
        get('h68,32'h43410101); get('h6c,11); get('h70,12);
        get('h74,13); get('h78,14); get('h7c,15);
        @(negedge clk); buttons = 2'b10;
        repeat (3) @(negedge clk);
        get('h54, 2);
        get('h64, 32'h494e0101);
        look_state=24'h80fe80; repeat(3) @(negedge clk);
        get('h54,32'h80fe8002);
        look_state=0; repeat(3) @(negedge clk);
        @(negedge clk); addr = 32'h40000058; read_en = 1; #1;
        begin
            logic [31:0] before_cycles;
            before_cycles = rdata;
            repeat (4) @(negedge clk);
            #1;
            if (rdata - before_cycles != 4) $fatal(1, "Cycle timer");
        end
        read_en = 0;
        @(negedge clk);
        decoder_error = 1; command_error = 1;
        @(posedge clk); #1; decoder_error = 0; command_error = 0;
        get('h14, 6);
        // New errors and frame completion win against simultaneous W1C / ACK.
        @(negedge clk);
        addr = 32'h40000014; wdata = 6; write_en = 1; decoder_error = 1;
        @(posedge clk); #1; write_en = 0; decoder_error = 0;
        get('h14, 2); put('h14, 2, 1);
        @(negedge clk);
        frame_done = 1; frame_done_id = 42; frame_statistics = {32'd123, 384'b0};
        addr = 32'h40000010; wdata = 1; write_en = 1;
        @(posedge clk); #1; frame_done = 0; write_en = 0;
        get('h0c, 42); get('h20, 123); get('h04, 7);
        put('h10, 1, 1); get('h04, 3);
        put('h18, 'h12345678, 1); get('h18, 'h12345678);
        put(0, 'haa, 1);
        @(negedge clk); reset = 1;
        @(negedge clk); reset = 0;
        get('h08, 3); get('h14, 0); get('h18, 0);
        $display("PASS soc_mmio_tb"); $finish;
    end
    initial begin #10000; $fatal(1, "Timeout"); end
endmodule
