# Original SM64 engine slice: implementation and measurement record

Measured on the DE2-115 on October 13, 2026. Comparison baseline: `45370e4`.

This experiment runs a scoped set of original Mario actions and collision functions on the RV32I CPU using software floating point and the existing SDRAM-execution hardware image. It is an engine slice, not a complete SM64 port. The selected castle demo was restored after every physical validation pass.

## Measurement correction

The first diagnostic omitted writes to `SOC_CPU_SNAPSHOT`. CPU cycle, retired-instruction, freeze, and dependency-bubble registers expose latched snapshots, so that run read stale zeros. Those zeros are invalid timing data. The counters were already running; the earlier explanation that they were not enabled was incorrect.

The corrected diagnostic triggers a snapshot before and after each update and rejects zero cycle or retired-instruction deltas. The second physical pass produced the valid counters below. Both passes are retained separately in `docs/benchmarks/sm64-engine-slice-001/`; the first is labelled **state only, invalid CPU timing**. No performance conclusion uses its zero counters.

Earlier raw frame-sample records also called the sample “idle.” Input was not forced neutral, so that label was too strong. These are short live frame-production samples only. The raw records remain intact; this correction supersedes that label. No sustained FPS improvement or regression is claimed.

## What runs

SM64 source is pinned by `sm64.lock.json` to `2b17d081c9798b31b91dc71f37994b0da28cffc9`. The target compiles unchanged original translation units for Mario action initialization, stationary/moving/airborne actions, Mario stepping, collision queries, surface loading, math, and animation frame advancement. Linker garbage collection removes functions outside this slice.

`firmware/engine/engine_adapter.c` supplies the platform state, input mapping, and an explicit 26-action dispatch. It covers idle, walking, braking/turning, jumps, falling, landing, sleeping/waking, and selected sliding states. Initialization is scoped and does not reproduce the entire original level startup. Unsupported actions, warps, and unavailable object services report a fault instead of silently substituting custom gameplay.

`surface_adapter.c` loads original castle-grounds vertices, surface types, forces, and water regions through the original surface-loader functions. The board measured 879 surfaces and 3,237 surface nodes, using 80,376 bytes of surface-pool storage. That pool is included in BSS; do not add it again when calculating total RAM.

All 209 original Mario animation descriptors, values, and indices are loaded for original engine animation timing. The visual renderer still selects its existing six imported clips; original visual animation integration is incomplete. The camera remains the existing camera adapter. Audio and cosmetic effects are omitted, and the existing HUD is a traversal fixture, not original save progress. Objects, missions, full action dispatch, original Lakitu camera, save state, swimming, and complete level transitions remain future work.

`firmware/ports/castle_engine.c` is an opt-in port through the existing shared game project, scene IR, package, input ABI, and renderer. The default castle port remains selected. The integer renderer subset checker is retained; original floating-point engine code is compiled through an explicit separate adapter. Final ELF instruction auditing permits only implemented RV32I instructions and low-result integer MUL, and rejects unresolved runtime symbols.

Berkeley SoftFloat 3e provides compiler arithmetic/conversion helpers and square root. Its archive and cached source files are hash locked in `softfloat.lock.json`. This adds no hardware FPU. Its 8086-SSE specialization is not a claim of exact N64 FPU exception/NaN behavior.

## Actual hardware and executable layout

No RTL or clock change was made for this experiment. The previously fitted candidate was reused:

| Image | SHA-256 |
| --- | --- |
| Experimental `SdramExecSoC.sof` | `140fa00e9d66def31e6897be29bc927469de72a9a051481186f7d7b2bc30be15` |
| Restored selected `ArchStage5SoC.sof` | `e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14` |

The candidate CPU exposes SDRAM execution plus integer MUL and geometry-worker features. Its main configured clock is 50 MHz. Time conversions below use that configuration; there was no external frequency calibration. Existing timing reports are checked before programming, not presented as new hardware improvements.

Rendered experimental package sizes come from linked ELF symbols and hash-verified binary segments:

| Region | Bytes | Address |
| --- | ---: | --- |
| Local boot | 1,744 | `0x00000000` |
| SDRAM executable | 81,960 | `0x80000000` |
| Initialized static state | 22,748 | `0x81000000` |
| Zero-initialized static state (BSS) | 91,860 | `0x810058dc` |
| Assets | 1,479,080 | `0x8101bfc0` |

