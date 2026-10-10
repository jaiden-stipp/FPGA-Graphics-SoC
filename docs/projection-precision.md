# GPU-001: projection precision correction

October 9, 2026. This is a rendering correctness change, not a measured game
performance optimization. Physical gameplay acceptance remains pending.

## Observation and reproduced defect

The user's `IMG_6537.mov` shows castle roofs and wall/opening shapes changing
as Mario and the camera move, including gaps exposing the sky. The clip does
not establish an unambiguous collision fall through a floor. The most recently
loaded software is the direct-terrain diagnostic described in
[TERRAIN-001](terrain-loading-diagnosis.md); whether that was the image during
the entire recording has not been independently captured.

The original GPU computes an integer reciprocal `floor(65536/z)`, then uses it
for both pixel projection and its eight-bit depth value. At typical castle
distances, small depth changes cross reciprocal thresholds and move vertices
many pixels. This is a confirmed arithmetic defect in the simulated renderer;
it is a plausible contributor to the recorded distortion, not proof that all
reported visual and collision faults have the same cause.

Measured example from the actual transform module:

| Vertex / depth (GPU units) | Original projected x | Integer reference x | Corrected projected x |
| --- | ---: | ---: | ---: |
| x = 4,000; z = 8,192 | 285 | 285 | 285 |
| x = 4,000; z = 8,193 | 269 | 284 | 284 |

The original output moves 16 pixels while the reference moves one pixel. These
are simulated pixel coordinates for a synthetic triangle, not VGA measurements
or FPS results.

## Reusable implementation

`scripts/soc.py generate()` adapts the pinned, clean upstream transform into
`rtl/generated/transform_3d_pipeline.sv`. The source selector includes the
adaptation and excludes the upstream module to prevent duplicate definitions.
The original renderer repository, game source models and asset conversion
remain unchanged.

- Compute `floor(16777216/z)` for a reciprocal with eight additional fractional
  bits (Q16.16 inverse depth for Q8.8 coordinates).
- Use signed 48-bit coordinate products and signed 64-bit focal products;
  shift by 24 for screen coordinates.
- Derive the existing depth value from reciprocal bits `[23:8]`, retaining the
  previous depth-buffer interface and quantization.
- Register the coordinate and focal products in separate stages. Preserve the
  command ABI, input coordinates, triangle output format, culling, clipping
  behavior and divider width. Both terrain submission modes and
  actor meshes use the corrected projection.

This does not improve depth-buffer precision, import missing source geometry,
add textures, or repair collision behavior. Wider arithmetic can affect FPGA
resources and timing; fitting and timing results must be checked before use.

## Simulation evidence

[Raw evidence](benchmarks/gpu-001/) records one baseline and one candidate run
of the same 26-case fixture, using ModelSim Intel FPGA Edition 10.5b. The
fixture covers both signs of x/y, reciprocal thresholds and near depths 257,
300 and 512; it checks the first projected vertex, retained color/depth, and
stable output under four cycles of backpressure per triangle.

| Metric | Baseline | Candidate | Method |
| --- | ---: | ---: | --- |
| Maximum first-vertex coordinate error | 16 pixels | 1 pixel | Compared against integer `floor(focal * coordinate / z)` reference |
| Fixture completion simulation time | 86,420 ns | 89,540 ns | Same test clock and transaction sequence, including reset/backpressure |

The pipeline adds two clocks per projected vertex. In this 78-vertex fixture,
that accounts for 3,120 ns of additional simulated time at a 20 ns clock period.
This is a correctness/timing tradeoff, not a throughput improvement claim.

The elapsed simulation time is a fixture result, not board latency, throughput,
game frame time, or maximum operating frequency. No percentage FPS improvement
is supported. Three transform benches pass: the precision regression, upstream
projection test and upstream near/viewport clipping test. The precision bench
also compiles and passes through the full SoC source-selection path. The
CPU-to-renderer-to-VGA smoke test passes, including completed-frame
acknowledgement and nonzero rendered pixels. Its first elaboration failed
because the older testbench omitted the existing `look_state` port; explicitly
tying that input to zero repaired the fixture. The failed log is retained.
Three host loader/package validation tests pass.

