// Experimental 4 KiB read-only I-cache. Falling-edge data read matches local RAM.
// No executable stores are permitted during execution; invalidate before reload.
module execution_fetch_cache(
 input logic clk,reset,invalidate,selected,advance,input logic [31:0] pc,
 output wire hit,output logic [31:0] instruction,
 output wire request_valid,output wire [24:0] request_address,
 input logic request_ready,response_valid,input logic [31:0] response_data,
 output logic [31:0] hits,misses,fills
);
 (* ramstyle="M9K" *) logic [31:0] words[0:1023];
 logic [14:0] tags[0:127];logic [127:0] valid;
 logic issuing,waiting,discard;logic [24:0] saved;logic [2:0] beat;
 assign hit=selected && valid[pc[11:5]] && tags[pc[11:5]]==pc[26:12];
 assign request_valid=issuing;
 assign request_address={saved[24:3],3'b0};
 always_ff @(negedge clk) instruction<=words[pc[11:2]];
 always_ff @(posedge clk)begin
  if(reset)begin valid<=0;issuing<=0;waiting<=0;saved<=0;beat<=0;discard<=0;hits<=0;misses<=0;fills<=0;end
  else begin
   if(invalidate)begin valid<=0;discard<=1;end
   if(selected && advance && hit)hits<=hits+1'b1;
   if(selected && !hit && !issuing && !waiting && !invalidate)begin
    saved<=pc[26:2];issuing<=1;beat<=0;discard<=0;misses<=misses+1'b1;
   end
   if(issuing && request_ready)begin issuing<=0;waiting<=1;end
   if(waiting && response_valid)begin
    words[{saved[9:3],beat}]<=response_data;fills<=fills+1'b1;
    if(beat==7)begin
     waiting<=0;
     if(!discard && !invalidate)begin tags[saved[9:3]]<=saved[24:10];valid[saved[9:3]]<=1;end
    end else beat<=beat+1'b1;
   end
  end
 end
endmodule
