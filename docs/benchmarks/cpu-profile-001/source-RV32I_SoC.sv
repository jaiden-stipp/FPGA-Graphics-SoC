import pipeline_pkg::*;

module RV32I_SoC(
    input logic clk,
    input logic rst,
    // Current fetch-stage PC for simple board-level observation.
    output logic [31:0] debug_pc,
    // Architectural trace used by the verification environment.
    output logic trace_valid,
    output logic [31:0] trace_pc,
    output logic [31:0] trace_instruction,
    output logic trace_reg_write,
    output logic [4:0] trace_rd,
    output logic [31:0] trace_rd_data,
    output logic trace_mem_read,
    output logic trace_mem_write,
    output logic [31:0] trace_mem_address,
    output logic [31:0] trace_mem_data,
    output logic [2:0] trace_mem_funct3,
    output logic trace_branch,
    output logic trace_jump,
    output logic trace_jalr,
    output logic commit_valid,
    input logic [31:0] soc_instruction, soc_rdata,
    input logic soc_misaligned, soc_write_performed,
    input tri0 soc_stall,
    output logic [31:0] soc_pc, soc_addr, soc_wdata,
    output logic [2:0] soc_funct3,
    output logic soc_read_en, soc_write_en,
    output wire [159:0] cpu_statistics
);

	ctrl_t ctrl_WB, ctrl_ID, ctrl_EX, ctrl_MEM;
    wire soc_advance = !soc_stall;
    // Stage 1: IF
    logic [31:0] pc, pc_target, Instruction;
    logic pc_src, stall;
    soc_cpu_counters performance (
        .clk(clk), .reset(rst), .memory_freeze(soc_stall),
        .retired(trace_valid), .dependency(stall), .redirect(pc_src),
        .statistics(cpu_statistics)
    );
    assign debug_pc = pc;

    soc_PC_IF pc_if (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .pc_target(pc_target),
        .pc_src(pc_src),
        .stall(stall),
        .pc(pc)
    );

    // IF/ID register
    logic valid_IF, valid_ID;
    logic [31:0] pc_ID, Instruction_ID;
    assign valid_IF = 1'b1;
    
    soc_IF_ID stage1 (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .stall(stall),
        .flush(pc_src),
        .valid_IF(valid_IF),
        .pc_IF(pc),
        .Instruction_IF(Instruction),
        .valid_ID(valid_ID),
        .pc_ID(pc_ID),
        .Instruction_ID(Instruction_ID)
    );

    // Stage 2: ID
    logic [6:0] opcode, funct7;
    logic [2:0] funct3;
    logic [4:0] rdaddr, rs1addr, rs2addr;
    assign opcode = Instruction_ID[6:0];
    assign rdaddr = Instruction_ID[11:7];
    assign funct3 = Instruction_ID[14:12];
    assign rs1addr = Instruction_ID[19:15];
    assign rs2addr = Instruction_ID[24:20];
    assign funct7 = Instruction_ID[31:25];
    logic halt;
    
    logic [2:0] imm_sel;

    ControlUnit CU (
        .opcode(opcode),
        .funct3(funct3),
        .funct7b5(funct7[5]),
        .rdaddr(rdaddr),
        .reg_write(ctrl_ID.reg_write),
        .alu_src(ctrl_ID.alu_src),
        .imm_sel(imm_sel),
        .mem_write(ctrl_ID.mem_write),
        .mem_read(ctrl_ID.mem_read),
        .branch(ctrl_ID.branch),
        .jump(ctrl_ID.jump),
        .jalr(ctrl_ID.jalr),
        .result_src(ctrl_ID.result_src),
        .ALU_Sel(ctrl_ID.ALU_Sel),
        .funct3_o(ctrl_ID.funct3),
        .rdaddr_o(ctrl_ID.rdaddr),
        .pc_sel(ctrl_ID.pc_sel)
    );

    logic [31:0] rs1out, rs2out, wr_data;

    soc_RegFile RF (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .rs1addr(rs1addr),
        .rs2addr(rs2addr),
        .rdaddr(ctrl_WB.rdaddr),
        .wr_en(ctrl_WB.reg_write),
        .wr_data(wr_data),
        .rs1out(rs1out),
        .rs2out(rs2out)
    );

    logic [31:0] imm_out;

    ImmGen IG (
        .Instruction(Instruction_ID),
        .imm_sel(imm_sel),
        .imm_out(imm_out)
    );
    logic uses_rs1_ID, uses_rs2_ID;

    always_comb begin
        uses_rs1_ID = 1'b0;
        uses_rs2_ID = 1'b0;
        case (opcode)
            R, S, B: begin
                uses_rs1_ID = 1'b1;
                uses_rs2_ID = 1'b1;
            end
            I, L, JALR: uses_rs1_ID = 1'b1;
            default: begin
                uses_rs1_ID = 1'b0;
                uses_rs2_ID = 1'b0;
            end
        endcase
    end

    HazardUnit HU (
        .id_ex_mem_read(ctrl_EX.mem_read),
        .id_ex_rdaddr(ctrl_EX.rdaddr),
        .if_id_rs1addr(rs1addr),
        .if_id_rs2addr(rs2addr),
        .if_id_uses_rs1(uses_rs1_ID),
        .if_id_uses_rs2(uses_rs2_ID),
        .stall(stall)
    );
    // ID/EX register
    logic valid_EX;
    logic [31:0] pc_EX, rs1_EX, rs2_EX, imm_EX, instruction_EX;
    logic [4:0] rs1addr_EX, rs2addr_EX;
    

    soc_ID_EX stage2 (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .stall(stall),
        .flush(pc_src),
        .valid_ID(valid_ID),
        .rs1addr_ID(rs1addr),
        .rs2addr_ID(rs2addr),
        .pc_ID(pc_ID),
        .rs1out(rs1out),
        .rs2out(rs2out),
        .imm_out(imm_out),
        .instruction_ID(Instruction_ID),
        .ctrl_ID(ctrl_ID),
        .valid_EX(valid_EX),
        .pc_EX(pc_EX),
        .rs1_EX(rs1_EX),
        .rs2_EX(rs2_EX),
        .imm_EX(imm_EX),
        .instruction_EX(instruction_EX),
        .rs1addr_EX(rs1addr_EX),
        .rs2addr_EX(rs2addr_EX),
        .ctrl_EX(ctrl_EX)
    );

    // Stage 3: EX
    logic [31:0] ALU_A, ALU_B, ALU_result;
    logic ALU_Zero;
    // Forwarding Unit extras
    logic [31:0] rs1_forward, rs2_forward;
    logic [1:0] forwardA_sel, forwardB_sel;
    logic valid_MEM;
    logic [31:0] pc_MEM, rs2_MEM, imm_MEM, ALU_result_MEM, instruction_MEM;
    
    ForwardMux Afw (
        .forwardSel(forwardA_sel),
        .reg_data_EX(rs1_EX),
        .ALU_result_MEM(ALU_result_MEM),
        .wr_data(wr_data),
        .reg_data_forward(rs1_forward)
    );
    ForwardMux Bfw (
        .forwardSel(forwardB_sel),
        .reg_data_EX(rs2_EX),
        .ALU_result_MEM(ALU_result_MEM),
        .wr_data(wr_data),
        .reg_data_forward(rs2_forward)
    );
    assign ALU_A = ctrl_EX.pc_sel ? pc_EX : rs1_forward;
    assign ALU_B = ctrl_EX.alu_src ? imm_EX : rs2_forward;

    
    ALU alu (
        .A(ALU_A),
        .B(ALU_B),
        .ALU_Sel(ctrl_EX.ALU_Sel),
        .ALU_result(ALU_result),
        .ALU_Zero(ALU_Zero)
    );
    
    logic ALU_Zero_MEM;
    BranchUnit BU (
        .jump(ctrl_EX.jump),
        .jalr(ctrl_EX.jalr),
        .branch(ctrl_EX.branch),
        .ALU_Zero(ALU_Zero),
        .funct3(ctrl_EX.funct3),
        .imm_EX(imm_EX),
        .ALU_result(ALU_result),
        .pc_EX(pc_EX),
        .pc_target(pc_target),
        .pc_src(pc_src)
    );
    // EX/MEM register
    soc_EX_MEM stage3 (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .valid_EX(valid_EX),
        .pc_EX(pc_EX),
        .rs2_EX(rs2_forward),
        .imm_EX(imm_EX),
        .ALU_result_EX(ALU_result),
        .instruction_EX(instruction_EX),
        .ALU_Zero(ALU_Zero),
        .ctrl_EX(ctrl_EX),
        .valid_MEM(valid_MEM),
        .pc_MEM(pc_MEM),
        .rs2_MEM(rs2_MEM),
        .imm_MEM(imm_MEM),
        .ALU_result_MEM(ALU_result_MEM),
        .instruction_MEM(instruction_MEM),
        .ALU_Zero_MEM(ALU_Zero_MEM),
        .ctrl_MEM(ctrl_MEM)
    );

    // Stage 4: MEM
    logic [31:0] mem_rdata;
    logic misaligned, mem_write_performed;

    // Generated SoC boundary: preserve the upstream zero-wait MEM timing.
    assign soc_pc = pc;
    assign soc_addr = ALU_result_MEM;
    assign soc_wdata = rs2_MEM;
    assign soc_funct3 = ctrl_MEM.funct3;
    assign soc_write_en = valid_MEM && ctrl_MEM.mem_write && !rst;
    assign soc_read_en = valid_MEM && ctrl_MEM.mem_read && !rst;
    assign Instruction = soc_instruction;
    assign mem_rdata = soc_rdata;
    assign misaligned = soc_misaligned;
    assign mem_write_performed = soc_write_performed;
    // MEM/WB register
    logic valid_WB;
    logic [31:0] ALU_result_WB, rdata_WB, pc_WB, instruction_WB, store_data_WB;
    

    soc_MEM_WB stage4 (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .valid_MEM(valid_MEM),
        .ALU_result_MEM(ALU_result_MEM),
        .rdata(mem_rdata),
        .pc_MEM(pc_MEM),
        .instruction_MEM(instruction_MEM),
        .store_data_MEM(rs2_MEM),
        .ctrl_MEM(ctrl_MEM),
        .valid_WB(valid_WB),
        .ALU_result_WB(ALU_result_WB),
        .rdata_WB(rdata_WB),
        .pc_WB(pc_WB),
        .instruction_WB(instruction_WB),
        .store_data_WB(store_data_WB),
        .ctrl_WB(ctrl_WB)
    );

    // ECALL and EBREAK are simulation stop markers in this educational core.
    // Detect them at retirement so a wrong-path instruction cannot halt a test.
    assign halt = soc_advance && valid_WB &&
        ((instruction_WB == 32'h00000073) ||
         (instruction_WB == 32'h00100073));

    // Stage 5: WB
    ResultMux RM (
        .result_src(ctrl_WB.result_src),
        .ALU_result(ALU_result_WB),
        .mem_rdata(rdata_WB),
        .pc_plus4(pc_WB + 32'd4),
        .wr_data(wr_data)
    );

    // Verification trace. A valid trace entry is emitted for every real
    // instruction reaching WB, including NOP/FENCE instructions with no
    // architectural side effect.
    assign trace_valid = soc_advance && valid_WB;
    assign trace_pc = pc_WB;
    assign trace_instruction = instruction_WB;
    assign trace_reg_write = soc_advance && valid_WB && ctrl_WB.reg_write;
    assign trace_rd = ctrl_WB.rdaddr;
    assign trace_rd_data = wr_data;
    assign trace_mem_read = soc_advance && valid_WB && ctrl_WB.mem_read;
    assign trace_mem_write = soc_advance && valid_WB && ctrl_WB.mem_write;
    assign trace_mem_address = ALU_result_WB;
    assign trace_mem_data = store_data_WB;
    assign trace_mem_funct3 = ctrl_WB.funct3;
    assign trace_branch = soc_advance && valid_WB && ctrl_WB.branch;
    assign trace_jump = soc_advance && valid_WB && ctrl_WB.jump;
    assign trace_jalr = soc_advance && valid_WB && ctrl_WB.jalr;
    assign commit_valid = soc_advance && valid_WB &&
        (ctrl_WB.reg_write || ctrl_WB.mem_write || ctrl_WB.branch ||
         ctrl_WB.jump || ctrl_WB.jalr);

    // Assertions are simulation-only and are intentionally kept outside the
    // synthesizable datapath.
    // synthesis translate_off
    soc_PipelineAssertions assertions (
        .enable(soc_advance),
        .clk(clk),
        .rst(rst),
        .stall(stall),
        .flush(pc_src),
        .pc(pc),
        .pc_ID(pc_ID),
        .instruction_ID(Instruction_ID),
        .valid_EX(valid_EX),
        .valid_ID(valid_ID),
        .misaligned(misaligned),
        .effective_mem_write(mem_write_performed),
        .forwardA_sel(forwardA_sel),
        .forwardB_sel(forwardB_sel),
        .rs1addr_EX(rs1addr_EX),
        .rs2addr_EX(rs2addr_EX),
        .x0_value(RF.registers[0]),
        .trace_valid(trace_valid),
        .commit_valid(commit_valid)
    );
    // synthesis translate_on
    ForwardingUnit FU (
        .id_ex_rs1addr(rs1addr_EX),
        .id_ex_rs2addr(rs2addr_EX),
        .ex_mem_rdaddr(ctrl_MEM.rdaddr),
        .ex_mem_reg_write(ctrl_MEM.reg_write),
        .mem_wb_rdaddr(ctrl_WB.rdaddr),
        .mem_wb_reg_write(ctrl_WB.reg_write),
        .forwardA_sel(forwardA_sel),
        .forwardB_sel(forwardB_sel)
    );
    // Monitor for testbench
    // synthesis translate_off
    logic [31:0] instruction_counter, cycle_counter;
    logic [31:0] stall_counter, flush_counter, forward_counter;

    logic instruction_retired;
    logic forward_used;

    assign instruction_retired = trace_valid;

    assign forward_used =
        valid_EX && ((forwardA_sel != 2'b00) ||
        (forwardB_sel != 2'b00));

    Monitor monitor (
        .clk(clk),
        .rst(rst),
        .instruction_retired(instruction_retired),
        .stall(stall),
        .flush(pc_src),
        .forward(forward_used),

        .instruction_counter(instruction_counter),
        .cycle_counter(cycle_counter),
        .stall_counter(stall_counter),
        .flush_counter(flush_counter),
        .forward_counter(forward_counter)
    );
    // synthesis translate_on
endmodule
