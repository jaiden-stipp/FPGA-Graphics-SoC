// Complete-transaction arbitration between instruction fills and data/DMA.
// Contested grants alternate; response ownership persists through every beat.
module sdram_fetch_arbiter(
 input logic clk,reset,
 input logic instruction_valid,input logic [24:0] instruction_address,
 output wire instruction_ready,instruction_response,output wire [31:0] instruction_data,
 input logic data_valid,data_write,data_burst,input logic [24:0] data_address,
 input logic [31:0] data_wdata,input logic [3:0] data_bytes,
 output wire data_ready,data_response,output wire [31:0] data_rdata,
 output wire memory_valid,memory_write,memory_burst,output wire [24:0] memory_address,
 output wire [31:0] memory_data,output wire [3:0] memory_bytes,
 input logic memory_ready,memory_response,input logic [31:0] memory_rdata
);
 logic owned,owner_data,last_data;logic [3:0] remaining;
 wire choose_data=data_valid && (!instruction_valid || !last_data);
 assign memory_valid=!owned && (instruction_valid || data_valid);
 assign memory_write=choose_data && data_write;
 assign memory_burst=choose_data?data_burst:1'b1;
 assign memory_address=choose_data?data_address:instruction_address;
 assign memory_data=choose_data?data_wdata:32'b0;
 assign memory_bytes=choose_data?data_bytes:4'hf;
 assign instruction_ready=!owned && !choose_data && memory_ready;
 assign data_ready=!owned && choose_data && memory_ready;
 assign instruction_response=owned && !owner_data && memory_response;
 assign data_response=owned && owner_data && memory_response;
 assign instruction_data=memory_rdata;assign data_rdata=memory_rdata;
 always_ff @(posedge clk)begin
  if(reset)begin owned<=0;owner_data<=0;last_data<=1;remaining<=0;end
  else begin
   if(memory_valid && memory_ready)begin
    owned<=1;owner_data<=choose_data;last_data<=choose_data;
    remaining<=memory_burst && !memory_write?8:1;
   end
   if(owned && memory_response)begin
    if(remaining==1)begin owned<=0;remaining<=0;end else remaining<=remaining-1'b1;
   end
  end
 end
endmodule
