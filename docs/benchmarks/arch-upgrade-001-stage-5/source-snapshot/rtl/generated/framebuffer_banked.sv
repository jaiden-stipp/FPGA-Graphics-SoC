// Raster writes both parity banks; VGA reads one bank with registered parity.
module framebuffer_banked #(parameter int FRAME_WIDTH=320,FRAME_HEIGHT=240)(
    input logic reset,raster_clk,raster_write,input logic[9:0]raster_x,input logic[8:0]raster_y,
    input logic[7:0]raster_color,
    input logic raster_write1,input logic[9:0]raster_x1,input logic[8:0]raster_y1,input logic[7:0]raster_color1,
    input logic clear_request,output logic clear_busy,
    input logic display_clk,display_read_enable,input logic[9:0]display_x,input logic[8:0]display_y,
    output logic[7:0]display_pixel,output logic display_pixel_valid
);
    localparam WORDS=(FRAME_WIDTH/2)*FRAME_HEIGHT,AB=$clog2(WORDS);
    logic clear_active,parity;
    logic[AB-1:0]clear_address;
    wire[1:0]we={raster_write1,raster_write};
    wire[9:0]wx[0:1];wire[8:0]wy[0:1];wire[7:0]wc[0:1],q[0:1];
    assign wx[0]=raster_x;assign wx[1]=raster_x1;assign wy[0]=raster_y;assign wy[1]=raster_y1;
    assign wc[0]=raster_color;assign wc[1]=raster_color1;
    wire bounds=display_x<FRAME_WIDTH && display_y<FRAME_HEIGHT;
    wire[AB-1:0]ra=display_y*(FRAME_WIDTH/2)+(display_x>>1);
    assign clear_busy=clear_active;
    always_comb display_pixel=display_pixel_valid?q[parity]:8'd0;
    always_ff @(posedge display_clk or posedge reset)begin
        if(reset)begin parity<=0;display_pixel_valid<=0;end
        else begin parity<=display_x[0];display_pixel_valid<=display_read_enable && bounds;end
    end
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
        wire[AB-1:0]ram_write_address=clear_active?clear_address:wy[b]*(FRAME_WIDTH/2)+(wx[b]>>1);
        wire[7:0]ram_write_data=clear_active?8'd0:wc[b];
        wire ram_write_enable=!reset && (clear_active || (we[b] && wx[b]<FRAME_WIDTH && wy[b]<FRAME_HEIGHT && wx[b][0]==b && !clear_request));
        pixel_bank_ram #(.WORDS(WORDS)) memory(.write_clk(raster_clk),.read_clk(display_clk),
            .write_address(ram_write_address),.write_data(ram_write_data),.write_enable(ram_write_enable),
            .read_address(ra),.read_enable(display_read_enable && bounds && display_x[0]==b),.read_data(q[b]));
    end endgenerate
endmodule
