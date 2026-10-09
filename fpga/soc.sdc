# CPU uses rising edges, RAM/MMIO/renderer use falling edges of this same clock.
# Keep these half-cycle paths timed; do not false-path them.
create_clock -name CLOCK_50 -period 20.000 [get_ports {CLOCK_50}]
create_generated_clock -name SDRAM_CLK -source [get_ports {CLOCK_50}] -invert -divide_by 1 [get_ports {DRAM_CLK}]
set dram_outputs [get_ports {DRAM_ADDR[*] DRAM_BA[*] DRAM_DQM[*] DRAM_CS_N DRAM_RAS_N DRAM_CAS_N DRAM_WE_N DRAM_CKE DRAM_DQ[*]}]
# CL3 at 50 MHz: 1.5 ns device setup plus 0.8 ns board allowance.
set_output_delay -clock SDRAM_CLK -max 2.300 $dram_outputs
set_output_delay -clock SDRAM_CLK -min -0.800 $dram_outputs
set_input_delay -clock SDRAM_CLK -max 6.400 [get_ports {DRAM_DQ[*]}]
set_input_delay -clock SDRAM_CLK -min 2.700 [get_ports {DRAM_DQ[*]}]
create_clock -name ENET0_RX_CLK -period 40.000 [get_ports {ENET0_RX_CLK}]
create_clock -name ENET0_TX_CLK -period 40.000 [get_ports {ENET0_TX_CLK}]
derive_pll_clocks
set pixel_clock [get_clocks {*|clock_generator|*|clk[0]}]
# The inherited renderer swaps pages through toggle synchronizers between the
# raster and pixel domains. Preserve its asynchronous clock-domain contract.
set_clock_groups -asynchronous -group [get_clocks {CLOCK_50 SDRAM_CLK *|read_clock|*|clk[0]}] -group $pixel_clock \
    -group [get_clocks {ENET0_RX_CLK}] -group [get_clocks {ENET0_TX_CLK}]
set mii_receive_ports [get_ports {ENET0_RX_DATA[*] ENET0_RX_DV ENET0_RX_ER}]
set_input_delay -clock ENET0_RX_CLK -max 28.000 $mii_receive_ports
set_input_delay -clock ENET0_RX_CLK -min 12.000 $mii_receive_ports
set mii_transmit_ports [get_ports {ENET0_TX_DATA[*] ENET0_TX_EN}]
set_output_delay -clock ENET0_TX_CLK -max 10.000 $mii_transmit_ports
set_output_delay -clock ENET0_TX_CLK -min 0.000 $mii_transmit_ports
set vga_data_ports [get_ports {VGA_R[*] VGA_G[*] VGA_B[*] VGA_BLANK_N VGA_HS VGA_VS}]
# DE2-115 VGA interface delays inherited from the renderer's board constraints.
set_output_delay -clock $pixel_clock -max 0.500 $vga_data_ports
set_output_delay -clock $pixel_clock -min -1.500 $vga_data_ports
set_false_path -to [get_ports {LEDG[*] VGA_CLK VGA_SYNC_N ENET0_RST_N ENET0_TX_ER}]
derive_clock_uncertainty
# Reset button is asynchronous; release is synchronized in the board wrapper.
set_false_path -from [get_ports {KEY[0]}]
# Mechanical game buttons enter the first stage of a two-register synchronizer.
set_false_path -from [get_ports {KEY[1] KEY3}] -to [get_registers {*buttons_meta*}]
