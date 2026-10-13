// Experimental two-client mux. Ownership persists through every burst beat.
module execution_mux #(parameter BEATS=8)(
 input logic clk,reset,
 input logic [1:0] valid,wr,burst,
 input logic [24:0] address[0:1],
 input logic [31:0] data[0:1],input logic [3:0] bytes[0:1],
 output logic [1:0] ready,response,
 output wire [31:0] rdata,
 output wire mvalid,mwrite,mburst,output wire [24:0] maddress,
 output wire [31:0] mdata,output wire [3:0] mbytes,
 input logic mready,mresponse,input logic [31:0] mrdata
);
 logic owned,owner,last;logic [3:0] left;
 wire chosen=valid[1] && (!valid[0] || !last);
 assign mvalid=!owned && |valid;
 assign mwrite=wr[chosen];assign mburst=burst[chosen];
 assign maddress=address[chosen];assign mdata=data[chosen];assign mbytes=bytes[chosen];
 assign ready[0]=!owned && !chosen && mready;
 assign ready[1]=!owned && chosen && mready;
 assign response[0]=owned && !owner && mresponse;
 assign response[1]=owned && owner && mresponse;
 assign rdata=mrdata;
 always_ff @(posedge clk)begin
  if(reset)begin owned<=0;owner<=0;last<=1;left<=0;end
  else begin
   if(mvalid && mready)begin owned<=1;owner<=chosen;last<=chosen;left<=mburst && !mwrite?BEATS:1;end
   if(owned && mresponse)begin
    if(left==1)begin owned<=0;left<=0;end else left<=left-1'b1;
   end
  end
 end
endmodule
