# Stage 1: starting field, path and bridge

The Mario boot profile now imports original opaque geometry around a connected
route from the original Bob-omb Battlefield spawn to the wooden bridge. CPU,
GPU, Ethernet RTL, graphics protocols and upstream model files are unchanged.
The standing pose and controller are retained. This does not import the complete
game, original collision semantics, textures or animation.

## Reproduce

```powershell
.\scripts\run.ps1 soc.py sm64-mario --sim --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
.\scripts\run.ps1 test_player.py
.\scripts\run.ps1 test_scene_pipeline.py
.\scripts\run.ps1 diagnose_game.py
```

Open `SoC.qpf` in the project folder and program `build/quartus/SoC.sof`.
WASD/arrows, Space and R still mean movement, jump and respawn.

## Import policy and area

`profiles/sm64-bob-playable.json` resolves the four opaque roots from their four
original C files before applying any normalization. The retained source-space
box is X `[-8192,2048]`, Y `[-384,4295]`, Z `[-1500,8193]`. Whole original
triangles whose bounds intersect that box are selected. Their vertices, order,
winding and topology are preserved; there are no filler or clipped triangles.
Large touching triangles extend outside the box, so its border is a selection
guarantee rather than a perfectly cut map boundary.

The six level roots contain 1,043 opaque triangles and 58 alpha/decal triangles.
Stage 1 selects 326 opaque triangles, compared with the previous single-root
184-triangle terrain. Decorative alpha/decal roots are explicitly omitted;
using them as solid collision surfaces would be incorrect. Distant mountain
geometry is outside this milestone. Every texture has a declared flat color;
the new stone/structure policies are approximations rather than extracted texels.

| Opaque root | Source triangles | Selected triangles |
| --- | ---: | ---: |
| `bob_seg7_dl_07004390` | 184 | 90 |
| `bob_seg7_dl_07009D80` | 473 | 160 |
| `bob_seg7_dl_0700DD18` | 354 | 76 |
| `bob_seg7_dl_0700E338` | 32 | 0 |

Four tiny triangles collapse if all opaque level geometry is quantized to the
old 2048-unit extent. They are diagnosed during strict conversion rather than
silently removed. The selected area uses a uniform 4096-unit extent to preserve
its small source triangles. Collision is generated from the exact displayed
quantized triangles: 188 floors and 138 obstacles. Original SM64 collision
metadata remains a separate future import.

The combined terrain and Mario use 538 triangles, 5/16 handles and 151/256
palette entries. The board ELF ends its BSS at `0x6320` (25,376 bytes), leaving
36,064 bytes before the reserved 4 KiB stack. The original spawn maps to
`[-1576,-208,1616]` and has capsule-sized floor support.

## Route and geometry checks

The native regression executes the production integer C controller through
source-space X/Z waypoints:

1. Original spawn `[-6558,6464]` to `[-6558,7000]`.
2. Across the starting field to `[-2000,7000]`.
3. Toward the path at `[-2000,5632]`.
4. Onto the bridge approach at `[-1100,5632]`.
5. Across the original sloping wooden bridge to `[1200,5632]`.

It checks support on every movement tick, jump and landing at every waypoint,
no fall/respawn on the route, and manual return to the declared spawn. Other
production-controller fixtures exercise wall sliding, ceilings, slope movement,
falling and respawn. These are controller checks, not claims of full SM64 physics.

`soc_mario_top_tb` and `soc_mario_bridge_top_tb` run actual RV32I firmware,
MII/UDP input, GPU rendering, depth writes and VGA presentation. The bridge
fixture has a simulation-only initial position; the board starts at the original
spawn. Both fixtures capture standing and jumping views. JSON files alongside
the PPM captures contain geometry, raster, clear, depth and frame-cycle counters.
The accelerated physics used by these tests does not measure board input latency.

`diagnose_game.py` exports `build/game/diagnostics/source-coverage.svg`, two
independent world projection PPMs and `coverage.json`. Its floating-point
projection/rasterization checks world coverage, not bit-exact FPGA pixels.
The comparison ignores a three-pixel band near source silhouette edges and
reports remaining sky-colored interior pixels for investigation.
An additional reference applies the GPU's integer reciprocal projection and
integer pixel sample points. This classifies projection-boundary shifts without
assuming the floating-point image should match every FPGA pixel.

The large gaps in the earlier single-root view were missing opaque surfaces.
The selected source views at the spawn and bridge have continuous terrain.
Sky beyond the selected geometry is intentional. Alpha/decal appearance remains
unsupported. At each of the spawn and bridge views, three isolated pixels flagged
by the floating-point reference disappear when the comparison uses integer projection/sample points;
they are boundary rounding, not evidence of missing interior triangles. Any
other residual interior gaps must be evaluated against quantized projection,
shared edges and depth before changing RTL.

## Performance follow-up

Use the captured stage counters before refactoring either processor. CPU software
multiply/divide and linear collision scans are candidates for profiling; GPU
bounding-box work and depth rejection can reveal raster cost. The 30 Hz active
GPU budget excludes time waiting for VGA page swaps. Positive Quartus timing
establishes 50 MHz operation, not a gameplay frame-rate guarantee at every view.
Physical walking, jumping, walls and the FPS overlay should be checked with the
new image; automated simulation and UDP acknowledgements cannot replace that
visual board check.

Measured active GPU work is 331,566 cycles (6.63 ms at 50 MHz) at the spawn and
344,967 cycles (6.90 ms) at the bridge. These exclude VGA swap wait and are
below the 1,666,667-cycle budget. The geometry-active counts are only 6,086 cycles;
raster-active counts are 211,439 / 226,926 and geometry stalls overlap raster work.
Stage counts overlap, so do not add them to infer total frame time. These two
views leave substantial headroom; they do not establish the cost of a full level
or animated actors. Broad processor refactoring is not needed for this area.
