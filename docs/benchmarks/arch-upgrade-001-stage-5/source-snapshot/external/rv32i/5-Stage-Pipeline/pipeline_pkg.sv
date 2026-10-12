package pipeline_pkg;

    typedef enum logic [3:0] {
        ADD = 4'b0000,
        SUB = 4'b0001,
        AND = 4'b0010,
        OR  = 4'b0011,
        XOR = 4'b0100,
        SLT = 4'b0101,
        SLTU = 4'b0110,
        SLL = 4'b0111,
        SRL = 4'b1000,
        SRA = 4'b1001,
        PASSB = 4'b1010
    } aluops;

    typedef enum logic [6:0] {
        R = 7'b0110011,
        I = 7'b0010011,
        L = 7'b0000011,
        S = 7'b0100011,
        B = 7'b1100011,
        JAL = 7'b1101111,
        JALR = 7'b1100111,
        LUI = 7'b0110111,
        AUIPC = 7'b0010111,
        FENCE = 7'b0001111
    } opcodes;

    // Prefixed to avoid conflict with opcodes members I, S, B
    typedef enum logic [2:0] {
        I_TYPE = 3'b000,
        S_TYPE = 3'b001,
        B_TYPE = 3'b010,
        U_TYPE = 3'b011,
        J_TYPE = 3'b100
    } instructiontypes;

    typedef enum logic [2:0] {
        BYTE = 3'b000,
        HALF = 3'b001,
        WORD = 3'b010,
        BYTEU = 3'b100,
        HALFU = 3'b101
    } loadtypes;
    
    typedef struct packed {
        // WB
        logic reg_write;
        logic [1:0] result_src;
        logic [4:0] rdaddr;
        // MEM
        logic mem_write;
        logic mem_read;
        logic branch;
        logic jump;
        logic jalr;
        logic [2:0] funct3;
        // EX
        logic pc_sel;
        logic alu_src;
        logic [3:0] ALU_Sel;
    } ctrl_t;

endpackage
