// Include after control_packets.svh: same real Ethernet/UDP/CRC path.
task automatic send_input(input [7:0] sequence_id,keys,yaw,pitch,input bit bad_crc);
    reg [7:0] bytes[0:88];reg [15:0] crc;reg [31:0] fcs;integer sum;
    begin
        for(integer i=0;i<89;i=i+1)bytes[i]=0;
        bytes[0]=2;bytes[5]=1;bytes[6]=16;bytes[7]=32;bytes[8]=48;bytes[9]=64;bytes[10]=80;bytes[11]=96;
        bytes[12]=8;bytes[14]=8'h45;bytes[17]=71;bytes[22]=64;bytes[23]=17;
        bytes[26]=192;bytes[27]=168;bytes[28]=7;bytes[29]=1;
        bytes[30]=192;bytes[31]=168;bytes[32]=7;bytes[33]=2;
        sum=0;for(integer i=14;i<34;i=i+2)sum=sum+{bytes[i],bytes[i+1]};
        sum=(sum&65535)+(sum>>16);sum=(sum&65535)+(sum>>16);
        bytes[24]=(~sum>>8);bytes[25]=~sum;
        bytes[34]=4;bytes[35]=210;bytes[36]=15;bytes[37]=160;bytes[39]=51;
        bytes[42]=71;bytes[43]=80;bytes[44]=2;bytes[45]=3;
        bytes[46]=control_frame>>24;bytes[47]=control_frame>>16;bytes[48]=control_frame>>8;bytes[49]=control_frame;
        bytes[53]=31;bytes[54]=71;bytes[55]=70;bytes[56]=2;bytes[57]=11;bytes[58]=24;
        bytes[59]=73;bytes[60]=78;bytes[61]=1;bytes[62]=sequence_id;
        bytes[63]=keys;bytes[64]=yaw;bytes[65]=pitch;
        crc=16'hffff;for(integer i=54;i<83;i=i+1)crc=control_crc_byte(crc,bytes[i]);
        bytes[83]=crc>>8;bytes[84]=crc^bad_crc;
        fcs=32'hffffffff;
        for(integer i=0;i<85;i=i+1)begin
            fcs=fcs^bytes[i];for(integer b=0;b<8;b=b+1)fcs=(fcs>>1)^(fcs[0]?32'hedb88320:32'b0);
        end
        bytes[85]=~fcs;bytes[86]=~(fcs>>8);bytes[87]=~(fcs>>16);bytes[88]=~(fcs>>24);
        repeat(7)control_byte(8'h55);control_byte(8'hd5);
        for(integer i=0;i<89;i=i+1)control_byte(bytes[i]);
        @(negedge rx_clk);rx_dv=0;repeat(100)@(posedge rx_clk);control_frame=control_frame+1;
    end
endtask
