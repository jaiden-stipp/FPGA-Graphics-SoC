# Integer MUL: MUL-001

Implemented and measured October 10, 2026 on the physical DE2-115. A controlled original-idle-pose castle fixture reduces CPU rendering from 1,678,270 to 945,783 cycles: 33.56540 to 18.91566 ms at the configured 50 MHz, a calculated 43.645% reduction. Normal animated standing gameplay measures approximately 30 FPS with MUL, versus approximately 20 with software multiplication. These are bounded castle-demo results, not complete-game or arbitrary-scene performance guarantees.

## Implementation

The pinned upstream CPU remains unchanged. `scripts/soc.py` generates `soc_ControlUnit.sv` using full funct7 decoding. Opcode 0x33, funct7 0x01, funct3 0 selects MUL through ALU control 0xB. `rtl/soc_alu.sv` multiplexes the low 32 bits of a 32-bit integer product with the existing RV32I ALU result. Signed and unsigned products have identical low 32 bits. Overflow wraps; no saturation or floating point is introduced.

MUL executes within the existing EX cycle and feeds the normal EX/MEM register, forwarding paths and writeback. No new pipeline hold or arithmetic wait counter is required. Existing memory freezes hold the instruction and operands, and advancement-qualified retirement prevents double counting. Destination x0 retains the existing register-file suppression and trace semantics: the trace can report write intent, but x0 remains zero.

Other M-family instructions suppress register writes instead of aliasing ADD/shift/etc. The CPU has no new illegal-instruction trap implementation. This adds MUL only, not full RV32M or the complete Zmmul extension.

MMIO `0x4000009C`, bit 0 advertises MUL. Portable firmware built with `--integer-mul` checks this before using multiplication and stops with scratch `0xDEAD00C2` on incompatible hardware. Default builds retain the original software `fixed_mul`. The opt-in implementation emits exactly the MUL instruction through `.insn` inline assembly while the compiler remains targeted at RV32I. Every MUL-enabled firmware build audits executable M-family encodings and rejects multiply-high/division instructions. Package metadata records the required feature, and `.isa.json` records the MUL addresses. The measured normal detail build has 43 MUL encodings.

This optimization is available to any compatible portable game adapter through `fixed_mul`; imported geometry, animation channels, collision data and GPU commands are unchanged. It does not accelerate separate software division routines or automatically replace every C multiplication expression.

## Validation

`cpu_mul_tb.sv` executes the real CPU pipeline on 134 operand pairs, including zero, negative representations, INT_MIN and wrapping products, plus randomized pairs. It verifies dependent MUL/ADD forwarding, consecutive dependent multiplication, load-use hazards, x0, taken-branch flushing, unsupported M write suppression and 16 memory-freeze cycles with exact retirement counts. `cpu_counter_pipeline_tb`, `soc_mmio_tb` and `cpu_stream_tb` also pass.

The physical arithmetic probe checks 256 operand pairs in each of three runs. All products agree with an unsigned shift/add reference; the aggregate hash is 3,347,174,586, also reproduced independently with Python unbounded multiplication reduced modulo 2^32. Timed loops read the same local-RAM operand set and store results, with validation/hash calculation outside the timers. All three runs record 2,564 cycles for MUL and 75,343 for software shift/add. Their ratio is approximately 29.385, but this is a local-RAM arithmetic kernel, not the game speedup or a measurement of the original signed `fixed_mul` routine's isolated cost.

Active portable builds pass the specialized C audits. All five measured game variants preserve the original 883,124-byte asset segment, SHA-256 `afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`. Loader readback verifies uploaded CPU and asset bytes. Existing rendering/collision issues are not claimed fixed.

## Controlled game comparison

The first normal-game comparison sampled different animation poses because frame rates changed. To avoid treating those as identical work, a separate compile-time `CASTLE_PROFILE_FIXED_POSE` fixture holds the original idle start pose. Physics, camera and tick scheduling remain active. Normal builds do not enable this fixture.

Both versions run on the same MUL-enabled FPGA image, with the same detailed profiling timers, standing spawn position (-1328, 260, 4664), original model data and direct terrain path. Three trials per configuration capture one completed-frame profile after warmup and a roughly five-second frame-progress window. Differences include the MUL instruction use and associated compiler inlining/code layout, not just replacing one ALU operation in a fixed instruction stream.

| Fixed-pose CPU section | Software cycles | MUL cycles | Software ms | MUL ms |
|---|---:|---:|---:|---:|
| Terrain transforms/outcodes | 732,785 | 317,172 | 14.65570 | 6.34344 |
| Triangle classification/clipping | 297,740 | 202,327 | 5.95480 | 4.04654 |
| Animation joints | 107,946 | 20,113 | 2.15892 | 0.40226 |
| Animation vertex posing | 160,169 | 35,542 | 3.20338 | 0.71084 |
| Chunk selection | 11,348 | 4,443 | 0.22696 | 0.08886 |
| Entire CPU render phase | 1,678,270 | 945,783 | 33.56540 | 18.91566 |