Reproduce the regression with ModelSim and upstream dependencies installed:

```powershell
.\scripts\run.ps1 soc.py bootstrap
.\scripts\run.ps1 soc.py sim --simulator modelsim --full --tests projection_precision_tb --work-dir build/projection-regression
```

For the baseline comparison, compile the original
`external/renderer/rtl/pipeline/transform_3d_pipeline.sv` in place of the
generated module and set `REQUIRE_ACCURACY=0`; this measures the defect without
terminating at the first reference error. The candidate's default
`REQUIRE_ACCURACY=1` rejects errors greater than one pixel in this fixture.

## Physical build and acceptance

The first, unpipelined candidate synthesized and fitted, but failed setup timing
with -2.437 ns slack at the constrained 50 MHz clock. The reported worst path
runs from `project_index` to `polygon_x` through projection arithmetic (22.735
ns data delay). It was not assembled or programmed. Its measured fitted totals
were 20,984 logic elements, 2,659,668 memory bits and 74 embedded 9-bit multiplier
elements; these are whole-SoC counts, not the projection's isolated resource
cost. Raw reports and source are preserved under
`benchmarks/gpu-001/rejected-unpipelined/`.

The final candidate separates the coordinate and focal products into registered
stages. Quartus Lite 18.1 Build 625 completed synthesis, fit, timing and assembly
successfully for EP4CE115F29C7. The constrained 50 MHz `CLOCK_50` setup slack is
+0.199 ns; the lowest reported slack across the summary's checks is +0.104 ns.
Fitted whole-SoC totals are 20,918 logic elements, 2,659,668 memory bits and
74 embedded 9-bit multiplier elements. No maximum physical clock rate or
isolated resource-cost claim is made from these results.

A separate `ProjectionSoC` project uses the same cache-enabled SoC, board pins,
timing constraints and initial firmware as `CacheSoC`, replacing only the
transform source and output directory. It writes
`build/quartus-projection/ProjectionSoC.sof`. The existing cache and original
SOF files are preserved for rollback. The candidate was successfully programmed
through USB-Blaster JTAG, then the same 27,832-byte direct-terrain CPU image and
883,124-byte asset image were uploaded and verified by readback. A completed
frame was reported with SDRAM initialized and the CPU released. This confirms
programming and startup, not the recorded route's visual or collision quality.

Programmed SOF SHA-256:
`8326b76009f681087f3615256ff45f7f7bb5922dc43dfebca2d77387f499105b`.
Preserved cache-image rollback SOF SHA-256:
`bc0948f73f1ff97f71d36411eb62e376d485d9559d8d6aa46d0f9d84cd596927`.
The corrected image and direct-terrain diagnostic are currently running;
the user's visual comparison remains pending. No new physical FPS result was
measured.

Use `ProjectionSoC.qpf` to open the corrected project in Quartus. For the normal
generated project, rerun `soc.py quartus-project` after `soc.py bootstrap` so
the QSF selects the generated transform. Older ignored QSF files can retain
the upstream transform reference; the saved rollback SOF remains unchanged.

After programming, compare the same route and camera movement with the direct
diagnostic package first. Then re-enable resident terrain mesh submission and
repeat. Record any remaining gaps separately from collision failures. A physical
fix claim requires that comparison, not just a completed frame counter.

Supported resume wording is currently limited to implementation and simulation:

> Corrected fixed-point perspective projection in an FPGA renderer, reducing
> maximum coordinate error from 16 to 1 pixel across a 26-case simulation
> regression while preserving the graphics protocol and depth-buffer interface.

This wording must retain the fixture and simulation qualification. It is not
a claim that a complete game port or its physical rendering is verified.
