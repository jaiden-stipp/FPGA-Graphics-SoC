`timescale 1ns/1ps
module soc_memory_tb;
    logic clk = 0, reset = 1;
    always #5 clk = ~clk;
    logic [31:0] pc = 0, addr = 0, wdata = 0, instruction, rdata, scratch;
    logic [2:0] funct3 = 2;
    logic read_en = 0, write_en = 0, misaligned, write_performed;
    logic [7:0] byte_data;
    logic byte_valid, byte_ready = 0, frame_pending;
    logic [3:0] error_flags;
    soc_memory #(.HEX_FILE("")) dut (
        .clk(clk), .reset(reset), .pc(pc), .addr(addr), .wdata(wdata),
        .funct3(funct3), .read_en(read_en), .write_en(write_en),
        .instruction(instruction), .rdata(rdata), .misaligned(misaligned),
        .write_performed(write_performed), .byte_data(byte_data),
        .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(1'b0), .command_error(1'b0), .frame_done(1'b0),
        .frame_done_id(32'b0), .frame_statistics(416'b0),
        .buttons(8'b0),
        .frame_pending(frame_pending), .error_flags(error_flags), .scratch(scratch)
    );
    task automatic store(input logic [31:0] a, input logic [31:0] v,
                         input logic [2:0] f, input logic accepted);
        @(posedge clk); #1; addr = a; wdata = v; funct3 = f; write_en = 1; #1;
        if (write_performed !== accepted) $fatal(1, "Store acceptance");
        @(negedge clk); #1; write_en = 0;
    endtask
    task automatic load(input logic [31:0] a, input logic [2:0] f, input logic [31:0] expected);
        @(posedge clk); #1; addr = a; funct3 = f; read_en = 1; #1;
        if (rdata !== expected) $fatal(1, "Load %h got %h expected %h", a, rdata, expected);
        @(negedge clk); #1; read_en = 0;
    endtask
    initial begin
        repeat (2) @(posedge clk); #1; reset = 0;
        store(0, 'h12345678, 2, 1); load(0, 2, 'h12345678);
        if (instruction !== 'h12345678) $fatal(1, "Instruction port");
        store(1, 'h80, 0, 1); load(1, 0, 'hffffff80); load(1, 4, 'h80);
        store(2, 'h8001, 1, 1); load(2, 1, 'hffff8001); load(2, 5, 'h8001);
        load(0, 2, 'h80018078);
        store(1, 'hffffffff, 2, 0); load(0, 2, 'h80018078);
        store('hfffc, 'habcdef01, 2, 1); load('hfffc, 2, 'habcdef01);
        store('h10000, 'hffffffff, 2, 0); load('h40000014, 2, 8);
        store('h40000014, 8, 2, 1);
        store('h40000018, 'hfeedbeef, 2, 1); load('h40000018, 2, 'hfeedbeef);
        load(0, 2, 'h80018078); // MMIO must never alias low RAM.
        pc = 'h10000; #1;
        if (instruction !== 'h13) $fatal(1, "Fetch bounds");
        $display("PASS soc_memory_tb"); $finish;
    end
    initial begin #10000; $fatal(1, "Timeout"); end
endmodule
