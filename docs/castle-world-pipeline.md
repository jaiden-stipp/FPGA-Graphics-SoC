# Castle world pipeline: implementation checkpoint

This is a software foundation for the selected complete-castle milestone. It
does not yet implement the Secret Slide star mission or the original SM64
movement engine. The hardware image is unchanged.

## Reproduce the package

From the repository root with LLVM/Clang on PATH:

```powershell
.\scripts\run.ps1 sm64_castle.py
.\scripts\run.ps1 portable_game.py check build/castle/game.project.json
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json
.\scripts\run.ps1 test_world_pipeline.py
```

The adapter reads the clean commit in `sm64.lock.json`. It exports
`build/castle/world.json` and the corresponding project. The shared compiler
emits source-neutral `world_data.h`; a separate source adapter emits Mario's
original skeleton/clips and the castle's warp records. The specialized-C audit
and linker reject unsupported arithmetic, unresolved helpers, oversized local
firmware, or assets that overlap SDRAM's test page. The package loader verifies
both segments by readback before releasing the CPU.

The resulting `build/mario-castle-sdram.package.json` is an experimental
traversal package. It must not replace the established Mario/Quake packages as
the advertised completed mission. No new Quartus build is required.

## Stored content and runtime

| Area | Exported static triangles | Original collision faces | Packed world meshes |
|---|---:|---:|---:|
| Grounds | 785 | 879 | 8 |
| Interior 1 | 2,181 | 2,144 | 19 |
| Interior 2 | 2,546 | 2,019 | 22 |
| Interior 3 | 1,419 | 1,395 | 13 |
| Secret Slide | 1,347 | 1,126 | 10 |

The 8,278 exported terrain triangles remain exact after spatial ordering and
packing: source triangle ID, ordered positions and palette index are checked.
Counts describe explicit static display lists, not all original dynamic
objects or callback-generated graphics. Interior roots have the original
`geo_switch_area` room membership; the supporting collision floor selects the
room. Room zero retains the last selection, as in the original callback.

The CPU stores physics positions in source units. Rendering uses a player-relative
origin and four GPU units per source unit. The target policy uses focal 256,
near depth 257 and software far depth 30,000 GPU units. Flat colors substitute
textures explicitly; texture alpha/decal appearance is rendered solid. The
models' source files are not rewritten.

The castle camera uses the shared `camera_orbit_step` service. Its framing is
based on the original radial/8-direction camera's 1,000-unit distance and
125-unit focus height, with an 800-unit boom inside the castle. The default
view looks downward by 22.5 degrees, replacing the earlier 400-unit close view
that looked upward. Focus follows smoothly; collision retracts the boom
immediately and its length recovers gradually. Area changes and respawns reset
following so the old area's camera cannot carry into a new spawn. Mouse pitch
is relative to this default view and stays between downward 45 degrees and
horizontal. Projection remains the existing focal 256. This is original-style
third-person framing, not a complete port of original Lakitu modes, scripted
paths or contextual camera regions. The original model and physics are intact.
Camera tests verify open-space screen coverage, following, collision recovery,
neutral mouse framing and area-reset behavior. Earlier FPS measurements below
describe the previous camera; the wider view may submit more visible geometry.

Castle appearance uses `profiles/sm64-castle-colors.json`, with explicit authored
RGB swatches for 88 material symbols including the untextured default. This
replaces the earlier Bob-omb Battlefield material-table fallback that made
castle terrain uniformly gray. Grass, roofs, masonry, paths and interior/slide
materials now have distinct palette colors. These are flat-color approximations,
not colors sampled from original textures: the source checkout has no extracted
castle texture images. An unknown texture symbol fails conversion instead of
silently receiving a gray fallback. Source vertices, ordered faces, collision,
animations and warp data are compared before/after this appearance change in
`build/castle/color-validation.json`.
The camera-framing revision was successfully uploaded with memory readback
verification and a confirmed advancing frame counter. It contains 28,608 bytes
of CPU code/data and 883,124 bytes of SDRAM assets. Hardware image unchanged;
14 camera tests and 25 world integration tests pass.

The corrected export has 11 distinct terrain colors on the grounds, 11/15/10
in the three interior areas, and seven on the slide (101 total palette entries,
including Mario). Its software package builds and the 24 world integration
checks pass. The initial recolored-package upload attempt received no status
reply from 192.168.7.2:4000; it stopped before BEGIN, so that attempt did not
alter the running board. The subsequent camera-framing revision loaded both
fixes successfully after the connection recovered. To reload that package:

```powershell
.\scripts\run.ps1 load_game.py build/mario-castle-sdram.package.json --status
```

Each area has a conservative 512-unit X/Z collision grid. The default query
halo includes radius plus maximum per-tick movement. Legacy controllers retain
their exhaustive query path and original world bounds. World queries use
Q12 plane normals for steep floors that cannot fit the legacy slope fields.
Original surface names, room IDs, special objects and water boxes remain in
the exported IR. The adapter reads original numeric surface IDs directly from
`include/surface_terrains.h` and preserves `COL_TRI_SPECIAL` force parameters.
The shared compiler emits opaque type IDs, source face IDs, force parameters
and rooms for floors and walls. Other games can supply their own type table;
the shared runtime does not interpret SM64 surface numbers. `world_floor_contact`
returns the supporting surface, normal and height to the game port. Retaining
metadata does not implement all its behaviors.

