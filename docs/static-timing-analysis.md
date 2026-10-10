# Static timing analysis: STA-001

Analyzed October 10, 2026, source/report baseline `ba78b16`. The existing fitted IntegerMulSoC design meets its configured timing constraints at 50 MHz. The worst setup margin is **+0.468 ns on the local-RAM-to-UDP-loader return path**, which has only a 10 ns half-cycle budget. The smallest hold margin is **+0.115 ns in Ethernet receive logic** at the fast corner. These are TimeQuest static timing results, not measured maximum operating frequencies or new performance improvements.

No RTL, clock constraints, firmware, game assets or programmed FPGA image were changed. No fitter or new board benchmark was run. Detailed queries were run against the existing placed-and-routed database using Quartus Lite 18.1.0 Build 625, Cyclone IV E EP4CE115F29C7. The final query completed with zero errors and zero warnings.

## Critical paths

Setup results below use the slow 1200 mV, 85 C model. A positive slack means the modeled signal arrives before its deadline, including the applied clock uncertainty and skew. Rows with register filters describe paths ending in that group; they do not exclude sources elsewhere in the system.

| Priority/domain | Reported setup slack | Edge budget | Critical path and significance |
|---|---:|---:|---|
| Overall / loader | +0.468 ns | 10.000 ns | Local RAM port-B internal register → loader `results[1][29]`. Falling-edge RAM output, read formatting and memory selection feed a rising-edge result capture. |
| CPU endpoints | +1.032 ns | 20.000 ns | Writeback `pc_WB[3]` → fetch `pc[1]`/`pc[0]`, through writeback selection, forwarding, ALU MUL hardware and control/next-PC logic. |
| SDRAM capture | +1.410 ns | 14.500 ns | `DRAM_DQ[13]` → controller `dq_sample[13]`, with the phase-shifted read PLL and external input-delay assumptions. |
| GPU endpoints | +1.456 ns | 20.000 ns | Transform `fan_index[0]` → `out_data.z0[2]`, through polygon selection, screen-area arithmetic, backface decision and output capture. |
| SDRAM output | +2.828 ns | 10.000 ns | Controller `dq_drive` → `DRAM_DQ[22]` and `[16]`, including output setup requirements. |
| Ethernet TX | +3.581 ns | 40.000 ns | Response `status_frame_id[5]` → `ENET0_TX_DATA[3]`. Response selection is a long combinational output path. |
| Cache endpoints | +4.901 ns | 10.000 ns | Bridge `request_data[30]` → cache `saved_data[30]`. The cache's internal response path also appears in the top five at +5.686 ns. |
| Ethernet RX | +6.166 ns | 40.000 ns | `ENET0_RX_DATA[0]` → receiver `transport_result[0]`, including external input delay. |
| Pixel-clock domain | +12.982 ns | 39.724 ns | Display `fps_sync2[2]` → `VGA_G[4]`, including VGA output delay. This is not the 50 MHz rendering datapath. |

The original multicorner report shows zero negative slack/TNS for its reported setup, hold, recovery, removal and pulse-width checks at slow 85 C, slow 0 C and fast 0 C. The worst CLOCK_50 setup margins across those corners are +0.468, +1.202 and +4.857 ns respectively.

### Local RAM and loader

The worst path's data delay is 8.983 ns: interconnect 4.836 ns (report-rounded 54%), cell delay 3.884 ns (43%), and clock-to-output 0.263 ns (3%). It has five reported logic levels and -0.547 ns clock skew. The RAM's internal port output cell alone contributes 2.890 ns; major individual routes contribute 1.819 ns and 1.602 ns. This is both a memory/output-selection and placement problem.

`rtl/generated/soc_ram.sv` captures RAM inputs on `~clk` and leaves outputs unregistered. It formats byte/halfword/word reads. `rtl/soc_memory.sv` selects local RAM versus SDRAM for `load_rdata`, and `rtl/udp_memory_loader.sv` stores that result on the rising edge when `bus_ready` is asserted. Being a loader path does not exempt it from timing: it is exercised by loading/readback/profiling and constrains the common clock.

First investigate a separately registered, handshaked loader read response or a simpler dedicated full-word loader return path. Preserve RAM subword semantics for CPU accesses and adjust ready/result capture together. A register cannot be inserted safely without accounting for its extra latency. Also inspect placement/locality of RAM output selection and loader result registers. Do not hide this path with a false-path or multicycle exception merely because it is infrequent.

### CPU forwarding, MUL and next-PC

The CPU path has 18.860 ns data delay, 16 reported logic levels, 7.383 ns interconnect, 11.245 ns cell delay and 0.232 ns clock-to-output. The full path explicitly includes `RM|Mux3`, `ALU_A`, `alu|Mult0` DSP and product-combining logic, `ALU_result`, and PC capture selection. The DSP cell on this path contributes 3.476 ns; the whole path is much longer than that DSP alone.

The source explains the connection: writeback includes `pc_WB + 4`; forwarding can feed that result into EX; `soc_ALU` selects MUL or the base ALU; `BranchUnit` uses shared `ALU_result` for JALR target and comparisons. Static analysis considers the structural path even though MUL and JALR are distinct instruction modes. This report does not establish whether every segment can be simultaneously sensitized by a legal instruction. No path exception was added or proposed as proven.

A useful first CPU experiment is a dedicated forwarded `rs1 + imm` JALR target and separate branch comparison, removing shared multiplier output from next-PC selection while preserving all ISA behavior. Then re-fit and query EX/MEM as well as PC endpoints: shortening one path can expose another. Pipelining MUL is a larger alternative that requires latency, forwarding, dependency and retirement changes. Superscalar processing is not justified by this analysis.

### GPU fan construction and culling

