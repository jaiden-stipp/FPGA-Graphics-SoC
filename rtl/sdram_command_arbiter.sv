// Non-preemptive, transaction-owned responses, round-robin contested grants.
module sdram_command_arbiter #(parameter integer BURST_WORDS=8)(
 input logic clk,reset,
 input logic cpu_valid,cpu_write,cpu_burst,
 input logic[24:0]cpu_address,
 input logic[31:0]cpu_data,
 input logic[3:0]cpu_bytes,
 output logic cpu_ready,cpu_response,
 output logic[31:0]cpu_rdata,
 input logic dma_valid,
 input logic[24:0]dma_address,
 output logic dma_ready,dma_response,
 output logic[31:0]dma_rdata,
 output logic memory_valid,memory_write,memory_burst,
 output logic[24:0]memory_address,
 output logic[31:0]memory_data,
 output logic[3:0]memory_bytes,
 input logic memory_ready,memory_response,
 input logic[31:0]memory_rdata
);
 typedef enum logic[1:0]{NONE,CPU,DMA} owner_t;
 owner_t owner;
 logic last_dma,choose_dma;
 logic[3:0]beats_left;
 assign choose_dma=dma_valid && (!cpu_valid || !last_dma);
 assign memory_valid=owner==NONE && (cpu_valid || dma_valid);
 assign memory_write=!choose_dma && cpu_write;
 assign memory_burst=choose_dma || cpu_burst;
 assign memory_address=choose_dma?dma_address:cpu_address;
 assign memory_data=choose_dma?32'b0:cpu_data;
 assign memory_bytes=choose_dma?4'hf:cpu_bytes;
 assign cpu_ready=owner==NONE && !choose_dma && memory_ready;
 assign dma_ready=owner==NONE && choose_dma && memory_ready;
 assign cpu_response=owner==CPU && memory_response;
 assign dma_response=owner==DMA && memory_response;
 assign cpu_rdata=memory_rdata;assign dma_rdata=memory_rdata;
 always_ff @(posedge clk)begin
  if(reset)begin owner<=NONE;last_dma<=1;beats_left<=0;end
  else begin
   if(memory_valid && memory_ready)begin
    owner<=choose_dma?DMA:CPU;last_dma<=choose_dma;
    beats_left<=(!memory_write && memory_burst)?BURST_WORDS:1;
   end
   if(memory_response && owner!=NONE)begin
    if(beats_left==1)begin owner<=NONE;beats_left<=0;end
    else beats_left<=beats_left-1'b1;
   end
  end
 end
endmodule