The castle port now handles death/vertical-wind floors using the original
`player_y < floor_height + 2048` threshold. As in `interaction.c` and
`level_update.c`, falling invokes F3, falls back to F1 if necessary, and delays
the exit for 20 simulation ticks. The slide's original F3 destination is castle
area 1, node 0x20, position (-1024, 900, 717). Star/death/falling destinations
are exported separately from proximity triggers; they cannot activate merely
because Mario walks past a spawn marker. Fade, sound, lives and original exit
actions remain unimplemented. The supporting-plane return sequence is tested
against the imported terrain on the host; physical fall traversal is pending.

Mario reserves two resident handles. World meshes occupy remaining handles
and upload only between frames. Visible meshes that cannot reside or whose
transformed coordinates exceed the indexed path use CPU clipping and existing
DRAW_TRIANGLE commands. The cache cannot truncate the visible scene. Cold area
uploads and steady-frame work must be measured separately.

Direct triangle submission reuses each mesh vertex's CPU transform and frustum
outcode within a frame. Command CRC uses an equivalent two-nibble lookup;
reference checks cover every byte with seven seeds and the standard CCITT-FALSE
check value. Long collision edges use remainder-based fractional division,
avoiding overflow from shifting a large dot product. These changes affect
software only.

The adapter resolves 15 original active door/warp links. A shared transition
query checks area, proximity, use input and progress requirements. Castle
runtime uses the explicit 70-star/two-key traversal fixture, E for door warps,
automatic activation at the original slide entrance, and a cooldown after
arrival. Arrival positions include the original 300-unit door displacement.
This still needs original door models, collision/animation and traversal tests;
the link implementation alone does not complete the castle.

## Independent reuse

```powershell
.\scripts\run.ps1 portable_game.py check examples/portable-world/game.project.json
.\scripts\run.ps1 soc.py portable-game --project examples/portable-world/game.project.json
```

The authored two-area example uses the same compiler, collision query, cache,
clipping and transition functions. Move to source position X=600/Z=600 and
press E to move between its two areas. No SM64 adapter or actor data is needed.
Other games still require their own source adapters and scoped engine/gameplay
ports; this representation is not an automatic arbitrary-engine converter.

## Verification and remaining work

Native tests execute production C for cache overflow, upload ordering, clipping,
indexed/full collision equivalence, transition gates and automatic warps. They
also verify original castle face reconstruction and source script destinations.
An earlier full CPU/SDRAM/GPU simulation passed and recorded a VGA frame and
elapsed frame cycles before the subsequent software optimizations and floor
events. Latest code has host production-C tests and an on-board standing-frame
test; the full RTL simulation has not been repeated for this revision.
`game_frame_cycles` measures update start through completed presentation;
`game_cpu_cycles` measures submission and `game_present_cycles` the final wait.
Adding CPU time to the GPU interval would double-count concurrent work.

The latest regression run passed 109 tests, including the production castle
update path's full 20-tick falling return, source collision metadata, long-edge
arithmetic and failure-safe profiling restoration. Both castle and independent
two-area packages build with the RV32I specialized-C audit. The castle package
used for the timing run contains 27,776 bytes of CPU code/data and 883,048 bytes
of SDRAM assets. The later palette correction retains the same CPU size and
uses 883,124 bytes of SDRAM assets.

### Physical measurements, October 9, 2026

The same castle grounds standing view was measured on the existing FPGA:

| Software revision | Completed frame time | Approximate observed FPS | CPU update/submission |
|---|---:|---:|---:|
| Initial foundation | 100.10 ms | 10 | 84.25 ms |
| Frustum/CRC improvements | 66.73 ms | 15 | 52.65 ms |
| Per-mesh vertex reuse and floor events | 50.05 ms | 19.82 | 35.81 ms |

Raw reports are `build/castle/physical-foundation.json`,
`physical-optimized.json` and `physical-vertex-reuse.json`. The detailed phase
report is `physical-profile.json`. GPU geometry, raster and clear counters sum
to about 6.5 ms in this standing view; this excludes stalls and presentation
wait and is not an end-to-end frame time. Software submission remains the
larger measured cost. These results do not establish performance in other
rooms, during camera movement, or during cold area uploads, and do not meet
the 30 Hz rendering target.

The reusable profiler validates both packages, uploads/verifies the trial,
samples completed frames, holds the CPU to read counters, then restores the
specified baseline even if trial loading or sampling fails:

```powershell
.\scripts\run.ps1 profile_game.py build/mario-castle-sdram.package.json `
  --restore build/quake-interactive-sdram.package.json `
  --symbols build/mario-castle-sdram.symbols.json `
  --out build/castle/physical-profile-repeat.json
```

The final physical run restored Quake and confirmed the CPU was released.
No Quartus compilation or hardware programming was performed. The hardware
image SHA-256 remained
`B89797F51864CF1AA39E7C7835AD7105FB4D2A689986EED8F624CD8F70318617`.

Outstanding acceptance work: original doors and dynamic source graphics;
the original slide movement/action subset and physical death/return traversal; source box/star
geometry and behavior; mission return and save persistence; low-progress gate
tests; two-way castle route validation; cold and moving-scene timing measurements and
physical VGA/input verification. No claim of 30 Hz or a complete playable star
mission is made by this checkpoint.
