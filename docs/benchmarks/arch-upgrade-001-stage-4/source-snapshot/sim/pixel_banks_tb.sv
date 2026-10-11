`timescale 1ns/1ps
// Real altera_mf RAM, unrelated display clock, parity selection and RAW bypass.
module pixel_banks_tb;
    localparam W=8,H=4;
    logic clk=0,pclk=0,reset=1,clear=0;
    always #10 clk=~clk;
    always #17 pclk=~pclk;
    wire cb,zb;
    logic we=0,we1=0,re=0,re1=0;
    logic[9:0]wx=0,wx1=1,rx=0,rx1=1,dx=0;
    logic[8:0]wy=0,wy1=0,ry=0,ry1=0,dy=0;
    logic[7:0]wd=0,wd1=0;
    wire[7:0]rd,rd1,pixel;wire rv,rv1,pvalid;
    logic den=0;
    zbuffer_banked #(.FRAME_WIDTH(W),.FRAME_HEIGHT(H)) depth(
        .reset(reset),.raster_clk(clk),.clear_request(clear),.clear_busy(zb),
        .write_enable(we),.write_x(wx),.write_y(wy),.write_depth(wd),
        .write_enable1(we1),.write_x1(wx1),.write_y1(wy1),.write_depth1(wd1),
        .read_enable(re),.read_x(rx),.read_y(ry),.read_depth(rd),.read_valid(rv),
        .read_enable1(re1),.read_x1(rx1),.read_y1(ry1),.read_depth1(rd1),.read_valid1(rv1));
    framebuffer_banked #(.FRAME_WIDTH(W),.FRAME_HEIGHT(H)) color(
        .reset(reset),.raster_clk(clk),.raster_write(we),.raster_x(wx),.raster_y(wy),.raster_color(wd),
        .raster_write1(we1),.raster_x1(wx1),.raster_y1(wy1),.raster_color1(wd1),
        .clear_request(clear),.clear_busy(cb),.display_clk(pclk),.display_read_enable(den),
        .display_x(dx),.display_y(dy),.display_pixel(pixel),.display_pixel_valid(pvalid));
    task clear_banks;
        integer cycles;
        @(negedge clk);clear=1;
        @(negedge clk);clear=0;
        cycles=0;
        while(cb || zb)begin cycles++;@(negedge clk);end
        if(cycles!=W*H/2)$fatal(1,"clear duration %0d",cycles);
    endtask
    task scan(input bit cleared);
        for(integer y=0;y<H;y++)for(integer x=0;x<W;x++)begin
            @(negedge pclk);den=1;dx=x;dy=y;
            @(posedge pclk);#1;
            if(!pvalid || pixel!==(cleared?8'd0:8'(y*W+x+1)))
                $fatal(1,"display parity/latency x=%0d y=%0d pixel=%h",x,y,pixel);
        end
        @(negedge pclk);den=0;
        @(posedge pclk);#1;if(pvalid || pixel!==0)$fatal(1,"display validity");
    endtask
    initial begin
        repeat(4)@(negedge clk);reset=0;clear_banks();scan(1);
        for(integer y=0;y<H;y++)for(integer x=0;x<W;x+=2)begin
            @(negedge clk);we=1;we1=1;wx=x;wx1=x+1;wy=y;wy1=y;
            wd=y*W+x+1;wd1=y*W+x+2;
            // Same-edge read/write requires forwarding, independent of RAM q.
            re=1;re1=1;rx=x;rx1=x+1;ry=y;ry1=y;
            @(posedge clk);#1;
            if(!rv || !rv1 || rd!==wd || rd1!==wd1)$fatal(1,"RAW forwarding");
        end
        @(negedge clk);we=0;we1=0;re=0;re1=0;
        scan(0);
        // Read stored depths without concurrent writes; exercise RAM, not bypass.
        for(integer y=0;y<H;y++)for(integer x=0;x<W;x+=2)begin
            @(negedge clk);re=1;re1=1;rx=x;rx1=x+1;ry=y;ry1=y;
            @(posedge clk);#1;
            if(!rv || !rv1 || rd!==8'(y*W+x+1) || rd1!==8'(y*W+x+2))$fatal(1,"stored depth mismatch");
        end
        @(negedge clk);re=0;re1=0;
        // Wrong parity and out-of-bounds requests cannot reach a bank.
        @(negedge clk);re=1;re1=1;rx=1;rx1=W+1;
        @(posedge clk);#1;if(rv || rv1)$fatal(1,"invalid read accepted");
        @(negedge clk);re=0;re1=0;
        // Clear owns both banks even when conflicting writes are asserted.
        we=1;we1=1;wd=255;wd1=255;clear_banks();we=0;we1=0;
        scan(1);
        @(negedge clk);re=1;re1=1;reset=1;
        #1;if(rv || rv1)$fatal(1,"reset did not invalidate reads");
        repeat(3)@(negedge clk);reset=0;re=0;re1=0;
        clear_banks();scan(1);
        $display("PASS pixel_banks_tb");$finish;
    end
    initial begin #100000;$fatal(1,"bank test timeout");end
endmodule
