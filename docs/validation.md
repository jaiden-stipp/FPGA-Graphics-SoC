# Validation record

## General game pipeline

Validated October 8, 2026. [Contracts, adapters, game modules and commands](portable-games.md).
No CPU/GPU RTL or programmed FPGA image changes are needed.

| Check | Result | Evidence |
| --- | --- | --- |
| Host regressions | PASS | 70 tests: 57 existing tests plus 13 shared-pipeline tests; `stage4-host-tests.json`, `portable-host-tests.log` |
| Source/data preservation | PASS | 32 baseline files and original hardware generators unchanged; original Quake geometry/palette/collision round-trip exactly through the shared IR |
| Portable builds | PASS | Nine mandatory Clang subset audits per build; authored explorer, independent custom gameplay and original Quake adapter use the same build command |
| Capacity | PASS | Room: 10,480 CPU / 1,572 asset bytes, 3 handles / 26 triangles; custom: 10,616 / 196 bytes, 2 / 14; Quake: 10,480 / 36,492 bytes, 5 / 786 |
| Full portable Quake CPU-to-VGA | PASS | Actual RV32I, SDRAM, MII turn/walk/jump, GPU and post-depth VGA capture; `portable_scene_top_tb.log` |
| Rendered preservation | PASS | Both standing and moving captures pixel-for-pixel identical to the previous Quake package; `portable-render-validation.json` |
| Captured frame work | PASS | CPU plus active GPU: 10.97692 ms standing, 11.69612 ms moving, at 50 MHz; swap wait excluded |
| Physical package switching | PASS | All three packages uploaded with every word read back before COMMIT; each advances 30 displayed frames in a one-second sample; `portable-board-*.json` |
| Hardware preservation | PASS | Same SOF SHA-256 `35bccc1e7fbc2ad2a6690ee7f7658dc3abdfdff59a576f2cee12b1fa758275d5`; no Quartus rebuild or FPGA reprogramming |

The board is left running `portable-quake`. The unchanged small raster cracks
described below remain in the identical captures. Functional simulation uses
the final +4.5 ns SDRAM sampling phase and only shortens fixture boot retention;
physical packages retain the full 100 ms SDRAM test. The measured views and
one-second hardware samples do not guarantee frame performance for arbitrary
game modules or camera positions. Loading compatible scene data does not port
an original game's engine; arbitrary unmodified games remain unsupported.

## Stage 4: two games on the unchanged SDRAM SoC

Validated October 8, 2026. [Build, controls and package switching](stage4-packages.md).
The existing verified FPGA image is unchanged; this milestone builds and loads software packages.

| Check | Result | Evidence |
| --- | --- | --- |
| Original hardware and Mario logic | PASS | 32 source/header/profile files byte-identical to the SDRAM baseline; original CPU/GPU generators and three pinned upstream checkouts unchanged; `stage4-preservation.json` |
| Mario rendered preservation | PASS | Actual standing and jumping post-depth GPU pixels identical to the previous SDRAM captures; `stage4-mario-pixel-preservation.json` |
| Host tests | PASS | 57 tests: original scene/player/camera/animation, loader, runtime/package validation, original BSP geometry, all 64 view headings, walking, wall stop, jump/land, reset and bounds |
| Specialized RV32I C | PASS | Ten Clang subset audits; both ELF files `rv32i2p1`, no undefined helpers |
| Package capacity | PASS | Mario: 16,216 CPU bytes, 99,840 asset bytes, nine handles/1,255 triangles; Quake: 10,516 CPU bytes, 36,464 asset bytes, five handles/786 triangles |
| Local writable memory | PASS | Mario `_bss_end=0x4540`, Quake `_bss_end=0x293c`; 43,712/50,884 bytes remain before the reserved 4 KiB stack |
| Full Mario CPU-to-VGA | PASS | MII movement/jump, actual SDRAM/RV32I/GPU/VGA, 1,255 triangles; 20.70/22.56 ms CPU plus active GPU work |
| Full Quake CPU-to-VGA | PASS | MII turn/walk/jump, actual SDRAM/RV32I/GPU/VGA, 786 triangles; 10.98/11.69 ms CPU plus active GPU work |
| Quake original-geometry coverage | PASS | Interior background pixels standing/moving: 2/34; independent original BSP reference excludes a three-pixel edge band; `quake-coverage.json` |
| Physical package switching | PASS | Every word of both linked CPU/assets packages read back before COMMIT; each advances 30 displayed frames in a one-second sample; same SOF hash, no reprogramming |
| Physical keyboard transport | PASS | 59 replies / 59 accepted neutral packets after final corrected Quake load |
| Interactive physical VGA review | AWAITING USER CHECK | Quake is loaded; inspect first-person view, collision and control feel on the monitor |

