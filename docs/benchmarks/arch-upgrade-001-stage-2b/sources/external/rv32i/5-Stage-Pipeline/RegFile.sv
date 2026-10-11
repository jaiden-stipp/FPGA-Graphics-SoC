module RegFile(
    input logic clk,
    input logic rst,
    input logic [4:0] rs1addr,
    input logic [4:0] rs2addr, 
    input logic [4:0] rdaddr,
    input logic wr_en,
    input logic [31:0] wr_data,
    output logic [31:0] rs1out,
    output logic [31:0] rs2out
);
    logic [31:0] registers [31:0];

    always_comb begin
        rs1out = (rs1addr == 5'd0) ? 32'd0 : registers[rs1addr];
        rs2out = (rs2addr == 5'd0) ? 32'd0 : registers[rs2addr];

        // If register file is being written to in the same cycle, it pulls the value that is supposed to be there from a future stage into the new register out
        if (wr_en && (rdaddr != 5'd0) && (rdaddr == rs1addr)) begin
            rs1out = wr_data;
        end
        if (wr_en && (rdaddr != 5'd0) && (rdaddr == rs2addr)) begin
            rs2out = wr_data;
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            for (int i = 0; i < 32; i++) begin
                registers[i] <= 32'd0;
            end
        end else if (wr_en && rdaddr != 5'd0) begin
            registers[rdaddr] <= wr_data;
        end
    end
endmodule

