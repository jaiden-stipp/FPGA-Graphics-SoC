// 4 KiB read-only instruction cache, 32-byte lines and complete BL8 fills.
// Falling-edge instruction read preserves the local-RAM CPU capture schedule.
// Invalidation drains transactions but never installs an invalidated fill.
module sdram_instruction_cache(
 input logic clk,reset,invalidate,selected,advance,input logic [31:0] pc,next_pc,
 output wire hit,output logic [31:0] instruction,
 output wire request_valid,output wire [24:0] request_address,
 input logic request_ready,response_valid,input logic [31:0] response_data,
 output logic [31:0] read_hits,read_misses,fill_words
);
 (* ramstyle="M9K" *) logic [31:0] words[0:1023];
 // Tags must stay asynchronous register logic. Inferring a block RAM here
 // changes lookup timing and adds a RAM-to-enable half-cycle critical path.
 (* ramstyle="logic" *) logic [14:0] tags[0:127];logic [127:0] valid;
 logic issuing,waiting,discard;logic [24:0] saved;logic [2:0] beat;
 logic lookup_hit;logic [21:0] lookup_line;
 wire cached_current=valid[pc[11:5]] && tags[pc[11:5]]==pc[26:12];
 // Give the tag mux/comparison a full cycle. Sequential lookahead keeps normal
 // hits fast; a different branch target line safely incurs one lookup bubble.
 assign hit=selected && !invalidate && lookup_hit && lookup_line==pc[26:5];
 assign request_valid=issuing;
 assign request_address={saved[24:3],3'b0};
 always_ff @(negedge clk) instruction<=words[pc[11:2]];
 always_ff @(posedge clk)begin
  if(reset)begin valid<=0;issuing<=0;waiting<=0;saved<=0;beat<=0;discard<=0;lookup_hit<=0;lookup_line<=0;read_hits<=0;read_misses<=0;fill_words<=0;end
  else begin
   lookup_line<=next_pc[26:5];
   lookup_hit<=!invalidate && valid[next_pc[11:5]] && tags[next_pc[11:5]]==next_pc[26:12];
   if(invalidate)begin valid<=0;discard<=1;end
   if(selected && advance && hit)read_hits<=read_hits+1'b1;
   if(selected && !cached_current && !issuing && !waiting && !invalidate)begin
    saved<=pc[26:2];issuing<=1;beat<=0;discard<=0;read_misses<=read_misses+1'b1;
   end
   if(issuing && request_ready)begin issuing<=0;waiting<=1;end
   if(waiting && response_valid)begin
    words[{saved[9:3],beat}]<=response_data;fill_words<=fill_words+1'b1;
    if(beat==7)begin
     waiting<=0;
     if(!discard && !invalidate)begin tags[saved[9:3]]<=saved[24:10];valid[saved[9:3]]<=1;end
    end else beat<=beat+1'b1;
   end
  end
 end
endmodule
