// One owned descriptor; 32-byte SDRAM bursts; completion means FIFO acceptance.
module gfx_command_dma(
 input logic clk,reset,cancel,start,
 input logic [31:0] source,length,submission_id,
 output logic busy,
 output logic [7:0] error_code,
 output logic [31:0] completed_id,bytes_sent,read_words,request_wait,fifo_wait,
 output logic memory_valid,
 output logic [24:0] memory_address,
 input logic memory_ready,memory_response_valid,
 input logic [31:0] memory_response_data,
 output logic byte_valid,
 output logic [7:0] byte_data,
 input logic byte_accepted
);
 typedef enum logic[2:0] {IDLE,CHECK,REQUEST,FILL,STREAM} state_t;
 state_t state;
 logic [31:0] remaining,active_id,active_source;
 logic [24:0] word_address;
 logic [31:0] line [0:7];
 logic [2:0] beat;
 logic [4:0] byte_index;
 logic cancel_pending;
 wire [32:0] rounded_end={1'b0,active_source}+(({1'b0,remaining}+33'd31)&33'h1ffffffe0);
 wire descriptor_ok=active_source[4:0]==0 && active_source>=32'h80000000 && remaining!=0 && remaining<=65536 && rounded_end<=33'h087fff000;
 assign busy=state!=IDLE;
 assign memory_valid=state==REQUEST && !cancel;
 assign memory_address=word_address;
 assign byte_valid=state==STREAM && !cancel && !cancel_pending;
 assign byte_data=line[byte_index[4:2]][byte_index[1:0]*8+:8];
 always_ff @(posedge clk)begin
  if(reset)begin
   state<=IDLE;remaining<=0;active_id<=0;active_source<=0;word_address<=0;beat<=0;byte_index<=0;cancel_pending<=0;
   error_code<=0;completed_id<=0;bytes_sent<=0;read_words<=0;request_wait<=0;fifo_wait<=0;
  end else begin
   if(memory_valid && !memory_ready)request_wait<=request_wait+1'b1;
   if(byte_valid && !byte_accepted)fifo_wait<=fifo_wait+1'b1;
   // An accepted burst always drains; loader hold suppresses stream publication.
   if(cancel && state!=FILL)begin state<=IDLE;cancel_pending<=0;end
   else case(state)
    IDLE:if(start && !cancel)begin
     error_code<=0;
     // Capture the opposite-edge MMIO fields first. Validate on a full-cycle
     // path rather than placing two 33-bit additions on the half-cycle input.
     state<=CHECK;active_source<=source;word_address<=source[26:2];remaining<=length;active_id<=submission_id;byte_index<=0;cancel_pending<=0;
    end
    CHECK:begin
     if(!descriptor_ok)begin error_code<=1;state<=IDLE;end
     else state<=REQUEST;
    end
    REQUEST:if(memory_ready)begin state<=FILL;beat<=0;end
    FILL:begin
     if(cancel)cancel_pending<=1;
     if(memory_response_valid)begin
      read_words<=read_words+1'b1;line[beat]<=memory_response_data;
      if(beat==7)begin
       if(cancel || cancel_pending)begin state<=IDLE;cancel_pending<=0;end
       else begin state<=STREAM;byte_index<=0;end
      end else beat<=beat+1'b1;
     end
    end
    STREAM:if(byte_accepted)begin
     bytes_sent<=bytes_sent+1'b1;remaining<=remaining-1'b1;
     if(remaining==1)begin state<=IDLE;completed_id<=active_id;end
     else if(byte_index==31)begin state<=REQUEST;word_address<=word_address+25'd8;end
     else byte_index<=byte_index+1'b1;
    end
   endcase
  end
 end
endmodule