The coverage check allows at most 64 interior background pixels per frame
(under 0.09%). Its 2/34 observed pixels are small remaining cracks, especially
in the moving floor view; this pass does not mean pixel-perfect raster coverage.
Their cause requires a separate renderer precision investigation.

Both full-renderer simulations use the final +4.5 ns SDRAM sampling phase.
Only fixture boot retention is shortened to 1,000 cycles; real-board packages
retain the full 100 ms memory test and real 30 Hz gameplay timer. These captured
views fit the 33.33 ms budget; timing is not a guarantee across every camera view.
The existing Quartus resources, positive constrained timing and remaining
warnings recorded below still apply; stage 4 does not rebuild hardware.

The initial Quake profile revealed inverse-depth wrap for `near_z < 257`.
The corrected adapter uses uniform scale four, matching physics/eye scaling,
and a 257-unit near plane without changing GPU RTL. Source positions and face
identities are checked independently. Quake is flat-color starting-area
exploration, with 167 floor and 619 wall triangles; engine, entities, brush-model
doors, textures, audio and full-map streaming remain outside this milestone.

## SDRAM asset loading and expanded scene

Validated on October 8, 2026. Build, loading and memory details are in
[sdram.md](sdram.md). This is the current board image; the stage records below
describe earlier on-chip asset builds.

| Check | Result | Evidence |
| --- | --- | --- |
| Original logic and source preservation | PASS | Eleven stage 3 player/camera/animation/driver/header/profile files compare byte-for-byte; all three pinned upstream checkouts remain clean; `build/sdram-preservation.json` |
| Host regressions | PASS | 46 tests, including manifest/range/hash validation, completed-operation replies and retry transport IDs; `build/sdram-host-tests.log` |
| RV32I firmware and assets | PASS | Eight C source audits, ELF `rv32i2p1`, no undefined helpers; 15,696-byte CPU binary and 99,840-byte external asset segment; `_bss_end=0x4338` leaves 44,232 bytes before the reserved 4 KiB stack |
| Expanded original scene | PASS | All 1,043 opaque terrain triangles from four original BOB roots, 212 Mario triangles, original 20-joint hierarchy and four clips; nine handles and 243 colors; board and simulation asset segments are identical |
| SDRAM memory simulation | PASS | Initialization, all 25 word-address bits, upper-range accesses, byte masks, signed loads, consecutive accesses, misalignment and refresh; `build/sdram_memory_tb.log` |
| Actual RV32I SDRAM self-test | PASS | Data/address/byte/retention test with 2,538 wait cycles; all pipeline registers held and retirement suppressed during waits; full 100 ms retention loop; `build/sdram_cpu_tb.log` |
| MII package loader | PASS | Actual Ethernet CRC/CDC, local RAM and SDRAM upload/readback, range/hold guards and keyboard after COMMIT; `build/udp_loader_tb.log` |
| Full CPU-to-VGA simulation | PASS | Actual MII controls, movement/jump and 1,255 GPU triangles; displayed frame 2 at 187.55 ms; actual post-depth standing/jump captures contain 119/198 red Mario pixels; `build/sdram_mario_top_tb.log` |
| Measured frame work | PASS | CPU 14.26/16.12 ms plus GPU active work 6.44/6.44 ms = 20.70/22.56 ms at 50 MHz; swap wait excluded; below the 33.33 ms frame budget for these two captured views |
| Quartus synthesis/fit/timing/assembly | PASS | 19,653 logic elements, 2,624,944 logical memory bits, 346/432 M9Ks, 66 multipliers and two PLLs; CPU setup +0.743 ns, read-clock setup +1.426 ns, SDRAM output setup +2.805 ns; worst hold +0.102 ns, all 60 reported timing slacks positive and zero unconstrained paths |
| Physical FPGA programming | PASS | EP4CE115F29@1 / USB-Blaster [USB-0], checksum `0x014b264c`; zero programmer errors/warnings; `build/quartus-sdram-program.log` |
| Physical SDRAM self-test | PASS | Real CPU reports `0x5dad600d` after data/address-line checks, byte/signed accesses and full 100 ms refresh retention; `build/sdram-board-self-test.log` |
| Physical package and rendering | PASS | Every word of CPU and asset segments uploaded and read back before COMMIT; displayed-frame counter advances 30 frames in a one-second sample, with refresh running; `build/sdram-board-load.log`, `build/sdram-board-running.json` |
| Physical keyboard transport | PASS | 59 replies / 59 accepted packets after PHY link settles; `build/sdram-board-udp.log` |
| Interactive VGA and movement review | AWAITING USER CHECK | Hardware counters and simulated pixels pass; inspect physical animation, camera, collision and input feel interactively |

