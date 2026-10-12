# Stage 6: independent rendering and timing reassessment

The optional repeat-safe render mode is selected for Castle at the existing
50 MHz. Standing presentation medians improve **29.96906 to
59.95759 FPS (100.065% higher)**.
Simulation retains the original 1,666,667-cycle tick and four-update catch-up
cap. Extra presentations can repeat the same simulation state; this adds no
interpolation or gameplay speedup. Movement results below show why 60 FPS is
not a level-wide guarantee. CPU/GPU RTL, clocks, models, collision, camera,
transitions and animation logic are unchanged.

## Baselines and identity

- Accepted Stage 5: `c4f93877eb1c50b422046af8c1c89b9b1111a178`.
- Stage 6 comparison baseline: `e50d34f49689646bead2ac1431302bf7e7c7afc5`.
- Firmware implementation: `a854e1ed41bbe2be926481489f6fccdc38106e97`.
- Board: DE2-115 / EP4CE115F29C7, USB-Blaster [USB-0], UDP 192.168.7.2:4000.
- Quartus Lite 18.1.0 Build 625; Clang 21.1.6; RV32I with audited MUL only.
- Same accepted image: `build/quartus-arch-stage5-worker/ArchStage5SoC.sof`,
  SHA-256 `e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14`.
- Same 883,124-byte asset segment, SHA-256
  `afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`.
- Matched control CPU: 27,096 bytes,
  SHA-256 `12d634016e2913b700e0fd21de522f3ae5e507fdc3417f692d92defafc2a3407`.
- Candidate CPU: 27,108 bytes,
  SHA-256 `aba46c6d488085f1e7999ff42eeb2caa0220d3dc58a5fc9bf9a43911bd24e531`.
- Exact old Stage 5 package remains in `build/arch-stage6/baseline/`; CPU SHA
  `3b104f5a1a701732b866d7a31dea4091e937116e1f5730ac9d0c0c50863c5edf`.

Candidate adds 260 code bytes and 212 BSS bytes against the old Stage 5 package.
BSS end moves 34,476 to 34,948 including code displacement; RAM hardware remains
64 KiB. No hardware resources changed: 26,557 LEs, 2,659,688 logical memory bits,
366 M9Ks, 92 embedded 9-bit multipliers, two PLLs.

## Implementation and reusable contract

`game_clock.h` provides an unsigned-wrap-safe nonblocking deadline check and the
existing catch-up arithmetic. `game_runtime.c` uses the same advance helper.
`portable_main.c` optionally checks whether a tick is due before rendering,
updates only when due, and still waits for the original completed-frame and
vertical-blank presentation handshake. The default build retains tick pacing.

The project must declare `port.render_repeat_safe=true` to use
`--uncapped-render`. Rendering must not advance gameplay, camera smoothing,
transition timers or animation phase, or derive their time from presentation
IDs. Those changes belong in `game_port_update`. Castle already met that
contract; its game logic was unchanged. `sm64_castle.py` emits the declaration
for reproducible exports. Other game ports retain their existing pacing.

A 24-word ABI (`0x43540101`) publishes simulation tick count, elapsed cycles,
updates this frame, tick/update/submission/presentation spans and 13 matching
GPU counters. Firmware writes the inactive volatile slot, then publishes its
index last. Pausing during a write leaves the previous complete slot available.
`profile_cpu.py` validates addresses, ABI, clock and counter consistency before
using it. Counter arrays are low-cost normal telemetry, without the detailed
function profiler. Elapsed cycles are 32-bit; absolute simulation-rate estimates
use fresh short reset trials below wraparound, not long-running counters.

`audit_stage6_timing.py` reanalyzes the accepted fitted netlist.
`measure_render_cadence.py` runs matched reset trials, reads back uploaded
CPU/assets, records UDP input/frame progress and restores exact Stage 5 software
in a finally block. `--moving` selects a wall-clock movement diagnostic.

## Standing view: all three reset trials per mode

| Metric | Tick-paced | Uncapped |
| --- | --- | --- |
| Observed FPS | 29.86232, 29.96906, 29.96906 | 59.94972, 60.13148, 59.95759 |
| Median FPS | 29.96906 | 59.95759 |
| Simulation Hz, short cumulative window | 29.93463, 29.93463, 29.93463 | 29.93449, 29.87481, 29.93449 |
| Snapshot frame IDs | [251, 251, 251] | [500, 501, 500] |
| Updates in sampled frame | [1, 1, 1] | [1, 0, 1] |

