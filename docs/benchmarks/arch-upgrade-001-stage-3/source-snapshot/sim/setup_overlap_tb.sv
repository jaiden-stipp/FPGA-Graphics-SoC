`timescale 1ns/1ps
`include "renderer_types.svh"
// Independent memory and ordered write traces compare both hardware variants.
module setup_overlap_tb;
    localparam W=64,H=48,N=180;
    logic clk=0,reset=1;
    always #10 clk=~clk;
    triangle_data_t triangles[0:N-1];
    logic [1:0] ready,busy,valid,read_enable,read_valid=0,write_enable;
    triangle_data_t data[0:1];
    wire [9:0] rx[0:1],wx[0:1];wire[8:0]ry[0:1],wy[0:1];
    wire[7:0]wc[0:1],wz[0:1];logic[7:0]rz[0:1];
    reg[7:0]colors[0:1][0:W*H-1],depth[0:1][0:W*H-1];
    reg[34:0]trace[0:1][0:199999];
    integer index[0:1],writes[0:1],finished[0:1],cycle=0;
    integer phase=0,seed=32'h34567812;
    function automatic integer random_value(input integer limit);
        seed=seed*1664525+1013904223;
        return (32'(seed)>>16)%limit;
    endfunction
    generate for(genvar g=0;g<2;g++)begin:variants
        renderer #(.FRAME_WIDTH(W),.FRAME_HEIGHT(H),.SETUP_OVERLAP(g)) dut(
            .clk(clk),.reset(reset),.triangle_data(data[g]),.triangle_valid(valid[g]),.triangle_ready(ready[g]),
            .raster_write(write_enable[g]),.raster_x(wx[g]),.raster_y(wy[g]),.raster_color(wc[g]),
            .depth_read_enable(read_enable[g]),.depth_read_x(rx[g]),.depth_read_y(ry[g]),
            .depth_read_value(rz[g]),.depth_read_valid(read_valid[g]),.depth_write_enable(),
            .depth_write_x(),.depth_write_y(),.depth_write_value(wz[g]),.busy(busy[g]),
            .bounding_box_pixel(),.pixel_inside(),.depth_rejected(),.pixel_written());
        always @(posedge clk)begin
            if(reset)begin read_valid[g]<=0;rz[g]<=0; end
            else begin
                read_valid[g]<=read_enable[g];
                if(read_enable[g])rz[g]<=depth[g][ry[g]*W+rx[g]];
                if(write_enable[g])begin
                    if(wx[g]>=W || wy[g]>=H)$fatal(1,"out of viewport write");
                    colors[g][wy[g]*W+wx[g]]=wc[g];depth[g][wy[g]*W+wx[g]]=wz[g];
                    trace[g][writes[g]]={wx[g],wy[g],wc[g],wz[g]};writes[g]++;
                end
                if(valid[g] && ready[g])index[g]++;
            end
        end
    end endgenerate
    always @(negedge clk)begin
        cycle++;
        for(integer g=0;g<2;g++)begin
            valid[g]=!reset && index[g]<N && (phase==0 || cycle%7!=0);
            data[g]=index[g]<N?triangles[index[g]]:'0;
            if(!reset && index[g]==N && !busy[g] && finished[g]==0)finished[g]=cycle;
        end
    end
    task clear_test;
        @(negedge clk);reset=1;repeat(4)@(negedge clk);
        for(integer g=0;g<2;g++)begin
            index[g]=0;writes[g]=0;finished[g]=0;
            for(integer p=0;p<W*H;p++)begin colors[g][p]=0;depth[g][p]=0;end
        end
        @(negedge clk);reset=0;
    endtask
    task compare;
        wait(finished[0]!=0 && finished[1]!=0);@(negedge clk);
        if(writes[0]!=writes[1])$fatal(1,"write count mismatch %0d/%0d",writes[0],writes[1]);
        for(integer p=0;p<writes[0];p++)if(trace[0][p]!==trace[1][p])$fatal(1,"ordered write mismatch %0d",p);
        for(integer p=0;p<W*H;p++)if(colors[0][p]!==colors[1][p] || depth[0][p]!==depth[1][p])$fatal(1,"frame/depth mismatch %0d",p);
        $display("SETUP_CASE phase=%0d serial_end=%0d overlap_end=%0d writes=%0d max_queue=%0d setup_blocked=%0d raster_wait=%0d overlap=%0d accepted=%0d retired=%0d",
            phase,finished[0],finished[1],writes[0],variants[1].dut.overlap.core.max_queue,
            variants[1].dut.overlap.core.setup_blocked_cycles,variants[1].dut.overlap.core.raster_wait_cycles,
            variants[1].dut.overlap.core.overlap_cycles,variants[1].dut.overlap.core.accepted,variants[1].dut.overlap.core.retired);
        if(phase==0 && finished[1]>=finished[0])$fatal(1,"saturated fixture failed to reduce elapsed cycles");
    endtask
    initial begin
        valid=0;
        for(integer i=0;i<N;i++)begin
            triangles[i]='0;
            if(i<4)begin
                triangles[i].x0=0;triangles[i].y0=0;
                triangles[i].x1=W-1;triangles[i].y1=0;
                triangles[i].x2=0;triangles[i].y2=H-1;
            end else begin
                triangles[i].x0=(i*7)%W;triangles[i].y0=(i*3)%H;
                triangles[i].x1=triangles[i].x0+2;triangles[i].y1=triangles[i].y0;
                triangles[i].x2=triangles[i].x0;triangles[i].y2=triangles[i].y0+2;
            end
            triangles[i].z0=80;triangles[i].z1=80;triangles[i].z2=80;
            triangles[i].color=i+1;
        end
        clear_test();compare();
        phase=1;
        for(integer i=0;i<N;i++)begin
            triangles[i].x0=random_value(90);triangles[i].y0=random_value(70);
            triangles[i].x1=random_value(90);triangles[i].y1=random_value(70);
            triangles[i].x2=random_value(90);triangles[i].y2=random_value(70);
            triangles[i].z0=random_value(256);triangles[i].z1=random_value(256);triangles[i].z2=random_value(256);
            if(i%11==0)begin triangles[i].x1=triangles[i].x0;triangles[i].y1=triangles[i].y0;end
        end
        triangles[0].x0=0;triangles[0].y0=0;triangles[0].x1=W-1;
        triangles[0].y1=0;triangles[0].x2=0;triangles[0].y2=H-1;
        clear_test();
        // Reset with queued records, setup backpressure and active raster work.
        $display("RESET_FIXTURE waiting for full queue");
        wait(variants[1].dut.overlap.core.count==2);
        $display("RESET_FIXTURE full queue observed");
        clear_test();compare();
        if(variants[1].dut.overlap.core.max_queue!=2)$fatal(1,"full queue not covered");
        $display("PASS setup_overlap_tb");$finish;
    end
    initial begin #50000000;$display("TIMEOUT indexes=%0d/%0d finished=%0d/%0d state=%0d count=%0d setup_state=%0d triangle=%h",index[0],index[1],finished[0],finished[1],variants[1].dut.overlap.core.state,variants[1].dut.overlap.core.count,variants[1].dut.overlap.core.setup_engine.state,triangles[0]);$fatal(1,"setup overlap timeout");end
endmodule
