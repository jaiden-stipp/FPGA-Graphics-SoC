module ForwardingUnit (
    input logic [4:0] id_ex_rs1addr,   
    input logic [4:0] id_ex_rs2addr,
    input logic [4:0] ex_mem_rdaddr,   
    input logic ex_mem_reg_write,
    input logic [4:0] mem_wb_rdaddr,    
    input logic mem_wb_reg_write,
    output logic [1:0] forwardA_sel,
    output logic [1:0] forwardB_sel 
);
    always_comb begin
        forwardA_sel = 2'b00;
        forwardB_sel = 2'b00;
        // EX hazard
        if ((ex_mem_reg_write) && 
        (ex_mem_rdaddr != 5'b0) && 
        (ex_mem_rdaddr == id_ex_rs1addr)) 
        begin
            forwardA_sel = 2'b10;
        end
        else if ((mem_wb_reg_write) && 
        (mem_wb_rdaddr != 5'b0) && 
        !(ex_mem_reg_write && (ex_mem_rdaddr != 5'b0) && (ex_mem_rdaddr == id_ex_rs1addr)) && 
        (mem_wb_rdaddr == id_ex_rs1addr)) 
        begin
            forwardA_sel = 2'b01;
        end

        if ((ex_mem_reg_write) && 
        (ex_mem_rdaddr != 5'b0) && 
        (ex_mem_rdaddr == id_ex_rs2addr)) 
        begin
            forwardB_sel = 2'b10;
        end
        else if ((mem_wb_reg_write) && 
        (mem_wb_rdaddr != 5'b0) && 
        !(ex_mem_reg_write && (ex_mem_rdaddr != 5'b0) && (ex_mem_rdaddr == id_ex_rs2addr)) && 
        (mem_wb_rdaddr == id_ex_rs2addr)) 
        begin
            forwardB_sel = 2'b01;
        end
    end
        
endmodule