| Completed-frame span, cycles (all trials) | Tick-paced | Uncapped |
| --- | --- | --- |
| Tick wait | [754783, 754783, 754801] | [5, 5, 5] |
| Simulation update | [40190, 40190, 40190] | [40197, 8, 40197] |
| Render submission | [608723, 608723, 608723] | [608626, 608632, 608626] |
| Update + submission | [648913, 648913, 648913] | [648823, 608640, 648823] |
| Presentation wait | [264464, 264464, 264442] | [185121, 225304, 185121] |
| Update start through presentation | [913385, 913385, 913363] | [833952, 833952, 833952] |

Configured 50 MHz conversions: median render submission is 12.17446 versus
12.17252 ms, so no renderer execution speedup is claimed. Median tick wait falls
15.09566 to 0.00010 ms. A no-update frame still renders; its 8-cycle update span
is bookkeeping. Presentation wait includes GPU drain and vertical blank, not
just raster work. The theoretical simulation rate is 50,000,000 / 1,666,667,
approximately 30 Hz. Short cumulative windows include fractional tick/render
intervals; candidate frame 501 trails the elapsed tick deadline by one update,
other standing snapshots by zero. The tick period is unchanged.

GPU work before swap wait is 615,049 versus 615,054 cycles in these snapshots,
approximately 12.301 ms. Control frame 251 and candidate frames 500/501 at tick
250 have different actor poses; raw event counts belong to their own frame and
are not claimed identical. CPU submission, geometry, command starvation,
raster and clear spans overlap and must not be summed as serial frame time.

Observed FPS uses host-timed frame progress over about 5.3 seconds after three
seconds settling. Three completed-frame phase snapshots are not a frame-time
distribution or percentile study. Snapshot metrics exclude tick wait from
`game_frame_cycles`; actual presentation FPS is measured separately.

## Movement diagnostics

Three fresh resets per mode send timed square-direction UDP inputs. Raw packets,
timestamps, positions, frame progress and completed-frame CPU/GPU spans are
retained. This is a wall-clock diagnostic, not a cycle-identical replay.

| Mode | All FPS trials | Median FPS | Final positions |
| --- | --- | ---: | --- |
| moving-tick-paced | 29.98270, 29.86811, 30.06206 | 29.98270 | [[-1088, 260, 3920], [-1088, 260, 3944], [-1112, 260, 3944]] |
| moving-uncapped | 44.28544, 44.67221, 43.43648 | 44.28544 | [[-1112, 260, 3944], [-1136, 260, 3968], [-1088, 260, 3944]] |

Input sampling phases and host timing can change the final position. Some views
miss a VGA presentation deadline; faster presentation is workload dependent.
These tests verify running input/frame progress, not full castle/slide traversal,
original-engine behavior, physical framebuffer equivalence or every collision.
Neither framebuffer resolution nor the simulation-state update rate changed.

## Timing and clock-domain audit

TimeQuest reran on the same final routed Stage 5 database. Exact before/after
reports, SDC/QSF and tool log are retained. All 85 preserved Stage 5 RTL/SDC source files match byte-for-byte.
No new fit/assembly was required:
no RTL, clock, PLL, SDRAM timing or exception changed. No overclock was attempted.

| Multicorner worst slack | ns |
| --- | ---: |
| Setup | +0.424 |
| Hold | +0.128 |
| Recovery | +2.996 |
| Removal | +3.478 |
| Minimum pulse width | +9.194 |

Slow 85C, slow 0C and fast 0C models are in the raw report. There are zero
unconstrained setup/hold clocks, I/O ports or their paths. Worst slow-85C setup:
loader `hold_cpu` to RAM port-B write data, 10 ns half-cycle relationship,
9.989 ns data delay, +0.424 ns slack. RAM write feedback to loader results is
another half-cycle path (+0.554 ns). CPU `rs2addr_EX[0]` to
`ctrl_EX.ALU_Sel[1]` has +0.820 ns at a 20 ns relationship. These current paths
supersede guesses based on historical GPU endpoints.