The full-renderer functional simulation ran with a +3 ns read sampling phase.
The final hardware phase is +4.5 ns to close external timing. Final memory,
CPU and MII loader simulations use that phase with 6.4 ns read access and 2.7 ns
minimum data hold in the device model; physical self-test, complete package
readback and running frame counters also qualify the final image. The GPU
fixture shortens only boot retention to 1,000 cycles; its physics timer remains
the real 30 Hz timer. The dedicated CPU test and both board applications retain
the full 100 ms test. Address-line tests cover representative locations across
the 128 MiB window rather than exhaustively testing every byte.

Synthesis reports 19 warnings and fitting seven; timing and assembly have zero.
Fitting retains a remote PLL input compensation critical warning; external
input/output timing is fully constrained and positive with the final phase.
Other fitter warnings include the inherited VGA clock routing and I/O assignment
requirements. The full-renderer simulation has zero errors and 56 inherited
Intel IP warnings; memory/CPU/loader tests have zero errors and 14/28/10 unused
port connection warnings. Complete reports, image hashes and framebuffer
measurements accompany the SDRAM artifact package.

After hardware reset or power loss, reload the game package using the commands
in [sdram.md](sdram.md). The current image stores assets in SDRAM while code and
writable game state remain in 64 KiB local RAM. GPU resident mesh capacity,
textures and unsupported gameplay features are unchanged.

## Stage 3 original skeletal animation

Validated on October 8, 2026. Behavior and adapter choices are described in
[stage3-animation.md](stage3-animation.md). Content expansion estimates are in
[content-capacity.md](content-capacity.md).

| Check | Result | Evidence |
| --- | --- | --- |
| Source/controller/hardware preservation | PASS | 14 stage 2 RTL/controller/camera/driver/profile files compare byte-for-byte; profile adds only animation; all three pinned source checkouts clean; `build/stage3-preservation.json` |
| Host regressions | PASS | 43 tests; eight new animation tests cover original local vertices, all 135 reachable clip frames both grounded and airborne, indexed samples, axes, sole contact, state transitions, respawn and parser rejection |
| Pose accuracy | PASS | All 136 vertices against independent float hierarchy evaluation; worst deviation 1.0549 integer GPU coordinate units; rotation error below 0.001 and translation error below 0.5 source units |
| RV32I audit / firmware | PASS | Six C audits, ELF `rv32i2p1`, no undefined symbols; 56,058-byte board binary, `_bss_end=0xe0e4`; 3,868 bytes left before reserved 4 KiB stack |
| Assets | PASS | Original 20-node hierarchy, four clips, 212 actor + 326 terrain triangles, five handles and 151 colors; same source local coordinates, indices and palette assignments |
| Full CPU-to-VGA simulations | PASS | Actual MII UDP move/jump, 538 GPU triangles and displayed frame 2 at spawn and bridge; four post-depth framebuffer captures with 122/193 and 114/188 red actor pixels respectively |
| CPU pose / upload budget | PASS | Posing 254,919–255,782 cycles (5.10–5.12 ms); 136-vertex upload 175,783 cycles (3.52 ms); total CPU work 488,568–652,511 cycles (9.77–13.05 ms) in accelerated fixtures |
| GPU / combined work budget | PASS | GPU active work 307,338–346,748 cycles (6.15–6.93 ms); conservative CPU + GPU sum 15.97–19.87 ms, below 33.33 ms at 50 MHz; swap wait excluded |
| Independent terrain coverage | PASS | All four captured views/projections match float and integer-projection references with zero interior sky gaps; `build/game/diagnostics/coverage.json` |
| Quartus map / fit / timing / assembly | PASS | 17,111 logic elements, 2,623,928 logical memory bits, 338/432 M9Ks and 66 multipliers; CPU setup +0.746 ns, worst hold +0.109 ns; all 42 timing slacks positive |
| Real RV32I animation lifecycle | PASS | 33 frames, 22,188,918 cycles; movement/jump/landing/respawn, complete vertex updates, changed poses and all four clip states under backpressure |
| Physical FPGA programming / UDP | PASS | USB-Blaster [USB-0], EP4CE115F29@1; zero programmer errors/warnings; after link settles, neutral input receives 59 replies / 59 accepted; `build/quartus-stage3-program.log`, `build/stage3-board-udp.log` |
| Physical animation / sustained FPS review | AWAITING USER CHECK | Automated source accuracy, captures and frame budgets pass; physical motion and input feel need interactive VGA review |

