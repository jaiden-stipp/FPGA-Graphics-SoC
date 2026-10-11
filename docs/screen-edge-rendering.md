# Screen-edge rendering investigation

Measured October 10, 2026. Source baseline `c3df05d`. Two bounded rendering faults were reproduced and corrected. **The user's large missing regions have not been reproduced or visually accepted.** The corrected image and normal unprofiled Mario package are loaded on the DE2-115 after readback verification.

## What changed

`firmware/src/world.c` previously used a 12-bit clipping fraction. A large triangle crossing the near and side planes lost ten interior left-edge probes. The fraction now uses 16 bits, and interpolation splits the signed difference so that low-32-bit multiplication gives exact floor-rounded interpolation without 64-bit helpers or MULH. Existing projection, camera, source meshes, collision, game behavior and package interface are preserved.

The GPU's eight-fraction-bit depth gradients could round an interior depth below the smallest vertex depth. In the reproduced distant triangle, one covered pixel became zero and failed against the cleared depth buffer. The generated renderer now clamps interpolated depth to its triangle's vertex extrema. This preserves the affine interpolation bounds without adding pipeline stages. It does not increase depth-buffer precision or solve every depth/occlusion artifact. Pinned external RTL is unchanged; `scripts/soc.py` reproducibly generates the corrected renderer for all full builds.

## Verification and limits

- Native production clipping: three tests pass, including exact signed interpolation, the preserved authored regression, and 300 seeded crossing triangles. The seed-501 corpus loses interior coverage in one triangle before and zero after.
- Actual castle data: 680 constructed camera poses across all five areas, 1,125,808 triangle/pose cases, 66 edge probes with a two-pixel interior reference margin. Zero missing probes before and after. These are constructed surface poses, not a recorded gameplay route, and this test excludes GPU depth and frame submission.
- Actual GPU rasterizer: the distant triangle changes from 2,801 written / 2,802 covered pixels to 2,802 / 2,802; depth rejection changes from one to zero against a cleared buffer.
- Three full-viewport fixtures each cover all 76,800 pixels before and after; the projection-precision regression also passes. These do not exercise an entire moving game frame.
- Existing world, terrain-offload and portable-pipeline host tests: 47 pass. Firmware subset and emitted-instruction checks pass.

## Physical comparison

Three standing animated spawn trials per configuration, identical immutable assets, 50 MHz. Each profile is an atomic completed-frame snapshot. Timers include instrumentation and overlapping scopes; do not sum them as serial costs. This compares both corrections together, not an isolated hardware optimization. All trial values and matched-frame details are preserved in the evidence JSON.

| Metric | Before median | After median | Change |
| --- | ---: | ---: | ---: |
| CPU render ms | 18.91756 | 19.14806 | +1.218% |
| Command cycles | 294210.00000 | 281882.00000 | -4.190% |
| Clipping cycles | 202336.00000 | 231076.00000 | +14.204% |
| Observed FPS | 29.87664 | 30.06206 | +0.621% |

All paired snapshots are frame 251 at the same player position, with 242 commands and 7,011 command bytes. Raster event counts change because clipped coordinates and depth behavior change; command timing therefore cannot be attributed solely to hardware. Separate fraction/intersection counters were not enabled in these packages. More precise CPU clipping is a correctness tradeoff; no FPS speedup is claimed. Host-observed FPS includes sampling jitter and the existing presentation cadence.

## Fitting and timing

| Measure | Preserved IntegerMulSoC | ScreenEdgesSoC |
| --- | ---: | ---: |
| Logic elements | 21,640 | 21,754 |
| Memory bits | 2,659,668 | 2,659,668 |
| Embedded 9-bit multipliers | 80 | 80 |
| PLLs | 2 | 2 |
| CLOCK_50 slow 85C setup slack | +0.468 ns | +0.365 ns |
| Worst hold slack | +0.115 ns | +0.091 ns |

All reported candidate setup, hold, recovery, removal and pulse-width checks have positive slack. Resource change is +114 logic elements, with unchanged RAM/DSP/PLL counts. These are fitted static timing estimates, not measured maximum frequency or power.

The first attempted profile ran against an unidentified non-MUL FPGA image and failed the firmware feature guard (`0xdead00c2`). It produced no valid trials. That failure is preserved separately. Both measured configurations were subsequently programmed explicitly with logged successful Quartus operations and identified bitstream hashes.

## Reproduction

Run from the repository root with LLVM, ModelSim and Quartus available:

```powershell
python scripts/test_screen_edges.py
$env:PYTHONPATH = 'scripts'
python -m unittest test_world_pipeline test_terrain_offload test_portable_pipeline
python scripts/soc.py sim --full --simulator modelsim --tests depth_edge_coverage_tb,screen_edge_coverage_tb,projection_precision_tb --work-dir build/screen-edge-simlib
python scripts/diagnose_screen_edges.py
python scripts/soc.py portable-game --project build/castle/game.project.json --terrain-direct --integer-mul
python scripts/soc.py portable-game --project build/castle/game.project.json --terrain-direct --integer-mul --profile-detail
```

The castle diagnostic requires the preserved baseline `before-world.c` and existing local `build/castle/world.json`; game assets are not embedded in this report. `benchmarks/screen-edges-001/build-candidate.py` preserves the candidate build recipe and exact project QSF. Local deployment uses `build/quartus-screen-edges/ScreenEdgesSoC.sof` and `build/mario-castle-sdram-direct-mul.package.json`. Baseline firmware copies remain under `build/screen-edges/baseline`.

## Remaining acceptance

Walk the previously failing edge views on the loaded candidate. If large regions still disappear, capture the camera/area/player state and replay the complete submitted frame through the GPU with a framebuffer/depth comparison. Neither the sparse castle probes nor these targeted corrections establish that streaming, culling, near-plane camera cases, or full-frame depth ordering are correct. Avoid further performance changes until that visual fault has a deterministic full-frame reproduction.

[Raw results, source snapshots, build/programming logs and artifact hashes](benchmarks/screen-edges-001/measurements.json).
