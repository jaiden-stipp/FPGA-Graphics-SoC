module HazardUnit(
    input logic id_ex_mem_read,
    input logic [4:0] id_ex_rdaddr,
    input logic [4:0] if_id_rs1addr,
    input logic [4:0] if_id_rs2addr,
    input logic if_id_uses_rs1,
    input logic if_id_uses_rs2,
    output logic stall
);
    always_comb begin
        stall = 1'b0;
        if (id_ex_mem_read && (id_ex_rdaddr != 5'b0) &&
        ((if_id_uses_rs1 && (id_ex_rdaddr == if_id_rs1addr)) ||
         (if_id_uses_rs2 && (id_ex_rdaddr == if_id_rs2addr))))
        begin
            stall = 1'b1;
        end
    end
endmodule