Synthesis reports 16 warnings and fitting four, as in stage 2; timing and
assembly have zero. Both full-renderer simulations have zero errors and 56
inherited Intel memory/IP warnings each. Transcripts and captures are in
`build/`. The CPU-reference pose sheet and evaluated OBJ exports are in
`build/game/animation-diagnostics/`; they are not hardware framebuffer captures.

The animation image was programmed at 09:00 local time. SOF SHA-256:
`fe94d8280ca63381826ae9592225a562f3846914f568cc0ea30ecc70250565cd`.
Boot binary SHA-256:
`fb58c1e4ea2e3b94aba951b41980be835803e00f9ded2f66bc81be40657ab8b7`.
The first immediate 300 ms UDP probe received no replies while the PHY link
settled; the subsequent one-second probe passed.

## Stage 2 following camera

Validated on October 8, 2026. Configuration and behavior are described in
[stage2-camera.md](stage2-camera.md).

| Check | Result | Evidence |
| --- | --- | --- |
| Model/controller/hardware preservation | PASS | Stage 1 authored RTL, player controller, terrain selection and actor/physics profile compare unchanged; all three pinned source checkouts clean |
| Host regressions | PASS | 35 tests, including 12 production-camera tests: filtering/look-ahead, jump rise, landing, slope, wall, close-back-wall overhead fallback, ceiling, map-edge fall/respawn, teleport, real bridge route and invalid profiles |
| RV32I audit / firmware | PASS | Five C source audits; final ELF `rv32i2p1`, no undefined symbols; 41,266-byte binary, `_bss_end=0xa158`, 20,136 bytes before the reserved 4 KiB stack |
| Assets / camera collision | PASS | 326 terrain + 212 actor triangles, five handles, 151 colors; unchanged 188 floors / 138 obstacles; all 326 terrain faces included in camera avoidance |
| Quartus map / fit / timing | PASS | 17,111 logic elements, 2,623,928 memory bits, 66 multipliers; CPU setup +0.746 ns, worst hold +0.109 ns; all 42 timing slacks positive and zero unconstrained paths |
| Final RAM image / assembly | PASS | Close-wall fallback changed camera preset data only; Quartus `--update_mif` processed `build/firmware.mif`, then assembly regenerated the SOF; zero update/assembly errors or warnings |
| Final `mario_stream_tb` | PASS | 33 actual CPU frames under backpressure; 4,668,629 cycles; movement/jump/landing, held/released jump, camera-coordinate jump rise and camera/pose reset |
| `soc_mario_bridge_top_tb` | PASS | Actual MII UDP -> RV32I move/jump -> 538 GPU triangles -> VGA frame 2 at 65.76080 ms simulated time; 45 / 141 visible Mario red pixels |
| Four-frame independent coverage | PASS | Standing/jumping at spawn and bridge, using captured camera/projection; zero interior sky gaps against both float and integer-projection references |
| GPU active-work budget | PASS | Spawn standing/jumping: 307,398 / 308,400 cycles (6.15 / 6.17 ms); bridge: 346,810 / 346,271 cycles (6.94 / 6.93 ms), excluding swap wait; below the 1,666,667-cycle 30 Hz budget |
| Final `soc_mario_top_tb` | PASS | Actual UDP move/jump -> CPU -> 538 GPU triangles -> VGA frame 2 at 65.76068 ms simulated time; 45 / 141 visible Mario red pixels |
| Physical FPGA programming | PASS | EP4CE115F29@1 through USB-Blaster [USB-0]; JTAG ID `0x020f70dd`, checksum `0x0163bf06`, zero errors/warnings; `build/quartus-stage2-program.log` |
| Physical UDP acknowledgement | PASS | Neutral input after programming: 17 replies / 17 accepted; `build/stage2-board-udp.log` |
| Physical camera / jump / sustained FPS review | AWAITING USER CHECK | Automated framing, terrain avoidance and GPU output pass; interactive physical VGA review is still needed |

