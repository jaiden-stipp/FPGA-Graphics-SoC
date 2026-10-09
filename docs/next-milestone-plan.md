# Next milestone plan after physical Mario VGA output

Planning review dated October 8, 2026, based on the three supplied monitor
photographs and the current source/conversion pipeline. This review changes
documentation only; the running FPGA image remains the validated Mario image.

Stage 1 implementation is documented separately in
[stage1-playable-area.md](stage1-playable-area.md); the planning observations
and original baseline below are retained for context. Stage 2 implementation
is described in [stage2-camera.md](stage2-camera.md).
Stage 3 implementation is described in [stage3-animation.md](stage3-animation.md).
Stage 4 implementation is described in [stage4-packages.md](stage4-packages.md).
The intervening [SDRAM milestone](sdram.md) provides live Ethernet package
loading; the original planning assumptions below are historical.

## What the photographs establish

Mario and the terrain render together on the physical VGA display. Two photos
show FPS030 and one shows FPS029. There is no obvious loss of VGA synchronization
in these stills. Different character facings and views are consistent with the
controller operating, but photographs alone do not verify jump/landing behavior,
wall collision, input latency, frame-time consistency, or depth correctness.

The visual priorities are large sky-colored gaps in the terrain, a rigid character
pose, coarse face/hat patches, and limited camera framing. The large gaps deserve
an asset-completeness audit before changing the rasterizer. Face and logo textures
currently become flat colors; their missing detail is expected from that adapter.
Mario's source parts are assembled in a declared standing pose rather than posed
through the original animation hierarchy.

## Source findings and budgets

The level GeoLayout references six static display lists. A read-only inventory of
reachable source triangles found:

| List | Original layer | Triangles | Current import |
| --- | --- | ---: | --- |
| `bob_seg7_dl_07004390` | Opaque | 184 | Included |
| `bob_seg7_dl_07009D80` | Opaque | 473 | Omitted |
| `bob_seg7_dl_0700A470` | Transparent decal | 34 | Omitted |
| `bob_seg7_dl_0700A920` | Alpha | 24 | Omitted |
| `bob_seg7_dl_0700DD18` | Opaque | 354 | Omitted |
| `bob_seg7_dl_0700E338` | Opaque | 32 | Omitted |

This gives 1,043 opaque triangles and 58 decal/alpha triangles, or 1,101 in total,
excluding objects instantiated separately by the level script. Counts do not
establish that all lists can be represented faithfully by the current renderer.
The alpha list also disables backface culling in the original source. Decals and
alpha geometry require explicit material/culling policies; treating them as
ordinary solid terrain can produce incorrect occlusion and collision.

Current world + Mario: 396 triangles, four of 16 mesh handles, 123 palette colors,
147 floor triangles and 37 obstacle triangles. Hardware limits remain 128 vertices
and 256 triangles per handle, 256 palette colors and signed Q8.8 geometry. CPU RAM
is 64 KiB; `_bss_end` is `0x4a68`, leaving 42,392 bytes before the reserved 4 KiB
stack. Mesh data, collision metadata, animation data and code must share that
remaining space. Current resource fit and 29–30 FPS photos do not establish the
cost of importing the rest of the level or updating animated vertices.

Original animation data is present in `external/sm64/assets/anims/`, including
idle-center `anim_C5`, walking `anim_48`, jump `anim_4D` and landing `anim_4E`.
The jump/landing pair is in `anim_4D_4E.inc.c`. These clips can be evaluated from
the checked-in C data; they do not require waiting for texture extraction.
Original terrain collision data is also present in the level source.

## Proposed order

### 1. A coherent playable area and a geometry diagnosis

Extend the scene adapter to resolve multiple source files/display-list roots with
one shared world transform. Keep original vertices and winding, declared source
provenance and explicit layer policies. Import the missing opaque surfaces needed
for a connected area around the path and bridge, checking palette, mesh, firmware
and frame-time costs before expanding farther. Select whole original surfaces or
a declared bounded area if necessary; avoid inventing filler geometry.

