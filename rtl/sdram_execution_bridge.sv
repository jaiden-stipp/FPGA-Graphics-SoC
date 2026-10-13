// SDRAM MEM completion is consumed only when the entire CPU can advance.
// Loader ownership changes cancel unissued requests or drain issued requests.
module sdram_execution_bridge(
 input logic clk,reset,cpu_reset,load_hold,load_valid,advance,
 input logic selected,read_en,write_en,input logic [31:0] addr,wdata,
 input logic [2:0] funct3,
 output logic [31:0] rdata,output wire stall,misaligned,write_performed,
 output wire request_valid,output logic request_write,output logic [24:0] request_address,
 output logic [31:0] request_data,output logic [3:0] request_byte_enable,
 input logic request_ready,response_valid,input logic [31:0] response_data
);
 logic pending,accepted,completed,consumed,owner_loader,discard,access_bad;
 logic [2:0] saved_funct3;logic [1:0] saved_lane;logic [31:0] shifted;
 wire owner_valid=owner_loader==load_hold && (owner_loader || !cpu_reset);
 always_comb begin
  access_bad=0;
  case(funct3)
   3'b000,3'b100:access_bad=write_en && funct3[2];
   3'b001,3'b101:access_bad=addr[0] || (write_en && funct3[2]);
   3'b010:access_bad=|addr[1:0];
   default:access_bad=1;
  endcase
 end
 assign misaligned=selected && (read_en || write_en) && access_bad;
 assign stall=selected && (read_en || write_en) && !access_bad && !(completed && owner_valid);
 assign request_valid=pending && !accepted && owner_valid && !discard;
 assign write_performed=completed && owner_valid && !owner_loader && request_write && advance;
 // Handshakes and consumption are sampled on the CPU advancement edge.
 always_ff @(posedge clk)begin
  if(reset)begin accepted<=0;consumed<=0;end
  else begin
   if(!pending)accepted<=0;
   else if(request_valid && request_ready)accepted<=1;
   consumed<=completed && owner_valid && (load_hold?load_valid:advance);
  end
 end
 always_ff @(negedge clk)begin
  if(reset)begin
   pending<=0;completed<=0;owner_loader<=0;discard<=0;rdata<=0;
   request_write<=0;request_address<=0;request_data<=0;request_byte_enable<=0;saved_funct3<=0;saved_lane<=0;
  end else begin
   if(completed)begin if(consumed || !owner_valid)completed<=0;end
   else if(!pending && selected && (read_en || write_en) && !access_bad && (load_hold || !cpu_reset))begin
    pending<=1;owner_loader<=load_hold;discard<=0;request_write<=write_en;
    request_address<=addr[26:2];request_data<=wdata<<(8*addr[1:0]);saved_funct3<=funct3;saved_lane<=addr[1:0];
    case(funct3[1:0])
     0:request_byte_enable<=4'b0001<<addr[1:0];
     1:request_byte_enable<=4'b0011<<addr[1:0];
     default:request_byte_enable<=4'b1111;
    endcase
   end
   if(pending && !owner_valid)begin
    discard<=1;
    if(!accepted)pending<=0;
   end
   if(pending && accepted && response_valid)begin
    pending<=0;
    if(owner_valid && !discard)begin
     shifted=response_data>>(8*saved_lane);
     case(saved_funct3)
      3'b000:rdata<={{24{shifted[7]}},shifted[7:0]};
      3'b001:rdata<={{16{shifted[15]}},shifted[15:0]};
      3'b100:rdata<={24'b0,shifted[7:0]};
      3'b101:rdata<={16'b0,shifted[15:0]};
      default:rdata<=response_data;
     endcase
     completed<=1;
    end
   end
  end
 end
endmodule