Full synthesis/fitting report 16/four warnings respectively, as in stage 1.
The earlier validation sections below describe their historical firmware images.

The two final full-renderer tests report zero errors and 56 inherited Intel
memory/IP warnings each. Final CPU transcript: `build/mario_stream_tb.log`;
VGA transcripts: `build/soc_mario_top_tb.log` and
`build/soc_mario_bridge_top_tb.log`. Coverage: `build/game/diagnostics/coverage.json`.

Final SOF: 3,541,722 bytes, SHA-256
`47615d650d4aef868ffb709199fdc5a6bdbde0d15b10a667903351e929a529fc`.
Boot binary SHA-256:
`f3f30f9afb7aef2c73624cabf03bdb6f855338f5eca0566a6fc8984fc32193e9`.
The camera image is loaded on the board; controls retain the existing sender.

## Stage 1 connected-area image

Validated on October 8, 2026. The selected area is described in
[stage1-playable-area.md](stage1-playable-area.md).

| Check | Result | Evidence |
| --- | --- | --- |
| Source/model preservation | PASS | All three pinned checkouts clean; multiple source hashes/root counts and original winding recorded; no CPU/GPU/network RTL edits |
| Connected-area conversion | PASS | 326 terrain + 212 actor triangles, five handles, 151 palette colors; 188 floors / 138 obstacles |
| Host regressions | PASS | 23 tests; whole-triangle multi-root import, independent coverage winding, source-path/layer rejection and production-controller field-to-bridge walk/jump/landing/respawn route |
| RV32I audit / memory | PASS | Four C source audits; final ELF `rv32i2p1`, no undefined symbols; 25,338-byte Mario binary, `_bss_end=0x6320`, 36,064 bytes free before the reserved stack |
| `mario_stream_tb` | PASS | 33 real CPU frames under backpressure; 4,623,956 cycles; uploads once, moves/turns, jumps/lands, releases/re-jumps and respawns |
| `soc_mario_top_tb` | PASS | Real UDP move/jump, 538 GPU triangles, displayed frame 2 at 65.76086 ms simulated time; 51 / 109 visible red Mario pixels |
| `soc_mario_bridge_top_tb` | PASS | Same real CPU/GPU/UDP pipeline at the bridge fixture; standing/jump frame 2 at 65.76076 ms; 49 / 114 visible red Mario pixels |
| Source/GPU standing coverage | PASS | Spawn and bridge captures compared with independent world views; zero unexplained interior sky pixels against integer projection/sample coverage; three float-only boundary pixels at each view |
| GPU active-work budget | PASS | Spawn 331,566 cycles (6.63 ms); bridge 344,967 cycles (6.90 ms), excluding swap wait; both below 1,666,667 cycles for 30 Hz |
| Quartus map / fit / timing / assembly | PASS | Lite 18.1; 17,111 logic elements, 2,623,928 memory bits, 66 multipliers; CPU setup +0.746 ns, worst hold +0.109 ns |
| Physical FPGA programming | PASS | EP4CE115F29@1 configured through USB-Blaster [USB-0], checksum `0x014a43b2`; zero errors/warnings; `build/quartus-stage1-program.log` |
| Physical UDP acknowledgement | PASS | Neutral input after programming: 18 replies, 18 accepted; `build/stage1-board-udp.log` |
| Physical route / FPS review | AWAITING USER CHECK | Automated coverage and controller route tests pass; physical VGA gameplay and sustained FPS require an interactive check of the new image |

