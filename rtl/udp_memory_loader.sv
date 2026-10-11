`include "renderer_types.svh"
// Versioned SD envelope inside SET_VIEW_MATRIX, consumed before the GPU.
// BEGIN/WRITE/READ/COMMIT/STATUS = 1/2/3/4/5. Count is low nibble, 1..3.
module udp_memory_loader #(
    parameter bit REQUIRE_LOAD = 0,
    parameter logic[31:0] GPU_FEATURES=3,
`ifdef SOC_GEOMETRY_WORKER
    parameter logic[31:0] CPU_FEATURES=32'h80000003
`else
    parameter logic[31:0] CPU_FEATURES=32'h80000001
`endif
)(
    input logic clk, reset,
    input graphics_command_t command_data,
    input logic command_valid,
    output logic command_ready, envelope, error, hold_cpu,
    output logic bus_valid, bus_write,
    output logic [31:0] bus_addr, bus_wdata,
    input logic bus_ready,
    input logic [31:0] bus_rdata,
    input logic initialized,
    input logic [31:0] scratch, refresh_count,
    output logic reply_valid,
    output logic [31:0] reply_id,
    output logic [415:0] reply_statistics
);
    typedef enum logic [2:0] {IDLE, SETTLE, ISSUE, GAP, REPLY} state_t;
    state_t state;
    logic [3:0] operation, count;
    logic [1:0] index;
    logic [31:0] words[0:2], results[0:2];
    logic [31:0] base, status, transaction;
    logic [6:0] settle;
    logic [3:0] incoming_op, incoming_count;
    logic [31:0] incoming_addr, final_addr;
    logic valid_range;
    assign envelope = command_data.opcode == GFX_CMD_SET_VIEW_MATRIX &&
                      command_data.payload[191:168] == 24'h534401;
    assign incoming_op = command_data.payload[167:164];
    assign incoming_count = command_data.payload[163:160];
    assign incoming_addr = command_data.payload[127:96];
    assign final_addr = incoming_addr + ({28'b0,incoming_count} << 2)-1;
    assign valid_range = incoming_addr[1:0] == 0 && incoming_count >= 1 && incoming_count <= 3 &&
        ((incoming_addr < 32'h10000 && final_addr < 32'h10000) ||
         (incoming_addr >= 32'h80000000 && final_addr < 32'h88000000 && final_addr >= incoming_addr));
    assign command_ready = state == IDLE;
    assign bus_valid = state == ISSUE;
    assign bus_write = operation == 2;
    assign bus_addr = base + ({30'b0,index} << 2);
    assign bus_wdata = words[index];
    // First word is a signature, second result/status. Next three are read data.
    // Final two reserved words now mirror soc_mmio CPU/GPU features for
    // read-only package preflight while the CPU runs; older images report zero.
    assign reply_statistics = {32'h53440100,status,results[0],results[1],results[2],
        {30'b0,initialized,hold_cpu},scratch,refresh_count,base,{28'b0,count},32'h494e0101,CPU_FEATURES,GPU_FEATURES};
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state <= IDLE; hold_cpu <= REQUIRE_LOAD; reply_valid <= 0;
            reply_id <= 0; error <= 0; status <= 0; transaction <= 0;
            base <= 0; operation <= 0; count <= 0; index <= 0; settle <= 0;
            for (integer i=0;i<3;i=i+1) begin words[i] <= 0; results[i] <= 0; end
        end else begin
            reply_valid <= 0;
            case (state)
                IDLE: if (command_valid && envelope) begin
                    transaction <= command_data.payload[159:128]; base <= incoming_addr;
                    operation <= incoming_op; count <= incoming_count; index <= 0; status <= 0;
                    words[0] <= command_data.payload[95:64];
                    words[1] <= command_data.payload[63:32]; words[2] <= command_data.payload[31:0];
                    for (integer i=0;i<3;i=i+1) results[i] <= 0;
                    case (incoming_op)
                        1: begin hold_cpu <= 1; settle <= 63; state <= SETTLE; end
                        2,3: if (hold_cpu && initialized && valid_range) state <= ISSUE;
                             else begin status <= 1; error <= 1; state <= REPLY; end
                        4: begin
                            if (hold_cpu && initialized) hold_cpu <= 0;
                            else if (!initialized) begin status <= 2; error <= 1; end
                            state <= REPLY;
                        end
                        5: state <= REPLY;
                        default: begin status <= 3; error <= 1; state <= REPLY; end
                    endcase
                end
                SETTLE: if (settle != 0) settle <= settle-1'b1; else state <= REPLY;
                ISSUE: if (bus_ready) begin
                    results[index] <= bus_rdata;
                    if (index+1 >= count) state <= REPLY;
                    else begin index <= index+1'b1; state <= GAP; end
                end
                GAP: state <= ISSUE;
                REPLY: begin reply_id <= transaction; reply_valid <= 1; state <= IDLE; end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
