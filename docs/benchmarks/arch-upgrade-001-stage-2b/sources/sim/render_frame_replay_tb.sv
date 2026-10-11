`timescale 1ns/1ps
`include "renderer_types.svh"
`define RP dut.renderer.pipeline
module render_frame_replay_tb #(parameter integer PACKED_INPUT=0, DMA_INPUT=0);
 logic clk=0,reset=1,valid=0,ready,de,ce,done;logic [7:0] data=0;logic [31:0] done_id;renderer_stats_t stats;
 always #10 clk=~clk;
 wire[7:0]stream_data;wire stream_valid,stream_ready;
 logic[31:0]mmio_addr=0,mmio_word=0;wire[31:0]mmio_read,mmio_scratch;
 logic mmio_re=0,mmio_we=0;wire mmio_written,mmio_pending;wire[3:0]mmio_errors;
 reg [7:0] bytes[0:1999999];
 generate if(DMA_INPUT)begin : dma_source
  wire busy,bvalid,accepted,mvalid,mready;wire[7:0]bdata,error;wire[24:0]maddr;
  wire[31:0]completed,sent,reads,request_wait,fifo_wait;logic start=0;
  logic[31:0]source=32'h80000000,amount=0,id=0,mdata=0;logic response=0;
  integer pending=0,base=0,beat=0,ticks=0;
  assign mready=pending==0;
  gfx_command_dma transfer(.clk(~clk),.reset(reset),.cancel(1'b0),.start(start),.source(source),.length(amount),.submission_id(id),
   .busy(busy),.error_code(error),.completed_id(completed),.bytes_sent(sent),.read_words(reads),.request_wait(request_wait),.fifo_wait(fifo_wait),
   .memory_valid(mvalid),.memory_address(maddr),.memory_ready(mready),.memory_response_valid(response),.memory_response_data(mdata),
   .byte_valid(bvalid),.byte_data(bdata),.byte_accepted(accepted));
  soc_mmio #(.DMA_SUPPORTED(1)) input_fifo(.clk(clk),.reset(reset),.addr(32'b0),.wdata(32'b0),.funct3(3'b010),
   .read_en(1'b0),.write_en(1'b0),.rdata(),.write_performed(),.byte_data(stream_data),.byte_valid(stream_valid),.byte_ready(stream_ready),
   .decoder_error(de),.command_error(ce),.frame_done(done),.frame_done_id(done_id),.frame_statistics(stats),.buttons(8'b0),
   .frame_pending(),.error_flags(mmio_errors),.scratch(),.dma_busy(busy),.dma_byte_valid(bvalid),.dma_byte_data(bdata),.dma_byte_accepted(accepted),
   .dma_error_code(error),.dma_completed_id(completed),.dma_bytes_sent(sent),.dma_read_words(reads),.dma_request_wait(request_wait),.dma_fifo_wait(fifo_wait),
   .dma_start(),.dma_source(),.dma_length(),.dma_submission_id());
  // Deterministic variable burst latency; data comes from the exact saved wire.
  always @(negedge clk)begin
   response<=0;ticks=ticks+1;
   if(!reset && mvalid && mready)begin pending=1;base=maddr*4;beat=0;end
   else if(pending && ticks%3!=0)begin
    mdata<= {bytes[base+beat*4+3],bytes[base+beat*4+2],bytes[base+beat*4+1],bytes[base+beat*4]};response<=1;
    if(beat==7)pending=0;else beat=beat+1;
   end
  end
  always @(posedge clk)if(!reset && (error || mmio_errors))$fatal(1,"DMA replay error");
 end else if(PACKED_INPUT)begin : packed_source
  soc_mmio input_fifo(.clk(clk),.reset(reset),.addr(mmio_addr),.wdata(mmio_word),.funct3(3'b010),
   .read_en(mmio_re),.write_en(mmio_we),.rdata(mmio_read),.write_performed(mmio_written),
   .byte_data(stream_data),.byte_valid(stream_valid),.byte_ready(stream_ready),.decoder_error(de),.command_error(ce),
   .frame_done(done),.frame_done_id(done_id),.frame_statistics(stats),.buttons(8'b0),.look_state(24'b0),
   .cache_statistics(192'b0),.cpu_statistics(160'b0),.frame_pending(mmio_pending),.error_flags(mmio_errors),.scratch(mmio_scratch));
  always @(posedge clk)if(!reset && |mmio_errors)$fatal(1,"packed replay MMIO error");
 end else begin
  assign stream_data=data;assign stream_valid=valid;
 end endgenerate
 assign ready=stream_ready;
 graphics_stream_renderer dut(.clk(clk),.reference_clk(clk),.reset(reset),.restart(1'b0),.byte_data(stream_data),.byte_valid(stream_valid),.byte_ready(stream_ready),
 .decoder_error(de),.command_error(ce),.frame_done(done),.frame_done_id(done_id),.frame_statistics(stats),
 .VGA_R(),.VGA_G(),.VGA_B(),.VGA_CLK(),.VGA_BLANK_N(),.VGA_SYNC_N(),.VGA_HS(),.VGA_VS());
 reg [7:0] page0[0:76799],page1[0:76799],depth[0:76799];reg[23:0] palette[0:255];
 integer cycle=0,frame=0,captured=0,expected,length,fd,commands,triangles,timeline,first_byte,last_byte,last_setup,last_raster;
 integer occupancy=0,max_occupancy=0,queue_empty=0,queue_full=0,geometry_stalls=0;
 integer previous_raster_state=0;
 always @(posedge clk)begin
  cycle=cycle+1;
  if(!reset)begin
   if(de || ce)$fatal(1,"replay decoder/command error");
   if(stream_valid && stream_ready)begin if(first_byte<0)first_byte=cycle;last_byte=cycle;end
   if(`RP.display.framebuffer0.ram_write_enable)page0[`RP.display.framebuffer0.ram_write_address]=`RP.display.framebuffer0.ram_write_data;
   if(`RP.display.framebuffer1.ram_write_enable)page1[`RP.display.framebuffer1.ram_write_address]=`RP.display.framebuffer1.ram_write_data;
   if(`RP.depth_memory.ram_write_enable)depth[`RP.depth_memory.ram_write_address]=`RP.depth_memory.ram_write_depth;
   if(`RP.palette_write)palette[`RP.palette_address]=`RP.palette_write_rgb;
   if(dut.command_valid && dut.command_ready)begin
    $fdisplay(commands,"%0d %0d %h %h",cycle,frame,dut.command_data.opcode,dut.command_data.payload);
    if(dut.command_data.opcode==GFX_CMD_BEGIN_FRAME)begin
     frame=`GFX_ARGUMENT(dut.command_data);first_byte=-1;last_byte=-1;last_setup=-1;last_raster=-1;
     occupancy=0;max_occupancy=0;queue_empty=0;queue_full=0;geometry_stalls=0;
     $fdisplay(timeline,"%0d begin %0d",frame,cycle);
    end
   end
   if(`RP.triangle_in_valid && `RP.triangle_in_ready) $fdisplay(triangles,"%0d %h",frame,`RP.triangle_in_data);
   case ({`RP.triangle_in_valid && `RP.triangle_in_ready,`RP.transform_in_valid && `RP.transform_in_ready && !`RP.clear_request && !`RP.clear_busy && !`RP.swap_busy})
    2'b10:occupancy=occupancy+1;2'b01:occupancy=occupancy-1;default:begin end
   endcase
   if(occupancy>max_occupancy)max_occupancy=occupancy;
   if(`RP.triangle_fifo_empty)queue_empty=queue_empty+1;
   if(`RP.triangle_fifo_full)queue_full=queue_full+1;
   if(`RP.transform_out_valid && !`RP.transform_out_ready)geometry_stalls=geometry_stalls+1;
   if(`RP.rasterizer.state==6 && previous_raster_state!=6)last_setup=cycle;
   previous_raster_state=`RP.rasterizer.state;
   if(`RP.raster_write)last_raster=cycle;
   if(`RP.swap_request)$fdisplay(timeline,"%0d swap_request %0d first_byte=%0d last_byte=%0d last_setup=%0d last_raster=%0d max_queue=%0d empty=%0d full=%0d geometry_stall=%0d",frame,cycle,first_byte,last_byte,last_setup,last_raster,max_occupancy,queue_empty,queue_full,geometry_stalls);
   if(done)begin
    if(done_id!=captured+1)$fatal(1,"out of order frame completion");
    $fdisplay(timeline,"%0d swap_ack %0d stats=%h",done_id,cycle,stats);
    fd=$fopen($sformatf("build/render-replay/frame-%0d.color.hex",done_id),"w");
    for(integer i=0;i<76800;i++)$fdisplay(fd,"%02h",`RP.display.front_page_pixel ? page1[i] : page0[i]);$fclose(fd);
    fd=$fopen($sformatf("build/render-replay/frame-%0d.depth.hex",done_id),"w");
    for(integer i=0;i<76800;i++)$fdisplay(fd,"%02h",depth[i]);$fclose(fd);
    fd=$fopen($sformatf("build/render-replay/frame-%0d.palette.hex",done_id),"w");
    for(integer i=0;i<256;i++)$fdisplay(fd,"%06h",palette[i]);$fclose(fd);
    captured=captured+1;$display("REPLAY frame=%0d cycle=%0d",done_id,cycle);
   end
  end
 end
 initial begin
  first_byte=-1;last_byte=-1;for(integer i=0;i<76800;i++)begin page0[i]=0;page1[i]=0;depth[i]=0;end
  for(integer i=0;i<256;i++)palette[i]=0;
  fd=$fopen("build/render-replay/input.meta","r");if(!fd)$fatal(1,"missing replay input");
  if($fscanf(fd,"%d %d",length,expected)!=2 || length>2000000 || length<=0 || expected<=0)$fatal(1,"invalid replay input");$fclose(fd);
  $readmemh("build/render-replay/input.hex",bytes,0,length-1);
  commands=$fopen("build/render-replay/frame-commands.log","w");triangles=$fopen("build/render-replay/frame-triangles.log","w");timeline=$fopen("build/render-replay/frame-timeline.log","w");
  repeat(12)@(negedge clk);reset=0;repeat(12)@(negedge clk);
  if(DMA_INPUT)begin
   for(integer i=0;i<length;i=i+1024)begin
    @(posedge clk);#1;dma_source.source=32'h80000000+i;dma_source.amount=length-i<1024?length-i:1024;dma_source.id=dma_source.id+1;dma_source.start=1;
    @(negedge clk);@(posedge clk);#1;dma_source.start=0;
    wait(dma_source.busy);wait(!dma_source.busy);
    if(dma_source.completed!=dma_source.id)$fatal(1,"DMA replay completion mismatch");
   end
  end else if(PACKED_INPUT)begin
   for(integer i=0;i<length;i=i+4)begin
    integer n;n=length-i<4?length-i:4;
    @(negedge clk);mmio_addr=32'h40000008;mmio_re=1;
    #1;while(mmio_read<n)begin @(negedge clk);#1;end
    mmio_re=0;mmio_addr=32'h400000ac+4*n;mmio_word=0;
    for(integer j=0;j<n;j=j+1)mmio_word=mmio_word|({24'b0,bytes[i+j]}<<(8*j));
    mmio_we=1;#1;if(!mmio_written)$fatal(1,"packed reservation lost");
    @(posedge clk);@(negedge clk);mmio_we=0;
   end
  end else for(integer i=0;i<length;i++)begin
   // Deterministic producer gaps exercise ready/valid backpressure.
   if(i%17==0)begin valid=0;repeat(2)@(negedge clk);end
   data=bytes[i];valid=1;do @(posedge clk);while(!ready);@(negedge clk);valid=0;
  end
  wait(captured==expected);@(negedge clk);$fclose(commands);$fclose(triangles);$fclose(timeline);
  if(DMA_INPUT)$display("PASS dma_render_replay_tb");else if(PACKED_INPUT)$display("PASS packed_render_replay_tb");else $display("PASS render_frame_replay_tb");$finish;
 end
 initial begin #1000000000;$fatal(1,"render replay timeout");end
endmodule