`build/quartus/SoC.sof` is 3,541,722 bytes; SHA-256:
`3a494ccae7184826ab4f019f8e8633976caf2b65051e708d028e0ff52eac0d54`.
Synthesis reports 16 warnings and fitting four; timing/assembly zero. Both
full-renderer tests have zero errors and 56 inherited Intel memory/IP warnings.
The earlier portable regressions below remain historical; stage 1 reruns the
changed controller/asset host tests and the three milestone simulations.

## Earlier controllable Mario image

Validated on October 8, 2026. The CPU/GPU/network RTL and pinned source models
are unchanged; this milestone adds firmware, asset profiles/adapters and tests.

| Check | Result | Evidence |
| --- | --- | --- |
| Source/model preservation | PASS | Clean pinned source checkouts; actor source hash and all 15 selected display lists recorded in `build/game/conversion.json`; rigid assembly preserves part vertices and winding |
| Combined asset build | PASS | 184 terrain + 212 original actor triangles, four mesh handles, 123 palette colors; 147 floor / 37 obstacle collision triangles |
| Independent asset outputs | PASS | Game generation does not invoke the viewer header generator or change its assets; repeated game generation produces identical data |
| Host tests | PASS | Nine production C controller/asset tests and ten converter/C-subset/UDP tests; slopes, walls, ceilings, jumps, landing, held-key behavior, fall/manual respawn and real terrain |
| RV32I audit / firmware | PASS | Controller, application and both graphics drivers audited; final ELF has no undefined symbols, architecture `rv32i2p1`; 19,012-byte Mario binary, linker reserves at least 4 KiB stack |
| Existing portable regressions | PASS | `soc_mmio_tb`, `soc_memory_tb`, `cpu_stream_tb`, `game_stream_tb`, `udp_controls_tb`, `scene_stream_tb` rerun successfully |
| `mario_stream_tb` | PASS | Actual RV32I executes 33 frames under decoder backpressure; one-time upload, move/facing, jump/landing, held jump, release/re-jump and respawn; 4,296,487 CPU cycles |
| `soc_mario_top_tb` | PASS | Real MII UDP move+jump packet reaches CPU; GPU submits 396 triangles and VGA presents/CPU acknowledges changed frame 2; 48.96086 ms simulated time |
| GPU frame captures | PASS | Actual post-depth framebuffer write ports captured standing/jumping PPMs; 48 / 113 visible red Mario pixels; PNG previews also saved in `build/` |
| Quartus synthesis / fit / timing / assembly | PASS | Lite 18.1 Build 625; unchanged 17,111/114,480 logic elements (15%), 2,623,928/3,981,312 memory bits (66%), 66/532 multipliers and 1/4 PLLs |
| Timing | PASS | 50 MHz CPU setup +0.746 ns; worst hold +0.109 ns; all setup/hold/recovery/removal slacks positive; zero unconstrained clocks/input/output paths |
| Physical FPGA programming | PASS | October 8, 2026: Quartus Programmer configured EP4CE115F29@1 through USB-Blaster [USB-0]; JTAG ID `0x020f70dd`, programming checksum `0x013d5360`, zero errors/warnings; `build/quartus-program.log` |
| Physical UDP link after programming | PASS | Neutral control test received 18 replies / 18 accepted packets from `192.168.7.2:4000`; `build/mario-board-udp.log` |
| Physical Mario VGA display | PASS (user photographs) | October 8, 2026: three supplied photographs show Mario and terrain on the monitor, with FPS030 / FPS030 / FPS029. Stills establish visible output, not sustained frame timing |
| Physical Mario movement / jumping / collision | NOT FULLY VERIFIED | Different views/facings are consistent with controls; photographs alone do not establish jumping, landing or wall/edge behavior. These still need an interactive board check |

Current `build/quartus/SoC.sof`: 3,541,722 bytes; SHA-256:
`9eea295920081a9ea612f39d12d739bf9469cbe0ba5977baabe6dfaeba9967de`.
Synthesis reports 16 warnings, fitting four, timing and assembly zero. The full
renderer simulation reports zero errors and 56 inherited Intel memory/IP warnings.

