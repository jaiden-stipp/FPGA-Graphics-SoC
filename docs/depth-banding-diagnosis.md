# DEPTH-001: camera-dependent ground bands

On October 9, 2026, the user supplied an image showing broken green/gray bands
across terrain and confirmed that they change with camera movement.
The screenshot alone cannot identify the exact competing source faces or the
loaded bitstream. A deterministic simulation reproduces a matching class of
striped artifact in the production rasterizer without SDRAM or a CPU.

## Confirmed arithmetic defect

`external/renderer/rtl/pipeline/renderer.sv` converts 8-bit vertex depth to a
fixed-point value with eight fractional bits. It calculates X/Y depth slopes
using integer division, truncating each slope, then advances depth by adding
those rounded slopes. The starting value is anchored to vertex zero.

For mathematically identical geometry, rotating the vertex order changes that
anchor. Accumulated rounding error makes the two triangles disagree about
depth. `depth_test_stage.sv` accepts a pixel only when its depth is strictly
greater than the stored value. Flooring the interpolated value to eight bits
turns the small disagreement into alternating regions of accepted/rejected
pixels, producing stripes. Camera motion changes projected coordinates and
depths, so the bands move.

The existing projection correction increases screen-position precision; it
intentionally preserves the 8-bit depth interface and does not correct this
rasterizer arithmetic.

## Actual RTL reproduction

The fixture draws these screen-space vertices:

| Vertex | X | Y | Inverse-depth byte |
|---|---:|---:|---:|
| A | 20 | 20 | 10 |
| B | 300 | 40 | 15 |
| C | 40 | 220 | 30 |

First draw: A/B/C, gray. Second draw: C/A/B, green. Both draws are exactly the
same triangle, including winding and per-vertex depth. With consistent depth
interpolation and the existing strict comparison, the second draw should write
zero pixels. The actual rasterizer writes **27,831 pixels** on the first draw
and incorrectly overwrites **8,690 pixels** on the second.

Both draws compute truncated fixed-point depth slopes X=2, Y=25. Moving the
anchor from A to C introduces an offset of
`(30-10)*256 - 20*2 - 200*25 = 80` fractional depth units. After eight-bit output
quantization, only parts of the triangle pass the depth comparison. The archived
PNG visibly shows parallel, broken green/gray bands.

ModelSim 10.5b compiled and ran the actual upstream `renderer`,
`depth_test_stage`, and `iterative_signed_divider` modules. The fixture uses a
one-cycle behavioral depth memory matching the interface latency; it does not
instantiate physical M9K RAM, the transform pipeline, VGA scanout or game data.
The result proves the rasterizer mechanism, not the identity of the two surfaces
in the user's photograph. It is a correctness observation, not a performance
measurement or a physical-board fix.

## Why castle terrain exposes it

The GPU vertex depth remains `floor(65536 / camera_z)` and the depth buffer
stores only eight bits. Many distant surfaces therefore have equal or nearly
equal depth. Castle conversion also declares
`texture alpha/decal appearance rendered solid; geometry retained`
(`scripts/sm64_castle.py`), so overlapping authored layers can become solid
flat-color surfaces competing for depth. These are contributing conditions;
the exact failing game triangles have not yet been captured.

## Next correction

Make interpolation consistent across vertex orders and increase fractional
precision before truncating at the final depth test. Add a regression requiring
zero overwrites for this identical-triangle fixture, including cyclic orders
and opposite depth slopes. Then assess wider stored inverse depth and explicit
decal/layer semantics for genuinely overlapping surfaces. Increasing just the
buffer width does not remove anchor-dependent interpolation error, and changing
the comparison from `>` to `>=` does not solve it either.

No hardware source or FPGA programming changed in this investigation. Any
candidate correction still needs simulation, Quartus resource/timing checks,
and a board comparison before acceptance.

## Evidence and reproduction

`benchmarks/depth-001/` contains the testbench, runner, raw compile/run logs,
rendered PNG, module snapshots, and hash manifest. From the repository root,
with the project's generated protocol includes available:

```powershell
$depthPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
# Restore the fixture to the path used by the archived runner:
Copy-Item docs/benchmarks/depth-001/depth_banding_tb.sv build/depth_banding_tb.sv
New-Item -ItemType Directory -Force build/depth-banding | Out-Null
& $depthPython docs/benchmarks/depth-001/run_depth_banding.py
```

The runner uses the installed ModelSim path under `C:/intelFPGA/18.1/` and
produces `build/depth-banding/depth-banding.ppm`. It is deliberately a diagnostic
that expects the current defect; a future regression should require its absence.
