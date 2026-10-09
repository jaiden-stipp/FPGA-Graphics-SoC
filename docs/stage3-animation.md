# Stage 3: original skeletal animation

The CPU evaluates the original Mario joint hierarchy and idle, walking, single
jump and landing clips. The existing GPU receives posed vertices in the same
two actor handles, then transforms, clips, depth-tests and draws all triangles.
Player physics, the following camera, UDP controls and CPU/GPU RTL are unchanged.

## Source preservation and adapter choices

`scripts/animation_assets.py` reads `mario_geo_low_poly_body` from the pinned
`actors/mario/geo.inc.c`. Its 20 animated nodes include nodes without geometry;
those still consume the original rotation channels. Fifteen selected original
display lists supply the same 212 triangles and 136 packed vertices. Local
source positions, winding, triangle indices and palette assignments are retained.
The importer resolves branches and explicitly selected cap/eye/hand switches;
unsupported nodes, channels and undeclared callbacks stop conversion.

| Role | Original clip | Reachable source frames | Runtime behavior |
| --- | --- | --- | --- |
| Idle | `anim_C5`, idle head center | 0–29 | Repeat this original sequence while stationary |
| Walk | `anim_48`, walking | 0–76 | Preserve its loop, advance two source frames per physics tick |
| Jump | `anim_4D`, single jump | 0–11 | Advance one frame per tick, then hold while airborne |
| Land | `anim_4E`, land from single jump | 22–37 | Start at the original frame 22, then return to idle/walk |

The wrapper chooses clips from actual controller movement and grounded state.
Holding a direction against a wall does not count as walking. Respawn resets
animation history. Idle repetition, walk playback rate, clip selection and
neutral dynamic callbacks are explicit adapter behavior; this is not the
original SM64 animation state machine or gameplay engine.

Original indexed channel samples are retained losslessly for every reachable
frame. Identical channels share storage and redundant trailing repeated samples
use the source's clamp convention, reducing values to 4,185 signed samples
(8,370 bytes). Clip descriptors add 1,008 bytes, the quarter sine table 2,050
bytes, joints 160 bytes and vertex ownership 136 bytes. Source paths and hashes,
parents, selected switches and omissions are recorded in `build/game/conversion.json`.

Joint rotation follows the original XYZ convention (`Rz * Ry * Rx`) and 4,096
angular samples, using Q14 rotations and fractional source translations on RV32I.
The actor uses one declared uniform normalization to the existing 128-unit
controller height. Original vertical animation translation is evaluated;
lateral root motion stays with the player controller. Grounded poses receive a
common vertical render offset so their lower foot sole touches the collision
floor. This never changes the collision capsule or applies motion twice.

Cap-on, open eyes and closed hands are selected. Dynamic torso/head/hand scaling
callbacks are neutral; held objects and static alpha cap wings are explicitly
omitted. Flat colors and lighting remain the earlier declared standing-pose
palette; normals are not relit as joints turn. Face/logo textures, alpha,
animation blending, held objects and the complete gameplay engine remain later
capabilities. Upstream geometry and game files are untouched.

## Reusable runtime and budgets

`firmware/include/animation.h` defines source-independent joint, channel, clip
and package records. `firmware/src/animation.c` evaluates that package; SM64
parsing remains offline. Profiles without an `animation` object retain the
static actor path. The existing rigid pose declarations remain available for
that path and the unchanged flat palette bake.

Terrain, triangle indices and palette are uploaded at boot. After physics and
camera ticks, the CPU evaluates one pose and updates all 136 actor vertices
before starting the next GPU frame. Geometry handles and draw/model/view
commands retain the existing protocol. No new renderer commands are needed.

The board binary is 56,058 bytes. `_bss_end=0xe0e4` (57,572 bytes) leaves 3,868
bytes before the reserved 4 KiB stack. This is close to the current 64 KiB RAM
budget. Additional level/animation content needs measured compression or a
larger memory interface; unused FPGA logic alone does not add addressable RAM.
The board's external SDRAM is not currently connected to the CPU memory bus.

CPU cycle counters separately record pose evaluation, vertex upload and total
physics/camera/pose/upload/submission work. Full GPU capture metadata reports
active GPU work separately from swap wait. Tests conservatively add CPU work
and GPU active work and enforce the 1,666,667-cycle (33.3 ms at 50 MHz) budget.
See [validation.md](validation.md) for measured frame results.

## Reproduction and review

```powershell
.\scripts\run.ps1 soc.py sm64-mario --sim --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
.\scripts\run.ps1 test_animation.py
.\scripts\run.ps1 diagnose_animation.py
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout mario
```

The optional pose diagnostic requires Pillow and the native Clang test
toolchain. It writes a labeled CPU-reference pose sheet, JSON and evaluated OBJ
poses under `build/game/animation-diagnostics/`. These are software review
artifacts. `build/game/actor.obj` still describes the earlier rigid adapter pose
used for palette/packing; it does not describe a current animated frame.
Actual GPU framebuffer captures are the four `build/mario*.ppm` files.

Host tests compare production C output with independent floating-point hierarchy
evaluation for every reachable clip frame, both grounded and airborne. They
verify original samples/local vertices, axes, foot contact, state transitions,
respawn and absence of physics mutation. Maximum observed vertex deviation is
1.0549 integer GPU coordinate units. The real RV32I stream test checks changing
poses and complete per-frame updates under decoder backpressure. Full board
tests send MII UDP controls and capture standing/jumping at spawn and bridge.

On the physical board, check idle, walking in multiple directions, stopping at
a wall, jumping/landing, and R reset. Confirm sustained FPS and foot contact on
the path and bridge. Automated timing/captures establish the tested budget;
physical VGA animation and input feel require interactive review.