Table values are medians of the three snapshots. Scope definitions and timer overhead remain as documented in [render function profiling](render-function-profiling.md); transforms include outcodes and clipping includes classification/copies/intersections. They are not isolated multiplication timings.

All six controlled snapshots match these GPU event counts: 444 submitted triangles, 6 clipped, 185 culled, 264,023 bounding-box pixels, 91,151 inside pixels, 6,154 depth rejects and 84,997 written pixels. They also match 7,011 bytes, 242 commands and 294,210 command-submission cycles, with zero FIFO wait span. Matching event counts strengthen the identical-work comparison but do not substitute for a framebuffer checksum or full traversal test. Frame IDs differ (167 versus 251) because the pose fixture deliberately decouples render work from frame rate. Update has two catch-up ticks in software snapshots versus one in MUL snapshots; do not report the entire update-phase difference as a per-tick speedup.

| Case, three trials each | Median observed FPS | Median CPU render ms |
|---|---:|---:|
| Fixed-pose software | 20.046 | 33.56540 |
| Fixed-pose MUL | 29.975 | 18.91566 |
| Normal animated software, detailed profile | 19.915 | 33.59120 |
| Normal animated MUL, detailed profile | 29.791 | 18.91746 |
| Normal animated MUL, unprofiled | 29.969 | Not an atomic render profile |
| Moving MUL diagnostic | 29.877 | 21.26354 |

Normal standing snapshots have different animation poses and modestly different GPU event counts; use the fixed-pose fixture for the controlled cycle-reduction claim. The moving route is wall-clock controlled and has differing endpoints, so no movement speedup percentage is claimed. Unprofiled globals can refer to different frames; their values remain raw evidence rather than precise phase comparisons. These short windows do not establish performance throughout the castle or eliminate frame-time variation. The configured simulation tick remains 1,666,667 clocks, approximately 30 Hz.

## Fitted hardware cost and timing

The resource baseline is the existing counter-enabled FPGA image, not the older image without observability counters. Both use the same 32-byte burst cache and board clocks.

| Whole-SoC fitter metric | Counter baseline | MUL candidate | Difference |
|---|---:|---:|---:|
| Logic elements | 21,564 | 21,640 | +76 |
| Memory bits | 2,659,668 | 2,659,668 | 0 |
| Embedded multiplier 9-bit elements | 74 | 80 | +6 |
| PLLs | 2 | 2 | 0 |

Quartus Lite 18.1 placement/routing and all reported timing checks pass. Candidate CLOCK_50 setup slack is 0.468 ns; minimum reported summary slack is 0.115 ns. These are slack measurements at existing constraints, not maximum frequency or power measurements. The single-cycle EX implementation therefore remains in the accepted candidate; no multi-cycle alternative was needed for this fit.

## Reproduction and deployed state

```powershell
.\scripts\run.ps1 soc.py bootstrap
.\scripts\run.ps1 soc.py sim --simulator modelsim --tests 'cpu_mul_tb,cpu_counter_pipeline_tb,soc_mmio_tb,cpu_stream_tb'
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --integer-mul
.\scripts\run.ps1 soc.py quartus-project
```

The generated `SoC.qpf` includes the new ALU and decoder dependencies. The isolated measured build is `build/quartus-integer-mul/IntegerMulSoC.sof`; its archived build helper reconstructs the exact template/source list and rejects failed timing. Add `--profile-detail` to build the atomic function-profile package. The archived fixed-pose helper builds the two controlled benchmark variants from the same generated assets; it separately audits the active castle fixture configuration.

Load the normal package on compatible MUL hardware:

```powershell
.\scripts\run.ps1 load_game.py build/mario-castle-sdram-direct-mul.package.json --status
```

The candidate FPGA and normal animated, unprofiled MUL Mario are currently loaded. The final experiment verifies advancing frame status after restoration from the fixed-pose fixture. Original FPGA/game artifacts remain available for rollback; experiment failures restore a known working configuration. FPGA configuration remains volatile across board power loss.

Candidate SOF SHA-256: `84de9a3059e5a40957438df348da434c05e462955e60528491f2f2ac6713484b`. Baseline source: `af8580f`; MUL RTL: `8aa373b`; permanent opcode audit: `122bed3`; matched physical arithmetic loops: `cdf0f8c`; fixed-pose fixture: `762895b`. Exact CPU/package hashes, all trials, source snapshots, fitted reports, disassembly, probe reference and programming logs are retained in [measurements.json](benchmarks/integer-mul-001/measurements.json). Asset binaries and SOF files remain local; their hashes identify them. Copy archived build helpers to the repository root's `build` directory before running them there.

Resume-safe wording: "Added integer MUL to a five-stage RV32I FPGA SoC, preserving forwarding and memory-stall correctness; measured a 43.65% reduction in CPU render cycles on a controlled castle fixture and approximately 20 to 30 FPS in a standing game demo, with +76 logic elements and +6 embedded 9-bit multiplier elements at passing 50 MHz timing."