The GPU path has 18.415 ns data delay, eight reported logic levels, 7.942 ns interconnect, 10.241 ns cell delay and 0.232 ns clock-to-output. A DSP cell contributes 3.529 ns. In `external/renderer/rtl/pipeline/transform_3d_pipeline.sv`, dynamic `fan_index` selects polygon vertices, `screen_area()` calculates signed area, and `TRIANGLE_BUILD` tests `fan_area < 0` before storing the output triangle. The endpoint is a depth field because the culling decision controls the output update; it does not mean depth arithmetic alone is the culprit.

An experiment could register selected fan vertices and/or the area/cull decision before output emission. Preserve winding, triangle ordering, valid/ready behavior and counters. This may add cycles per triangle even while increasing allowable clock frequency, so evaluate frame workload counters alongside STA. It is not evidence that floating point would help.

### Hold margins

The fast 1200 mV, 0 C corner has +0.115 ns hold slack from receiver `packet_frame_id[15]` to the packet-response FIFO RAM input register. The smallest CLOCK_50 hold margin is +0.143 ns from cache `saved_data[30]` to a cache-word RAM data input. Both pass the current fit. These are short same-domain paths, not failed asynchronous transfers. Lowering the clock frequency is not a general repair for same-edge hold timing. Recheck all corners after placement, pipelining or clock changes; let the fitter manage short-path delays rather than inserting arbitrary RTL delay chains.

## Constraints and limits of the conclusion

`fpga/soc.sdc` constrains CLOCK_50 to 20 ns, MII RX/TX to 40 ns, an inverted SDRAM output clock, the derived 4.5 ns-phase read clock and a derived 39.724 ns pixel clock. CPU rising-edge and RAM/MMIO/renderer falling-edge transfers retain their real half-cycle constraints. SDRAM input maximum/minimum delays are 6.400/2.700 ns; output maximum/minimum delays are 2.300/-0.800 ns. MII and VGA have explicit I/O delays.

The original report's coverage summary lists zero illegal clocks, unconstrained clocks, unconstrained input/output ports and unconstrained port paths for setup and hold. That does not prove every timing exception or physical board-delay assumption is correct. Pixel, Ethernet RX and Ethernet TX groups are asynchronous to the core/SDRAM group and each other. The SDC intentionally excludes those cross-domain transfers, selected status outputs, asynchronous reset input, and mechanical-button input to synchronizer first stages. CDC correctness requires synchronizer/FIFO review independently of STA; this task did not perform an exhaustive CDC or board electrical audit.

TimeQuest reports a **52.45 MHz restricted Fmax for CLOCK_50** at slow 85 C. It computes same-clock paths (including edge inversion), excludes different-clock paths even for related generated clocks, and scales the duty cycle. This is a model estimate, not an experimentally demonstrated operating frequency or authorization to overclock. SDRAM phase relationships, external interfaces and PLL settings must be reanalyzed for any new clock configuration. The 50 MHz clock currently has limited margin.

## What is critical to frame performance?

The static paths above determine timing closure. Existing physical-board profiling determines the work taking time; no new runtime samples were taken here. In `docs/post-mul-bottlenecks.md`, normal animated standing/moving medians at 50 MHz are:

| CPU work | Standing | Moving |
|---|---:|---:|
| Whole rendering/submission | 18.91746 ms | 21.26326 ms |
| Terrain transforms/outcodes | 6.34360 ms | 6.34348 ms |
| Command submission | 5.88420 ms | 7.71204 ms |
| Classification/clipping | 4.04662 ms | 4.27592 ms |
| Memory freezes within rendering | 0.89550 ms | 0.89214 ms |

These scopes overlap and must not be added to the whole-render total. GPU execution overlaps CPU feeding, and presentation wait is not useful CPU computation. Current game pacing is approximately 30 frames/s, so reducing a render section need not increase FPS.

The later `docs/terrain-offload-and-profiling.md` comparison shows coarse direct rendering at 18.68794 ms for its controlled standing pose. Safe resident offload had zero admitted castle chunks and 18.75364 ms there. An authored eligible fixture reduced CPU render time from 7.30228 to 0.18166 ms without a demonstrated FPS increase. Fine CRC/check/write and intersection instrumentation is intrusive and is not interchangeable with these coarse timings.

Therefore the priorities depend on the objective:

1. **Clock headroom:** address the half-cycle RAM/loader response first; then CPU forwarded arithmetic/next-PC and GPU fan-area/cull staging. Audit SDRAM timing before any clock increase. Cache setup is not the first clock-limiting target.
2. **Game render headroom:** make castle chunks eligible for safe GPU offload through tighter geometry packing and exact translation support; investigate lower-overhead command submission; then clipping work. Preserve the existing correctness guards and original assets/behavior.
3. **Validation:** retain this fit as the baseline. Change one feature at a time; compare full multicorner timing, utilization, identical workload cycles and actual frame progress. Do not count an Fmax estimate or reduced synthetic-fixture cycles as a measured whole-game FPS improvement.

## Evidence and reproduction

Raw original STA report/summary, the analyzed SDC and project settings, fresh detailed setup/hold reports, Tcl query, runner and SHA-256 manifest are in `docs/benchmarks/static-timing-001/`. The manifest identifies the existing SOF and hashes it before/after querying. The runner temporarily recreates only the missing IntegerMulSoC project files, refuses to overwrite existing ones, opens the existing fit database, and removes its temporary files in `finally`. It requires the original `db/IntegerMulSoC*` fit database; the reports alone cannot regenerate placement.

Run from the repository root with Python: `python docs/benchmarks/static-timing-001/analyze_timing.py`. This invokes only `quartus_sta -t`; it does not invoke synthesis, fitting, assembly or programming. No performance improvement or new resume speedup claim is made by this analysis.