See [mario-controller.md](mario-controller.md) for reproduction and controls.
This is an original-model rigid-pose viewer with a reusable platformer controller;
original SM64 gameplay/animation, live game loading and texture sampling are not
implemented. Earlier full VGA regressions below remain historical evidence; the
six portable regressions and two new milestone RTL tests were run for this change.

## Earlier SM64 scene + UDP image

Validated on October 7, 2026 after adding the scene conversion pipeline and
CPU-directed UDP input. The earlier Catch baseline remains below for history.

| Check | Result | Evidence |
| --- | --- | --- |
| Pinned SM64 conversion | PASS | `sm64-port` at `2b17d081c9798b31b91dc71f37994b0da28cffc9`; 145 source positions, 164 chunk vertices, 184 triangles, 2 handles, 50 palette colors |
| Combined reusable command | PASS | `soc.py sm64-scene`; repeated conversion/audit/firmware/project generation produced the identical boot firmware hash |
| Host converter / C subset / UDP sender tests | PASS | Eight tests, including UDP loopback, neutral-state exit, unsupported C float/heap/division rejection and strict display-list lowering |
| RV32I C audit and linking | PASS | Scene + both graphics drivers; no undefined symbols in final ELF; architecture attribute `rv32i2p1`, 4,924-byte scene binary |
| Existing six CPU/MMIO/game/VGA regressions | PASS | All preserved after eight-bit inputs and network integration |
| `udp_controls_tb` | PASS | Real MII Ethernet/UDP bytes through upstream RX, async FIFO and decoder; CRC, stale/duplicate sequence, wrap, simultaneous keys, release, timeout and restart |
| `scene_stream_tb` | PASS | Real RV32I firmware uploads scene once; orbit/zoom/reset and mesh reuse under decoder backpressure; 522,521 cycles |
| `soc_scene_top_tb` | PASS | UDP input reaches board wrapper, CPU changes view, GPU renders 184 triangles with nonzero pixels and VGA presents/CPU acknowledges frame 3; simulation time 48.9608 ms |
| Quartus synthesis / fit / timing / assembly | PASS | Lite 18.1 Build 625; 17,111/114,480 logic elements (15%), 2,623,928/3,981,312 memory bits (66%), 66/532 multipliers and 1/4 PLLs |
| Timing constraints | PASS | 50 MHz CPU setup +0.746 ns; worst hold +0.109 ns; all setup/hold/recovery/removal slacks positive; zero unconstrained clocks/input/output paths; timing analyzer zero warnings/errors |
| Physical board rendering | PASS (user verified) | October 7, 2026: user supplied a photograph of the terrain displayed over VGA; FPS overlay reads 030 |
| Keyboard-to-board Ethernet | PASS (user verified) | October 7, 2026: user confirmed keyboard control works on the physical setup; exercises UDP input, RV32I camera updates and GPU/VGA rendering |

`build/quartus/SoC.sof` is 3,541,722 bytes; SHA-256:
`dc920faff14b7c9329add9b62be72639b3445615b2d0d9eca716a251447ff464`.
Synthesis has 16 warnings, fitting four, timing/assembly zero. Additional network
RAM inference warnings concern inherited asynchronous FIFO dual-clock memory;
its Gray-coded pointer synchronization and FIFO ownership are retained.

Reproduce with the commands in [sm64-subset.md](sm64-subset.md). Nine RTL
simulations and eight host tests pass. The scene image replaces the previous
Catch boot image; Catch and triangle remain separately selectable regressions.

## Earlier Catch baseline

Validated on October 7, 2026 with the exact upstream revisions in
`upstream.lock.json`.

