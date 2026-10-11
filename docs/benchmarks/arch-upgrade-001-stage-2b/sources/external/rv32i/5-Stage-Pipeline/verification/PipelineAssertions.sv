`timescale 1ns/1ps

// Simulation-only safety checks written as procedural assertions so they run
// with the Intel ModelSim Edition shipped with Quartus.
module PipelineAssertions (
    input logic clk,
    input logic rst,
    input logic stall,
    input logic flush,
    input logic [31:0] pc,
    input logic [31:0] pc_ID,
    input logic [31:0] instruction_ID,
    input logic valid_ID,
    input logic valid_EX,
    input logic misaligned,
    input logic effective_mem_write,
    input logic [1:0] forwardA_sel,
    input logic [1:0] forwardB_sel,
    input logic [4:0] rs1addr_EX,
    input logic [4:0] rs2addr_EX,
    input logic [31:0] x0_value,
    input logic trace_valid,
    input logic commit_valid
);

    logic stall_previous;
    logic flush_previous;
    logic [31:0] pc_previous;
    logic [31:0] pc_id_previous;
    logic [31:0] instruction_id_previous;
    logic misaligned_previous;
    logic effective_write_previous;

    task automatic assertion_fail(input string message);
        $display("ASSERTION FAIL: %s", message);
        $fatal(1);
    endtask

    always @(posedge clk) begin
        #1;
        if (rst) begin
            stall_previous = 1'b0;
            flush_previous = 1'b0;
            pc_previous = pc;
            pc_id_previous = pc_ID;
            instruction_id_previous = instruction_ID;
            misaligned_previous = 1'b0;
            effective_write_previous = 1'b0;
        end else begin
            // A load-use stall holds fetch and decode state for one cycle.
            if (stall_previous &&
                ((pc !== pc_previous) ||
                 (pc_ID !== pc_id_previous) ||
                 (instruction_ID !== instruction_id_previous))) begin
                assertion_fail("PC or IF/ID state changed while stalled");
            end

            // A redirected control transfer injects a bubble into ID/EX.
            if (flush_previous && valid_EX)
                assertion_fail("ID/EX was not invalidated after redirect");

            // Misaligned accesses must never perform a write.
            if ((misaligned && effective_mem_write) ||
                (misaligned_previous && effective_write_previous))
                assertion_fail("misaligned access performed a write");

            if (x0_value !== 32'b0)
                assertion_fail("x0 changed from zero");

            if ((forwardA_sel == 2'b11) || (forwardB_sel == 2'b11))
                assertion_fail("illegal forwarding select");

            if ((rs1addr_EX == 5'd0) && (forwardA_sel != 2'b00))
                assertion_fail("rs1=x0 selected a forwarding path");

            if ((rs2addr_EX == 5'd0) && (forwardB_sel != 2'b00))
                assertion_fail("rs2=x0 selected a forwarding path");

            if (commit_valid && !trace_valid)
                assertion_fail("commit event did not produce a trace entry");

            stall_previous = stall;
            flush_previous = flush;
            pc_previous = pc;
            pc_id_previous = pc_ID;
            instruction_id_previous = instruction_ID;
            misaligned_previous = misaligned;
            effective_write_previous = effective_mem_write;
        end
    end

endmodule