- CPU rising and RAM/MMIO/renderer falling edges remain timed together.
- SDRAM clock stays inverted 50 MHz, read capture stays +4.5 ns at 50 MHz,
  with CL3, burst and refresh constants unchanged. Related PLL/SDRAM clocks
  remain in the synchronous timing group.
- MII RX/TX stay constrained at 25 MHz. Imported Ethernet queues use Gray-pointer
  asynchronous FIFOs with two-register pointer synchronizers.
- VGA uses its derived pixel PLL and dual-clock RAM. Page swapping uses a
  two-register synchronized request/ack toggle and vertical-blank ownership.
- External SDRAM/MII/VGA delay values remain inherited board/device assumptions,
  not newly measured electrical margins. Zero unconstrained paths does not
  certify every assumption/CDC. Existing asynchronous groups cut Gray-bus
  paths; explicit routing-skew/delay bounds and per-domain reset-release proof
  require dedicated verification before any frequency change. The binary
  network free-space reply statistic is double-synchronized; that is not a
  coherent multi-bit CDC proof. Local RX FIFO ready governs receive ownership.

Keep 50 MHz. Future timing work should register loader request/read-response
ownership with delayed acknowledgement, then requery CPU decode/forwarding.
Do not hide the half-cycle paths with false-path/multicycle exceptions. A clock
experiment must revise PLL phases, SDRAM timings, input timeouts, cycle-to-time
reporting and fixed simulation deadlines, then run full fit/STA and physical
comparisons. No Fmax, maximum clock or power improvement is claimed here.

## Validation and selection

Five native tests execute production clock helpers: deadlines, repeated renders,
multiple render rates, wraparound, four-tick catch-up and capability rejection.
Thirty Castle/world tests pass, including the original 20-tick slide-return
behavior. A new fixture renders twice after each of 40 idle/moving updates:
captured payload/matrix bytes match exactly (frame IDs excluded), posed-vertex
hashes match, and player/camera/animation state hashes remain unchanged.
This is a host C fixture, not a new full CPU/GPU differential replay. Hardware
and draw semantics are unchanged; Stage 5 remains the RTL/full-frame reference.
Normal and shortened-retention builds pass specialized-C and linked ISA audits;
unsupported M instructions remain absent.

Twelve final physical trials use atomic telemetry (six standing, six movement).
Six earlier exploratory standing trials are retained under `preliminary/`;
their non-atomic phases are excluded from final phase claims. One exploratory
CPU binary was superseded before archiving; its original SHA/size remains in
raw trials, with no missing bytes/counters reconstructed. Final binaries,
ISA/symbol/package metadata, source/config snapshots, logs, profiles and SHA
manifest are preserved. Asset/SOF bytes stay in existing local artifacts and
are identified by hashes.

Selected unprofiled uncapped Castle is fully uploaded/read back and checked for
frame progress on the same Stage 5 image. The final deployment record identifies
the exact package. Old Stage 5 software remains the rollback. This milestone
improves presentation throughput; interpolation, complete-level acceptance,
power, maximum-frequency and frame-time percentile claims remain unmeasured.

## Reproduction

Run from the repository; stop the keyboard sender during experiments.

```powershell
.\scripts\run.ps1 test_game_clock.py
.\scripts\run.ps1 test_world_pipeline.py
.\scripts\run.ps1 audit_stage6_timing.py
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --packed-gfx --integer-mul --geometry-offload
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --packed-gfx --integer-mul --geometry-offload --uncapped-render
.\scripts\run.ps1 measure_render_cadence.py
.\scripts\run.ps1 measure_render_cadence.py --moving
.\scripts\run.ps1 load_game.py build/mario-castle-sdram-direct-packed-mul-geometry-uncapped.package.json
# Exact Stage 5 software rollback, same hardware:
.\scripts\run.ps1 load_game.py build/arch-stage6/baseline/mario-castle-sdram-direct-packed-mul-geometry.package.json
```

[Measurements](benchmarks/arch-upgrade-001-stage-6/measurements.json),
[timing audit](benchmarks/arch-upgrade-001-stage-6/timing/audit.json),
[deployment](benchmarks/arch-upgrade-001-stage-6/accepted-running-check.json),
[SHA manifest](benchmarks/arch-upgrade-001-stage-6/manifest.json).
