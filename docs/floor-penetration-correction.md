# COLLISION-001: horizontal movement through rising floors

On October 9, 2026, the user reported Mario clipping below the ground and falling
into a void. The image shows Mario partly occluded by terrain; it does not
identify the player coordinates or the responsible collision face.

The software controller has a reproduced defect independent of SDRAM streaming
and the GPU projection fix. Its floor query excludes surfaces above the current
feet plus the configured step allowance. Horizontal movement still proceeded
when a rising floor exceeded that ceiling. Floors are separate from the wall
list, so the character entered the floor, lost support, and continued falling.
Subsequent downward queries also excluded the surface now above his feet.

One original castle interior face reproduces the problem in one tick:

| Value | Baseline | Corrected |
|---|---:|---:|
| Start (X, Y, Z) | (-307, 1155, -1321) | same |
| Requested displacement | -24 X | same |
| Floor at requested endpoint | 1188 | same |
| Maximum allowed floor height | 1187 | same |
| Resulting X | -331 | -307 |
| Resulting Y | 1155 | 1155 |
| Grounded | false | true |

`firmware/src/player.c` now rejects horizontal motion when a destination floor
plane rises from below the starting feet/step allowance to above it. Airborne
movement uses feet height without a step allowance. Legal steps, downhill
motion, and movement beneath overhead floors retain their existing paths.
This is a reusable controller correction, not an original SM64 movement port.
No source meshes, hardware, or loader protocol were changed.

## Native evidence

Raw logs, source snapshots, and hashes are in `benchmarks/collision-001/`.
The audit starts at every imported floor centroid, tries eight headings, and
follows up to twelve ticks while grounded. Python integer cross products check
whether the starting floor covers both endpoints. Python plane arithmetic with
the imported quantized normals checks whether the character moves below that
previously supporting surface. This tests a physical invariant rather than
comparing two executions of the same controller.

| Area | Baseline penetration detections | Corrected detections |
|---|---:|---:|
| Castle grounds | 204 | 0 |
| Castle ground-floor interior | 3 | 0 |
| Castle upper-floor interior | 0 | 0 |
| Castle basement | 0 | 0 |
| Secret slide | 0 | 0 |

Aggregate: **207 to 0 detections in this native fixture**. Paths and tick counts
differ because blocking changes whether the character remains grounded; the
JSON records the counts. This is not 207 confirmed user failures or a hardware
performance improvement. The audit does not exhaust all routes, triangle-edge
crossings, airborne trajectories, or original-versus-quantized geometry.

The world suite passes **29 tests**, including the original interior face,
grounded and airborne ramp crossings, a legal step, and an overhead floor.
The legacy controller suite passes **11 tests**, including jumping, walls,
ceilings, walking off a real edge, and respawning. An initial new test fixture
failed during setup because the legacy importer classified its steep ramp as
a wall; the revised fixture uses explicit floor records. The failed log is kept.

## Package and physical status

Normal and direct-terrain Mario packages were rebuilt through the existing
RV32I pipeline. Their asset SHA-256 remains
`afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`.
The attempted direct-terrain CPU load failed at the initial UDP status request
to `192.168.7.2:4000`, before BEGIN or any upload. **The corrected software was
not loaded onto the board.** No FPGA reprogramming occurred. Board traversal
acceptance remains pending. No FPS or latency improvement was measured.

## Reproduce and load

From the repository root, with Clang/LLVM on PATH:

```powershell
.\scripts\run.ps1 test_world_pipeline.py
.\scripts\run.ps1 test_player.py
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json
# Once the FPGA Ethernet interface is available:
.\scripts\run.ps1 load_game.py build/mario-castle-sdram-direct.package.json
```

The direct-terrain package preserves the previous diagnostic submission mode
for comparison. The rebuilt normal package is
`build/mario-castle-sdram.package.json`; it contains the same controller fix.

Run the archived audit with Python directly:
`python docs/benchmarks/collision-001/audit_floor_penetration.py`.
It requires the generated castle data and native-test dependencies. To reproduce
the baseline, compile archived `player-before-floor-fix.c` into a shared library
exporting `player_bind_query`, `player_floor`, and `player_step`, then pass its
path and an output JSON path as the audit's two arguments. Windows Clang flags:
`-shared -O1 -ffreestanding -fno-builtin -Ifirmware/include -fuse-ld=lld -nostdlib
-Wl,/noentry`, plus one `-Wl,/export:NAME` per export.

If falling persists after loading the correction, capture the actual area,
feet coordinates, grounded state and candidate floor at the failing tick.
This fix does not establish that every visual gap or fall has the same cause.
