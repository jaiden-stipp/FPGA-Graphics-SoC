`timescale 1ns/1ps
// Small table deliberately forces hash collisions across distant SDRAM words.
module sdram_model_storage_tb;
    wire [31:0] dq;
    sdram_device_model #(.STORAGE_BITS(3)) chip (
        .DRAM_CLK(1'b0),.DRAM_CKE(1'b0),.DRAM_CS_N(1'b1),
        .DRAM_RAS_N(1'b1),.DRAM_CAS_N(1'b1),.DRAM_WE_N(1'b1),
        .DRAM_ADDR(13'b0),.DRAM_BA(2'b0),.DRAM_DQM(4'b0),.DRAM_DQ(dq)
    );
    initial begin
        if(chip.read_word(0)!==0) $fatal(1,"Unwritten SDRAM must read zero");
        chip.write_word(0,32'h12345678);
        chip.write_word(9,32'habcdef01); // Same hash as zero at STORAGE_BITS=3.
        chip.write_word(25'h1ffffff,32'hfeedface);
        if(chip.read_word(0)!==32'h12345678 || chip.read_word(9)!==32'habcdef01 ||
           chip.read_word(25'h1ffffff)!==32'hfeedface || chip.read_word(18)!==0)
            $fatal(1,"Sparse SDRAM addresses alias or unwritten collision reads data");
        chip.write_word(9,32'h76543210);
        if(chip.read_word(9)!==32'h76543210 || chip.read_word(0)!==32'h12345678)
            $fatal(1,"Sparse SDRAM overwrite changed another word");
        $display("PASS sdram_model_storage_tb");
        $finish;
    end
endmodule
