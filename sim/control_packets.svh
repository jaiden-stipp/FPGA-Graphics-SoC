// Include inside a test module with rx_clk/rx_data/rx_dv/rx_er signals.
integer control_frame = 1;
function automatic [15:0] control_crc_byte(input [15:0] crc, input [7:0] data);
    reg [15:0] value;
    begin
        value = crc ^ (data << 8);
        for (integer b = 0; b < 8; b = b + 1)
            value = (value << 1) ^ (value[15] ? 16'h1021 : 16'b0);
        control_crc_byte = value;
    end
endfunction
task automatic control_byte(input [7:0] value);
    @(negedge rx_clk); rx_dv = 1; rx_data = value[3:0];
    @(negedge rx_clk); rx_data = value[7:4];
endtask
task automatic send_control(input [7:0] sequence_id, input [7:0] keys,
                            input bit bad_crc, input bit wrong_port);
    reg [7:0] bytes [0:68];
    reg [15:0] crc;
    reg [31:0] fcs;
    integer sum;
    begin
        for (integer i=0; i<69; i=i+1) bytes[i]=0;
        bytes[0]=2; bytes[5]=1; bytes[6]=16; bytes[7]=32;
        bytes[8]=48; bytes[9]=64; bytes[10]=80; bytes[11]=96;
        bytes[12]=8; bytes[14]=8'h45; bytes[17]=51; bytes[22]=64; bytes[23]=17;
        bytes[26]=192; bytes[27]=168; bytes[28]=7; bytes[29]=1;
        bytes[30]=192; bytes[31]=168; bytes[32]=7; bytes[33]=2;
        sum=0;
        for (integer i=14; i<34; i=i+2) sum=sum+{bytes[i],bytes[i+1]};
        sum=(sum & 65535)+(sum>>16); sum=(sum & 65535)+(sum>>16);
        bytes[24]=(~sum>>8); bytes[25]=~sum;
        bytes[34]=4; bytes[35]=210; bytes[36]=15; bytes[37]=wrong_port ? 161 : 160;
        bytes[39]=31;
        bytes[42]=71; bytes[43]=80; bytes[44]=2; bytes[45]=3;
        bytes[46]=control_frame>>24; bytes[47]=control_frame>>16;
        bytes[48]=control_frame>>8; bytes[49]=control_frame; bytes[53]=11;
        bytes[54]=71; bytes[55]=70; bytes[56]=2; bytes[57]=4; bytes[58]=4;
        bytes[59]=255; bytes[60]=75; bytes[61]=sequence_id; bytes[62]=keys;
        crc=16'hffff;
        for (integer i=54; i<63; i=i+1) crc=control_crc_byte(crc,bytes[i]);
        bytes[63]=crc>>8; bytes[64]=crc ^ bad_crc;
        fcs=32'hffffffff;
        for (integer i=0; i<65; i=i+1) begin
            fcs=fcs^bytes[i];
            for (integer b=0; b<8; b=b+1) fcs=(fcs>>1)^(fcs[0] ? 32'hedb88320 : 32'b0);
        end
        bytes[65]=~fcs; bytes[66]=~(fcs>>8); bytes[67]=~(fcs>>16); bytes[68]=~(fcs>>24);
        repeat (7) control_byte(8'h55);
        control_byte(8'hd5);
        for (integer i=0; i<69; i=i+1) control_byte(bytes[i]);
        @(negedge rx_clk); rx_dv=0;
        repeat (100) @(posedge rx_clk);
        control_frame=control_frame+1;
    end
endtask
