// GW v1: ordered Q8 transform/outcode worker, CPU peripheral (falling-edge) clock.
// No memory master. CPU owns source reads and the returned render scratch buffer.
module geometry_worker(
    input logic clk,reset,
    input logic [31:0] addr,wdata,
    input logic [2:0] funct3,
    input logic read_en,write_en,
    output logic [31:0] rdata,
    output wire write_performed
);
    localparam ABI=32'h47570101;
    wire selected=addr[31:8]==24'h400001;
    wire aligned=funct3==3'b010 && addr[1:0]==0;
    wire [7:0] offset=addr[7:0];
    logic active,error;
    logic signed [15:0] matrix[0:11];
    logic signed [31:0] origin[0:2],reference_position[0:2];
    logic [31:0] descriptor_count,staged_xy;
    logic [7:0] expected,received,generated,consumed;
    logic [47:0] inputs[0:3];
    logic [101:0] results[0:3];
    logic [1:0] in_wr,in_rd,out_wr,out_rd;
    logic [2:0] in_count,out_count;
    typedef enum logic [2:0] {IDLE=3'd0,MULT=3'd1,ACC=3'd2,
        STORE=3'd3,FLAGS=3'd4,PUSH=3'd5} state_t;
    state_t state;
    logic [1:0] axis;
    logic signed [31:0] delta[0:2],product[0:2],sum[0:2],q[0:2];
    logic [5:0] code;
    logic [31:0] active_cycles,result_wait_cycles;
    wire config_address=(offset>=8'h10 && offset<=8'h3c) ||
        (offset>=8'h40 && offset<=8'h48) || (offset>=8'h50 && offset<=8'h58) || offset==8'h60;
    wire abort_request=selected && aligned && write_en && offset==8'h64 && wdata==2;
    wire start_request=selected && aligned && write_en && offset==8'h64 && wdata==1 &&
        !active && descriptor_count>=1 && descriptor_count<=128;
    wire configuration_write=selected && aligned && write_en && config_address && !active;
    wire xy_write=selected && aligned && write_en && offset==8'h70 && active && received<expected;
    wire input_push=selected && aligned && write_en && offset==8'h74 && active &&
        received<expected && in_count<4;
    wire input_pop=active && state==IDLE && in_count!=0;
    wire result_push=active && state==PUSH && out_count<4;
    wire result_pop=selected && aligned && read_en && offset==8'h8c && out_count!=0;
    assign write_performed=!reset && (abort_request || start_request || configuration_write || xy_write || input_push);
    wire known_read=config_address || offset==0 || offset==4 || offset==8 || offset==12 ||
        (offset>=8'h80 && offset<=8'h8c) || offset==8'h90 || offset==8'h94;
    wire result_read=offset>=8'h80 && offset<=8'h8c;
    // Low-32-bit products/sums match fixed_mul/MUL. Plane arithmetic also wraps
    // at the original 32-bit boundary; sign bit alone defines each outcode bit.
    function automatic [5:0] outcode(input logic signed[31:0] x,y,z);
        logic signed[31:0] p0,p1,p2,p3,p4,p5;
        begin
            p0=z-32'sd257;p1=32'sd30000-z;
            p2=(x<<<8)+(z<<<7)+(z<<<5);
            p3=-(x<<<8)+(z<<<7)+(z<<<5);
            p4=(y<<<8)+(z<<<7)-(z<<<3);
            p5=-(y<<<8)+(z<<<7)-(z<<<3);
            outcode={p5[31],p4[31],p3[31],p2[31],p1[31],p0[31]};
        end
    endfunction
    always_comb begin
        rdata=0;
        if(!reset && selected && aligned && read_en)begin
            if(offset>=8'h10 && offset<=8'h3c)rdata={{16{matrix[(offset-16)>>2][15]}},matrix[(offset-16)>>2]};
            else if(offset>=8'h40 && offset<=8'h48)rdata=reference_position[(offset-64)>>2];
            else if(offset>=8'h50 && offset<=8'h58)rdata=origin[(offset-80)>>2];
            else case(offset)
                8'h00:rdata=ABI;
                8'h04:rdata={16'd0,5'd0,out_count,1'b0,(3'd4-in_count),2'd0,error,active};
                8'h08:rdata={24'd0,received};
                8'h0c:rdata={24'd0,generated};
                8'h60:rdata=descriptor_count;
                8'h80:if(out_count!=0)rdata=results[out_rd][31:0];
                8'h84:if(out_count!=0)rdata=results[out_rd][63:32];
                8'h88:if(out_count!=0)rdata=results[out_rd][95:64];
                8'h8c:if(out_count!=0)rdata={26'd0,results[out_rd][101:96]};
                8'h90:rdata=active_cycles;
                8'h94:rdata=result_wait_cycles;
                default:begin end
            endcase
        end
    end
    integer i;
    always_ff @(posedge clk or posedge reset)begin
        if(reset)begin
            active<=0;error<=0;descriptor_count<=0;staged_xy<=0;
            expected<=0;received<=0;generated<=0;consumed<=0;
            in_count<=0;out_count<=0;in_wr<=0;in_rd<=0;out_wr<=0;out_rd<=0;
            state<=IDLE;axis<=0;code<=0;active_cycles<=0;result_wait_cycles<=0;
            for(i=0;i<12;i=i+1)matrix[i]<=0;
            for(i=0;i<3;i=i+1)begin origin[i]<=0;reference_position[i]<=0;delta[i]<=0;product[i]<=0;sum[i]<=0;q[i]<=0;end
        end else if(abort_request)begin
            active<=0;error<=0;expected<=0;received<=0;generated<=0;consumed<=0;
            in_count<=0;out_count<=0;in_wr<=0;in_rd<=0;out_wr<=0;out_rd<=0;
            state<=IDLE;active_cycles<=0;result_wait_cycles<=0;
        end else begin
            if(selected && ((write_en && !write_performed) ||
                (read_en && (!aligned || !known_read || (result_read && out_count==0)))))error<=1;
            if(configuration_write)begin
                if(offset>=8'h10 && offset<=8'h3c)matrix[(offset-16)>>2]<=wdata[15:0];
                else if(offset>=8'h40 && offset<=8'h48)reference_position[(offset-64)>>2]<=wdata;
                else if(offset>=8'h50 && offset<=8'h58)origin[(offset-80)>>2]<=wdata;
                else descriptor_count<=wdata;
            end
            if(start_request)begin
                active<=1;error<=0;expected<=descriptor_count[7:0];received<=0;generated<=0;consumed<=0;
                in_count<=0;out_count<=0;in_wr<=0;in_rd<=0;out_wr<=0;out_rd<=0;
                state<=IDLE;active_cycles<=0;result_wait_cycles<=0;
            end else begin
                if(active)active_cycles<=active_cycles+1'b1;
                if(active && state==PUSH && out_count==4)result_wait_cycles<=result_wait_cycles+1'b1;
                if(xy_write)staged_xy<=wdata;
                if(input_push)begin inputs[in_wr]<={wdata[15:0],staged_xy};in_wr<=in_wr+1'b1;received<=received+1'b1;end
                if(input_pop)in_rd<=in_rd+1'b1;
                case({input_push,input_pop})
                    2'b10:in_count<=in_count+1'b1;2'b01:in_count<=in_count-1'b1;default:begin end
                endcase
                if(result_push)begin
                    results[out_wr]<={code,q[2],q[1],q[0]};out_wr<=out_wr+1'b1;generated<=generated+1'b1;
                end
                if(result_pop)begin
                    out_rd<=out_rd+1'b1;consumed<=consumed+1'b1;
                    if(consumed==expected-1'b1)active<=0;
                end
                case({result_push,result_pop})
                    2'b10:out_count<=out_count+1'b1;2'b01:out_count<=out_count-1'b1;default:begin end
                endcase
                case(state)
                    IDLE:if(input_pop)begin
                        delta[0]<=($signed(inputs[in_rd][15:0])+origin[0]-reference_position[0])<<<2;
                        delta[1]<=($signed(inputs[in_rd][31:16])+origin[1]-reference_position[1])<<<2;
                        delta[2]<=($signed(inputs[in_rd][47:32])+origin[2]-reference_position[2])<<<2;
                        for(i=0;i<3;i=i+1)sum[i]<=0;
                        axis<=0;state<=MULT;
                    end
                    MULT:begin
                        for(i=0;i<3;i=i+1)product[i]<=delta[axis]*matrix[4*i+axis];
                        state<=ACC;
                    end
                    ACC:begin
                        for(i=0;i<3;i=i+1)sum[i]<=sum[i]+product[i];
                        if(axis==2)state<=STORE;else begin axis<=axis+1'b1;state<=MULT;end
                    end
                    STORE:begin
                        for(i=0;i<3;i=i+1)q[i]<=($signed(sum[i])>>>8)+$signed(matrix[4*i+3]);
                        state<=FLAGS;
                    end
                    FLAGS:begin code<=outcode(q[0],q[1],q[2]);state<=PUSH;end
                    PUSH:if(result_push)state<=IDLE;
                    default:state<=IDLE;
                endcase
            end
        end
    end
    // synthesis translate_off
    always @(posedge clk)if(!reset && (in_count>4 || out_count>4 || received>expected || generated>received || consumed>generated))
        $fatal(1,"geometry queue/descriptor invariant");
    // synthesis translate_on
endmodule
