// DE2-115: two x16 SDR SDRAMs as a 32Mx32 bank, 50 MHz, CL3.
// Burst mode uses sequential BL8 reads and single-location writes (M9=1).
// Single-word readers receive only the first word, after the burst drains.
// Closed-page access. All command/data outputs precede DRAM_CLK by 10 ns.
module sdram_controller #(
    parameter logic [13:0] POWERUP_CYCLES = 14'd10000,
    parameter integer REFRESH_CYCLES = 375,
    parameter ENABLE_BURST = 1
)(
    input logic clk, reset,
    input logic request_valid, request_write,
    input tri0 request_burst,
    input logic [24:0] request_address,
    input logic [31:0] request_data,
    input logic [3:0] request_byte_enable,
    output logic request_ready, response_valid, initialized,
    output logic [31:0] response_data,
    output logic [31:0] refresh_count,
    output wire DRAM_CLK,
    output logic DRAM_CKE, DRAM_CS_N, DRAM_RAS_N, DRAM_CAS_N, DRAM_WE_N,
    output logic [12:0] DRAM_ADDR,
    output logic [1:0] DRAM_BA,
    output logic [3:0] DRAM_DQM,
    inout wire [31:0] DRAM_DQ
);
    typedef enum logic [3:0] {POWERUP, INIT_PRE, INIT_REF, INIT_MODE,
        IDLE, ACCESS, READ_WAIT, READ_STREAM, RECOVER, REF_WAIT} state_t;
    state_t state;
    logic [13:0] timer;
    logic [8:0] refresh_age;
    logic [3:0] init_refreshes;
    logic [24:0] address;
    logic [31:0] data, dq_out;
    // Unconditional sampling permits the fitter to use fast input registers.
    // Forward the CL3 sample one cycle later; never clock-enable the I/O flops.
    logic [31:0] dq_sample;
    wire capture_clk;
    logic capture_locked;
    sdram_capture_clock read_clock(.inclk0(clk),.areset(reset),.c0(capture_clk),.locked(capture_locked));
    always_ff @(posedge capture_clk) dq_sample <= DRAM_DQ;
    logic [3:0] byte_enable;
    logic write_access, dq_drive;
    logic burst_access;
    logic [2:0] read_beat;
    // Reserve the additional burst drain clocks before starting another access.
    localparam integer REFRESH_LIMIT = REFRESH_CYCLES - (ENABLE_BURST ? 8 : 0);
    assign DRAM_CLK = ~clk;
    assign DRAM_DQ = dq_drive ? dq_out : 32'bz;
    assign request_ready = state == IDLE && initialized && refresh_age < REFRESH_LIMIT;
    always_ff @(posedge clk) begin
        if (reset || !capture_locked) begin
            state <= POWERUP; timer <= POWERUP_CYCLES-14'd1;
            initialized <= 0; refresh_age <= 0; refresh_count <= 0;
            response_valid <= 0; response_data <= 0; init_refreshes <= 0;
            {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0111;
            DRAM_CKE <= 1; DRAM_ADDR <= 0; DRAM_BA <= 0;
            DRAM_DQM <= 4'b1111; dq_drive <= 0; dq_out <= 0;
            address <= 0; data <= 0; byte_enable <= 0; write_access <= 0;
            burst_access <= 0; read_beat <= 0;
        end else begin
            {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0111;
            DRAM_DQM <= 0; dq_drive <= 0; response_valid <= 0;
            if (initialized && refresh_age < REFRESH_CYCLES+20) refresh_age <= refresh_age+1'b1;
            case (state)
                POWERUP: if (timer != 0) timer <= timer-1'b1; else begin
                    {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0010;
                    DRAM_ADDR <= 13'h400; timer <= 2; state <= INIT_PRE;
                end
                INIT_PRE, INIT_REF: if (timer != 0) timer <= timer-1'b1; else begin
                    if (init_refreshes != 8) begin
                        {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0001;
                        init_refreshes <= init_refreshes+1'b1; timer <= 3; state <= INIT_REF;
                    end else begin
                        {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0000;
                        DRAM_ADDR <= ENABLE_BURST ? 13'h233 : 13'h230;
                        DRAM_BA <= 0; timer <= 2; state <= INIT_MODE;
                    end
                end
                INIT_MODE: if (timer != 0) timer <= timer-1'b1; else begin
                    initialized <= 1; refresh_age <= 0; state <= IDLE;
                end
                IDLE: if (refresh_age >= REFRESH_LIMIT) begin
                    {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0001;
                    refresh_age <= 0; refresh_count <= refresh_count+1'b1;
                    timer <= 3; state <= REF_WAIT;
                end else if (request_valid) begin
                    address <= request_address; data <= request_data;
                    byte_enable <= request_byte_enable; write_access <= request_write;
                    burst_access <= ENABLE_BURST && request_burst && !request_write;
                    read_beat <= 0;
                    {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= 4'b0011;
                    DRAM_ADDR <= request_address[24:12]; DRAM_BA <= request_address[11:10];
                    timer <= 2; state <= ACCESS;
                end
                ACCESS: if (timer != 0) timer <= timer-1'b1; else begin
                    {DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} <= write_access ? 4'b0100 : 4'b0101;
                    DRAM_ADDR <= {2'b00,1'b1,address[9:0]};
                    DRAM_BA <= address[11:10];
                    if (write_access) begin
                        dq_out <= data; dq_drive <= 1; DRAM_DQM <= ~byte_enable;
                        timer <= 3; state <= RECOVER;
                    end else begin timer <= 4; state <= READ_WAIT; end
                end
                READ_WAIT: if (timer != 0) timer <= timer-1'b1; else begin
                    response_data <= dq_sample;
                    if (ENABLE_BURST) begin
                        response_valid <= burst_access;
                        read_beat <= 1; state <= READ_STREAM;
                    end else begin timer <= 2; state <= RECOVER; end
                end
                READ_STREAM: begin
                    // dq_sample is the previous cycle's phase-shifted CL3
                    // sample. Beats arrive on consecutive clocks, without
                    // backpressure; the cache has one RAM write per beat.
                    if (burst_access) begin
                        response_data <= dq_sample; response_valid <= 1;
                    end
                    if (read_beat == 7) begin timer <= 2; state <= RECOVER; end
                    else read_beat <= read_beat + 1'b1;
                end
                RECOVER: if (timer != 0) timer <= timer-1'b1; else begin
                    // Streaming reads already returned all eight beats.
                    response_valid <= !burst_access; state <= IDLE;
                end
                REF_WAIT: if (timer != 0) timer <= timer-1'b1; else state <= IDLE;
                default: state <= POWERUP;
            endcase
        end
    end
endmodule