| Check | Result | Evidence |
| --- | --- | --- |
| Dependency bootstrap / adapter generation | PASS | Both clean pinned checkouts; exact adaptation anchors matched |
| RV32I firmware build | PASS | Clang 21.1.6 + LLD + llvm-objcopy, `-march=rv32i -mabi=ilp32`, warnings treated as errors; board game, triangle, and accelerated game-test images |
| All scaffold and renderer RTL compilation | PASS | ModelSim Intel FPGA Edition 10.5b; zero compile errors |
| `soc_mmio_tb` | PASS | FIFO backpressure, full rejection, non-power-of-two wrap, simultaneous push/pop, W1C/event races, frame ID/counters, access validation, synchronized buttons, cycle timer, reset |
| `soc_memory_tb` | PASS | Word, signed/unsigned byte/halfword RAM, suppressed misaligned store, upper RAM boundary, unmapped fault, MMIO isolation, fetch bounds |
| `cpu_stream_tb` | PASS | Actual CPU runs C firmware; all five decoded command opcodes/payloads match under decoder backpressure; completion acknowledged in 7,377 cycles |
| `game_stream_tb` | PASS | Actual CPU runs 56 game ticks under command backpressure; scripted buttons verify left/right, simultaneous-button neutrality, limits, miss/catch feedback, block respawn and one-time mesh upload |
| `soc_top_tb` | PASS | Actual CPU, decoder, renderer, Intel memory models and VGA page swap; frame ID 1, one submitted triangle, nonzero pixels written, no errors; firmware acknowledges completion in 768,037 cycles |
| `soc_game_top_tb` | PASS | Actual game firmware, indexed-mesh renderer and VGA; two displayed/acknowledged game frames with four triangles and nonzero pixels each; 1,608,031 CPU cycles |
| Quartus project generation | PASS | Source manifest and board pin assignments generated |
| Quartus synthesis | PASS | Quartus Prime Lite 18.1 Build 625; zero errors; native CPU block RAM and direct VGA PLL reference |
| Quartus fitting | PASS | EP4CE115F29C7; 13,942 / 114,480 logic elements (12%), 2,604,536 / 3,981,312 memory bits (65%), 66 / 532 multipliers, 1 / 4 PLLs |
| Quartus timing | PASS | Fully constrained setup/hold; 50 MHz worst setup slack +1.339 ns, worst hold slack +0.166 ns; zero timing errors/warnings |
| Quartus assembly | PASS | Zero errors/warnings; generated `build/quartus/SoC.sof` with the Catch game firmware |
| Physical DE2-115 programming and display | UNVERIFIED | No board programming performed |
| Icarus / GNU compiler CI route | UNVERIFIED LOCALLY | Workflow supplied; portable tests were run with ModelSim and Clang locally |

The full VGA run reported zero errors and 56 warnings, principally upstream
Intel mixed-language memory-IP port connections. It uses the upstream behavioral
pixel-clock model rather than the synthesized PLL. Simulation establishes
functional integration. The separate Quartus run establishes resource fit and
positive timing slack under the supplied constraints; board behavior remains
unverified.

Synthesis reports 12 warnings and fitting reports four. Remaining messages cover
unused upstream verification signals, the control decoder's pre-defaulted case,
RAM pass-through logic, Lite-only feature availability, optional LED drive/slew
settings, the fixed VGA clock pin's non-dedicated routing and input-voltage
requirements. None prevents fitting or assembly. Timing analysis reports zero
warnings. The earlier expired evaluation message came from a separate Standard
Edition installation; the validated run uses Lite at
`C:\intelFPGA_lite\18.1\quartus\bin64`.

Two hardware integration errors were corrected in the generator: Quartus's native
macro now selects block RAM rather than the simulation initialization loop, and
the PLL gets a direct reference clock while the rasterizer retains the inverted
CPU clock. All six simulations were rerun after these changes in the relocated
project directory.

Reproduce the validated run:

```sh
python scripts/soc.py bootstrap
python scripts/soc.py build-fw
python scripts/soc.py sim --simulator modelsim --full
python scripts/soc.py quartus-project
quartus_map SoC
quartus_fit SoC
quartus_sta SoC
quartus_asm SoC
```

The equivalent reproducible helper is `python scripts/soc.py build-fpga`, with
`--quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"` to select the installed
Lite tools. Native stages work in the relocated folder; a separate Quartus Tcl
shell relative-flow invocation misnormalizes this machine's `Documents` path.
The generated native Flow Summary itself reports Successful.

Use the Lite edition tools for the Quartus commands. The validated local project
is `C:\Users\Orb1t\Documents\Codex\FPGA-Game-SoC\SoC.qpf`.

Simulator logs are generated under `build/`. The distributed archive includes
the authored scaffold and pinned dependency setup, excluding downloaded Git
checkouts, generated adapters, firmware binaries and simulator build directories.
