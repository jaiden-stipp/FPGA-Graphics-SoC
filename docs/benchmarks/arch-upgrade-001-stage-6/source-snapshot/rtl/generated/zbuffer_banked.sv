// Each lane owns its X parity. Explicit same-edge forwarding avoids DONT_CARE.
module zbuffer_banked #(parameter int FRAME_WIDTH=320,FRAME_HEIGHT=240)(
    input logic reset,raster_clk,clear_request,output logic clear_busy,
    input logic read_enable, input logic [9:0] read_x,input logic [8:0] read_y,
    output wire [7:0] read_depth,output logic read_valid,
    input logic write_enable,input logic [9:0] write_x,input logic [8:0] write_y,
    input logic [7:0] write_depth,
    input logic read_enable1,input logic [9:0] read_x1,input logic [8:0] read_y1,
    output wire [7:0] read_depth1,output logic read_valid1,
    input logic write_enable1,input logic [9:0] write_x1,input logic [8:0] write_y1,
    input logic [7:0] write_depth1
);
    localparam WORDS=(FRAME_WIDTH/2)*FRAME_HEIGHT,AB=$clog2(WORDS);
    logic clear_active;
    logic [AB-1:0] clear_address;
    wire [1:0] re={read_enable1,read_enable},we={write_enable1,write_enable};
    wire [9:0] rx[0:1],wx[0:1];wire[8:0]ry[0:1],wy[0:1];wire[7:0]wz[0:1];
    assign rx[0]=read_x;assign rx[1]=read_x1;assign ry[0]=read_y;assign ry[1]=read_y1;
    assign wx[0]=write_x;assign wx[1]=write_x1;assign wy[0]=write_y;assign wy[1]=write_y1;
    assign wz[0]=write_depth;assign wz[1]=write_depth1;
    wire [1:0] valid;
    wire [7:0] result[0:1];
    assign read_depth=result[0];assign read_depth1=result[1];
    always_comb begin read_valid=valid[0];read_valid1=valid[1];clear_busy=clear_active;end
    always_ff @(posedge raster_clk or posedge reset)begin
        if(reset)begin clear_active<=0;clear_address<=0;end
        else if(!clear_active && clear_request)begin clear_active<=1;clear_address<=0;end
        else if(clear_active)begin
            if(clear_address==WORDS-1)begin clear_active<=0;clear_address<=0;end
            else clear_address<=clear_address+1'b1;
        end
    end
    genvar b;
    generate for(b=0;b<2;b=b+1)begin:banks
        wire [AB-1:0] ra=ry[b]*(FRAME_WIDTH/2)+(rx[b]>>1);
        wire [AB-1:0] ram_write_address=clear_active?clear_address:wy[b]*(FRAME_WIDTH/2)+(wx[b]>>1);
        wire [7:0] ram_write_depth=clear_active?8'd0:wz[b];
        wire ram_write_enable=!reset && (clear_active || (we[b] && wx[b]<FRAME_WIDTH && wy[b]<FRAME_HEIGHT && wx[b][0]==b && !clear_request));
        wire ren=re[b] && rx[b]<FRAME_WIDTH && ry[b]<FRAME_HEIGHT && rx[b][0]==b && !clear_active && !clear_request && !reset;
        wire [7:0] q;
        logic forwarding,rv;
        logic [7:0] forwarded_depth;
        pixel_bank_ram #(.WORDS(WORDS)) memory(.write_clk(raster_clk),.read_clk(raster_clk),
            .write_address(ram_write_address),.write_data(ram_write_depth),.write_enable(ram_write_enable),
            .read_address(ra),.read_enable(ren),.read_data(q));
        assign valid[b]=rv;assign result[b]=forwarding?forwarded_depth:q;
        always_ff @(posedge raster_clk or posedge reset)begin
            if(reset)begin rv<=0;forwarding<=0;forwarded_depth<=0;end
            else begin
                rv<=ren;forwarding<=ren && ram_write_enable && ra==ram_write_address;
                if(ren && ram_write_enable && ra==ram_write_address)forwarded_depth<=ram_write_depth;
            end
        end
    end endgenerate
endmodule