Static runtime state is therefore **114,608 bytes**, calculated as initialized state plus BSS. Assets include the existing five-area package and original animation data, although original-engine traversal in this experiment is grounds only. These sizes are not the footprint of the entire SM64 engine or game.

Local RAM was painted before first stack use. The rendered pass observed **824 bytes** of stack high water after startup and a short live rendering sample. The diagnostic observed **616 bytes**. Neither is a worst-case stack bound for a complete level or full engine. This slice uses static allocations and no heap.

## Valid controlled diagnostic

The fixed 96-update replay starts at `[-1328, 260, 4664]`: eight idle updates, twelve forward updates, seven forward-plus-jump updates, fifteen forward updates, then idle through update 96. Updates are unpaced. Camera rendering, GPU submission, object updates, and full original camera logic are excluded.

The FPGA's raw XYZ floating-point bits, action IDs, and fault fields matched the native C replay on **all 96 updates**; there were no faults. This is comparison to the native build of the same scoped adapter and source functions, not validation against an N64 console replay.

| Counter delta per instrumented update | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: |
| CPU cycles | 21,163 | 21,685 | 106,813 |
| Retired instructions | 7,003 | 7,165 | 39,738 |
| Combined memory/fetch freezes | 12,153 | 12,452 | 56,560 |
| Dependency bubbles | 74 | 79 | 245 |
| Instruction-cache misses | 558 | 574 | 2,749 |

Calculated at the configured 50 MHz, median and maximum update intervals are **0.4337 ms** and **2.13626 ms**. Initialization used **9,619,085 measured cycles**. The counter interval includes snapshot/read instrumentation, and trace writes between intervals can influence the next update's cache state. This is not a measurement of naked function execution. The freeze counter combines instruction-fetch and data-memory stalls; it does not separate them.

The worst interval in this route is below a 30 Hz update budget, but that does not establish the cost of full object, camera, animation, mission, or rendering work. There is no measured before/after speedup claim for this software port.

## Rendered sample and interpretation

The rendered package advanced its frame counter from 50 to 80 in one short host-timed sample. The restored demo advanced from 113 to 173 in its sample. Input was uncontrolled, and the builds use different execution placements and scoped behavior. These samples verify progress after upload and restore; they are not a controlled performance comparison.

One held-memory read observed `game_update_cycles=186283`, `game_cpu_cycles=1023729`, and `game_frame_cycles=1667440`. These are raw last-frame fields from the live rendered sample, not the controlled diagnostic's per-update counters. They must not be substituted into its distribution.

The scoped engine fits in the existing SDRAM execution arrangement and its controlled replay runs successfully. The next software priority is integrating original object interactions and visual animation, then expanding actions/camera/area transitions with fixed route tests. These results do not justify requiring a hardware FPU before that work, and do not prove the entire game will fit or meet frame-rate targets.

## Reproduce

Use the pinned SM64 asset source already required by the project, LLVM, and the existing SDRAM-execution candidate. From the repository root:

```powershell
$env:PATH = 'C:\Program Files\LLVM\bin;' + $env:PATH
.\scripts\run.ps1 sm64_engine_slice.py diagnostic
.\scripts\run.ps1 test_sm64_engine_slice.py
.\scripts\run.ps1 sm64_engine_slice.py game
.\scripts\run.ps1 verify_sm64_engine_slice.py
```

The verifier programs the experimental image and uploads/readback-verifies each binary segment, reads diagnostic state/counters, samples frame progress, then restores the selected image and exact selected package in `finally`. It reports restoration failures explicitly. Physical checks require the DE2-115, USB-Blaster, and its UDP loader. `--diagnostic-only` and `--game-only` separate the two measurement scopes. Save each output record before rerunning, since the working record filename is reused.

`test_sm64_engine_slice.py` checks replay/reset, surface counts, all animation IDs, selected SoftFloat arithmetic against an independent finite-number reference, integer helper boundaries/random cases, and original function-call closure. This is not complete IEEE or complete SM64 conformance testing. The native Windows build removes unreferenced function definitions to satisfy COFF linking, retaining unchanged bodies; that source closure and its function-body hashes are archived.

Raw evidence, exact experimental package segments, build manifests/maps/ISA audits, native replay, source provenance, regression logs, and a SHA-256 manifest are archived under `docs/benchmarks/sm64-engine-slice-001/`.

References: [original SM64 port source](https://github.com/sm64-port/sm64-port), [Berkeley SoftFloat documentation](https://www.jhauser.us/arithmetic/SoftFloat.html).
