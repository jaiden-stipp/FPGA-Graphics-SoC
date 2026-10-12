`timescale 1ns/1ps
module geometry_worker_tb;
    logic clk=0,reset=1,rd=0,wr=0;
    always #10 clk=~clk;
    logic [31:0]addr=32'h40000100,wdata=0;
    logic[2:0]funct3=2;
    wire[31:0]rdata;wire performed;
    geometry_worker dut(.clk(clk),.reset(reset),.addr(addr),.wdata(wdata),.funct3(funct3),
        .read_en(rd),.write_en(wr),.rdata(rdata),.write_performed(performed));
    reg[31:0]config_words[0:189],input_words[0:4999],expected_words[0:9999];
    integer descriptors,total,fd,base=0,count,pushed,done;
    logic[31:0]value,status;
    task write_reg(input integer off,input logic[31:0]data,input bit accept=1);
        @(negedge clk);addr=32'h40000100+off;wdata=data;wr=1;
        #1;if(performed!==accept)$fatal(1,"write ownership/credit off=%h expected=%0d",off,accept);
        @(negedge clk);wr=0;
    endtask
    task read_reg(input integer off,output logic[31:0]data);
        @(negedge clk);addr=32'h40000100+off;rd=1;
        @(posedge clk);#1;data=rdata;
        @(negedge clk);rd=0;
    endtask
    task input_vertex(input integer index);
        write_reg('h70,input_words[index*2]);write_reg('h74,input_words[index*2+1]);
    endtask
    task configure(input integer desc);
        for(integer i=0;i<12;i++)write_reg('h10+4*i,config_words[19*desc+i]);
        for(integer i=0;i<3;i++)write_reg('h40+4*i,config_words[19*desc+12+i]);
        for(integer i=0;i<3;i++)write_reg('h50+4*i,config_words[19*desc+15+i]);
        write_reg('h60,config_words[19*desc+18]);
    endtask
    initial begin
        fd=$fopen("build/arch-stage5/vector.meta","r");if(!fd)$fatal(1,"missing vectors");
        if($fscanf(fd,"%d %d",descriptors,total)!=2)$fatal(1,"bad metadata");$fclose(fd);
        $readmemh("build/arch-stage5/vector-config.hex",config_words,0,descriptors*19-1);
        $readmemh("build/arch-stage5/vector-input.hex",input_words,0,total*2-1);
        $readmemh("build/arch-stage5/vector-expected.hex",expected_words,0,total*4-1);
        repeat(4)@(negedge clk);reset=0;
        read_reg(0,value);if(value!==32'h47570101)$fatal(1,"ABI");
        write_reg('h60,129);write_reg('h64,1,0);
        read_reg(4,value);if(value[0] || !value[1])$fatal(1,"invalid descriptor accepted");
        write_reg('h64,2);
        // Reject config mutation while active; reset with queued/unfinished data.
        configure(2);write_reg('h64,1);input_vertex(0);
        write_reg('h40,32'hdeadbeef,0);
        read_reg('h40,value);if(value!==0)$fatal(1,"active config changed");
        repeat(20)@(negedge clk);
        reset=1;repeat(4)@(negedge clk);reset=0;
        read_reg(4,value);if(value[1:0]!=0 || value[15:8]!=0)$fatal(1,"stale reset result");
        for(integer d=0;d<descriptors;d++)begin
            configure(d);count=config_words[19*d+18];write_reg('h64,1);pushed=0;done=0;
            // Fill both queues and block the producer before consuming results.
            while(pushed<count && pushed<9)begin
                read_reg(4,status);
                if(status[6:4]!=0)begin input_vertex(base+pushed);pushed++;end
            end
            repeat(40)@(negedge clk);
            while(done<count)begin
                read_reg(4,status);
                if(status[1])$fatal(1,"unexpected worker error");
                if(status[15:8]!=0)begin
                    for(integer j=0;j<4;j++)begin
                        read_reg('h80+j*4,value);
                        if(value!==expected_words[(base+done)*4+j])$fatal(1,"oracle mismatch vertex=%0d component=%0d got=%h expected=%h",base+done,j,value,expected_words[(base+done)*4+j]);
                    end
                    done++;
                end
                if(pushed<count)begin
                    read_reg(4,status);
                    if(status[6:4]!=0)begin input_vertex(base+pushed);pushed++;end
                end
            end
            read_reg(4,value);if(value[1:0]!=0 || value[15:8]!=0)$fatal(1,"descriptor did not drain");
            read_reg(8,value);if(value!=count)$fatal(1,"input count");
            read_reg(12,value);if(value!=count)$fatal(1,"result count");
            read_reg('h94,value);if(count>9 && value==0)$fatal(1,"output backpressure not exercised");
            base+=count;
        end
        // Abort with results available must prevent a stale read/new descriptor.
        configure(2);write_reg('h64,1);input_vertex(0);repeat(30)@(negedge clk);
        write_reg('h64,2);read_reg(4,value);if(value[1:0] || value[15:8])$fatal(1,"abort left results");
        $display("PASS geometry_worker_tb vertices=%0d descriptors=%0d",total,descriptors);$finish;
    end
    initial begin #10000000;$fatal(1,"geometry worker timeout");end
endmodule