Compare an offline source-geometry view with actual GPU framebuffer captures from
several fixed cameras. Classify each gap as absent source layer, an intentional
opening, unsupported appearance state, or a rendering problem. Investigate shared
edges, clipping, winding and depth precision only for gaps that remain after the
matching geometry is present. Add small regression scenes for any confirmed
renderer defect before considering a targeted RTL change.

Choose an explicit, validated spawn on a broad interior floor. Check walking to
the bridge, ramps, wall sliding, jumping/landing, falling and respawning on the
physical board. When using original collision data, select it consistently with
the displayed area so invisible omitted structures do not become obstacles.
Keep collision import separate from the controller and preserve surface metadata.

Acceptance: one connected route can be traversed and jumped through without
unexplained holes, clipping through walls, or invisible floors. Source models and
CPU/GPU interfaces remain unchanged. Memory/capacity checks pass and measured
frame times meet the 30 Hz target for this area.

### 2. A configurable third-person camera

Move pitch, distance, target height and projection settings into the game profile.
Add gentle following/look-ahead and limit camera penetration into terrain. Filter
vertical following so Mario's rise and landing are visible, rather than keeping
him locked to the same screen height throughout a jump. Test near walls, bridges,
slopes and map edges. Keep these functions in reusable fixed-point software.

Start with automatic camera behavior using the existing input transport. Manual
orbit controls can be a later input-interface extension with a separate protocol
compatibility test. Camera-relative movement must be introduced together with any
camera yaw changes so control directions stay understandable.

Acceptance: Mario remains visible, jumps are easy to judge, and the camera avoids
passing through solid terrain. Camera changes preserve model geometry and source
game data.

### 3. Original skeletal animation

Import the original joint hierarchy and idle/walk/jump/land clips. Verify a neutral
pose and joint axes against the original layout before connecting clips to player
state. Separate animation, world position and collision dimensions, and avoid
applying animation root motion on top of controller motion twice.

Prototype CPU evaluation of fixed-point joint transforms and updating the two
persistent actor mesh chunks, with unchanged local source vertices and triangle
indices. The GPU continues to apply character/world/view transforms and render
the triangles. Measure vertex-upload and CPU costs before committing to this
route. Keeping all 15 parts in separate persistent handles would require 17
handles with the present two terrain meshes, exceeding the existing limit.
Choose a measured packing/update strategy rather than increasing hardware
capacity by default.

Acceptance: original idle, walking, jumping and landing poses work in several
facing directions, feet align with the floor, and animation fits the firmware
budget and 30 Hz target. Record clip/source hashes and test transformed reference
vertices so animation adaptation does not silently alter source geometry.

### 4. Prove reuse with a second game package

Define a versioned package schema for meshes, palette/material policy, collision,
animation and game configuration, plus a narrow runtime interface for input,
update and draw. Keep source-specific conversion in adapters. A second small game
or independent test scene should use the same runtime/GPU interfaces with a
different asset package and gameplay module.

Initially select packages at build time and replace boot firmware. That establishes
reuse without implying an existing live loader. Runtime executable/asset loading
later needs a receive/storage path accessible to the CPU; the current Ethernet
interface exposes controls, not arbitrary downloaded game binaries. Size that
path from measured packages. Introduce external memory only with a CPU memory
interface that can tolerate its access latency.

Acceptance: two distinct game packages build and run without game-specific CPU
or GPU RTL, enforce the same capacity checks, and document which source logic
was preserved and which numeric/platform adapters were required.

## Later capabilities

Texture sampling and alpha support can restore the face/logo and level appearance
more faithfully, but require renderer capabilities beyond the current flat palette
pipeline. Full original SM64 gameplay needs a deliberate numeric/platform port
and a larger memory/performance budget; importing its mesh and animation data
does not supply that engine. Keep both as separately measured milestones.

The recommended immediate milestone is **a complete, connected playable area with
a usable following camera**, followed by original skeletal animation. This
prioritizes gaps and playability seen in the photographs while keeping the asset
pipeline and runtime reusable for other games.
