`timescale 1ns/1ps
// Give CL3 data time to return through the board and input buffer. The external
// clock remains CLOCK_50 inverted; only the I/O sampling clock shifts +4.5 ns.
module sdram_capture_clock (
    input logic inclk0, areset,
    output wire c0,
    output logic locked
);
`ifdef ALTERA_RESERVED_QIS
    wire [4:0] clocks;
    altpll pll (
        .areset(areset),.inclk({1'b0,inclk0}),.clk(clocks),.locked(locked),
        .clkena(6'b111111),.extclkena(4'b1111),.fbin(1'b1),.pfdena(1'b1),
        .phasecounterselect(4'b1111),.phasestep(1'b1),.phaseupdown(1'b1),.pllena(1'b1),
        .scanaclr(1'b0),.scanclk(1'b0),.scanclkena(1'b1),.scandata(1'b0),.scanread(1'b0),.scanwrite(1'b0)
    );
    defparam pll.bandwidth_type="AUTO", pll.clk0_divide_by=1,
        pll.clk0_multiply_by=1, pll.clk0_duty_cycle=50, pll.clk0_phase_shift="4500",
        pll.compensate_clock="CLK0", pll.inclk0_input_frequency=20000,
        pll.intended_device_family="Cyclone IV E", pll.lpm_type="altpll",
        pll.operation_mode="NORMAL", pll.pll_type="AUTO",
        pll.port_areset="PORT_USED", pll.port_inclk0="PORT_USED",
        pll.port_locked="PORT_USED", pll.width_clock=5;
    assign c0=clocks[0];
`else
    // Same period and phase as the configured PLL, without vendor lock latency.
    assign #4.5 c0=inclk0;
    always_comb locked=!areset;
`endif
endmodule
