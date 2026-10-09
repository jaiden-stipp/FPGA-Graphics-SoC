# Next milestone: traversable Peach's Castle and Secret Slide

Selected with the user on October 9, 2026. This is the next implementation
milestone, not a claim that the castle package or its original gameplay is
already running. It replaces Bob-omb Battlefield as the target for the next
complete-level milestone. Existing Mario, Quake, and portable packages remain
regression baselines.

The current software implementation and reproducible commands are documented
in [castle-world-pipeline.md](castle-world-pipeline.md). Its traversal foundation
does not yet satisfy the mission acceptance criteria below.

The user explicitly reserves hardware optimization for themselves. This
milestone changes software, asset adapters, schemas, tests, and documentation
only. Do not change CPU/GPU/SDRAM/Ethernet RTL, memory sizing, clocking, FIFO
interfaces, hardware capabilities, or the FPGA programming image. Existing
hardware can be observed/tested and compatible software packages loaded; do not
rebuild or reprogram hardware as part of this milestone. Report hardware limits
and measurements for the user to address independently.

## Outcome

Run Mario through the original castle grounds and all three original castle
interior areas. Doors and area transitions work; Mario can walk, jump, slide,
collide with the level, fall/retry, and retain his original model and animation
data. Enter Peach's Secret Slide from its original castle entrance, complete the
slide, open the original star box, collect its star, and return through the
original exit destination. Collecting a star changes mission state exactly once.

The implementation must use the reproducible source-adapter -> shared world
representation -> target compiler -> RV32I game port -> verified Ethernet
package loader pipeline. Shared loading, collision acceleration, input,
animation, transitions, and persistence interfaces must be usable by another
game. SM64 names, level IDs, mission rules, and source interpretation belong in
the SM64 adapter/port, not in CPU/GPU RTL or generic compiler branches.

This is a scoped port of the necessary SM64 behaviors, not the complete SM64
engine, every castle mission, or an arbitrary-engine converter. The first star
is the slide's box star; its under-21-seconds bonus star is outside this mission.
Other painting destinations and the separate castle courtyard are not added by
this milestone. Their unsupported transitions must be reported and safely
blocked, rather than entering missing areas.

## Verified starting point and constraints

- The existing Mario package already imports all 1,043 opaque Bob-omb
  Battlefield terrain triangles and the original low-poly Mario skeleton and
  four clips. It still derives collision from rendered triangles.
- Castle source data exists in the pinned SM64 checkout. Original terrain
  collision counts are: grounds 879, interior area 1 2,144, interior area 2
  2,019, interior area 3 1,395, Secret Slide 1,126. These are collision counts,
  not render-triangle or GPU capacity estimates.
- Castle interior GeoLayouts select room branches with `geo_switch_area` and
  have corresponding `room.inc.c` data. The importer must resolve the original
  branch structure; treating every listed branch as a simultaneously visible
  room is incorrect.
- The CPU executes from 64 KiB local RAM. SDRAM has 128 MiB for assets/data.
  The GPU holds 16 meshes, each with at most 128 vertices/256 triangles. Mesh
  definition/vertex/index uploads are currently permitted only in GPU IDLE,
  outside an active frame. The GPU has no direct SDRAM reader.
- The current combined CPU/GPU frame-budget calculation double-counts
  overlapping intervals. Establish correct wall-clock timing before accepting
  performance or choosing hardware changes.

## Implementation sequence

### 1. Establish accurate timing and source coverage

Record update, animation, upload, command submission, presentation, and complete
wall-clock frame intervals with matching frame IDs. Separate warmup/area loading
from steady play; retain GPU stage counters without adding overlapping intervals
to claim frame latency. Replay the existing Mario and Quake views as baselines.

Inventory the selected GeoLayouts, display lists, terrain collision, room tables,
level scripts, door models, original Mario clips, slide box/star objects, spawn
positions, and warp destinations. Pin hashes and source identities for every
included record. Produce an explicit report of unsupported materials, callbacks,
objects, and destinations; unknown behavior on the mission route is a build
failure, not a silent omission.

### 2. Add shared multi-area world assets and queries

Extend the source-neutral representation with areas, stable mesh/chunk IDs,
conservative bounds, explicit collision surfaces, visibility groups, instances,
transition endpoints, and animation references. Introduce a versioned extension
while retaining the existing version-1 scene/package path. Keep the existing
`game_port_init/update/render` entry points; game logic owns transition requests,
and shared services resolve/load area assets.

The SM64 adapter imports original collision separately from appearance, including
floors, ceilings, walls, surface classifications, room memberships, and water
volumes where needed. Preserve source positions, winding, hierarchy, clip samples,
object placements, and warp IDs. Apply declared area origins and a consistent
uniform coordinate scale, recording quantization and numeric limits. Preserve
source-specific surface metadata even when a behavior is not implemented yet.

Build a conservative spatial index for nearby collision and camera queries.
Compare indexed queries to exhaustive reference queries. Collision remains
available independently of the visibility set, so looking away cannot remove a
floor or obstacle. Shared services contain no hard-coded castle coordinates.

### 3. Load visible geometry safely from SDRAM

Use the original room membership/selection as the SM64 adapter's visibility
input and shared bounds/frustum filtering for rendering. Cache world chunks in
GPU handles; retain Mario's actor handles and budget doors/mission objects.
Upload missing chunks only after the previous frame completes and before the
next BEGIN_FRAME. Never overwrite geometry still referenced by an active draw.

All required visible geometry must be represented. If a visibility set exceeds
available handles, use existing direct triangle commands for uncached world
geometry as the correctness fallback and measure its cost. Do not drop distant
surfaces, invent filler, or reduce original topology to pass capacity checks.
If that correct fallback misses the measured performance target, profile the
specific transfer/render bottleneck, apply software optimizations that preserve
the source geometry/behavior, and report the remaining limit. DMA, new GPU
commands, memory expansion, and hardware interface changes are reserved for the
user. Do not assume uploads inside a frame are supported.

Preload transition destinations before committing an area switch. During loading,
keep the last complete displayed frame and pause gameplay time. On failure, keep
the source area/state valid and report the loading error. Camera, collision,
spawn, object state, and palette switch together; avoid mixed-area frames.

### 4. Port the castle and slide mission behaviors

Retain original Mario geometry and skeletal data. Port the source behavior subset
needed for walking, jumping, sliding, box interaction, star collection, doors,
warps, falling, and return/retry. The present shared walking controller does not
provide original slide physics and must not be relabeled as an engine port.

Numeric/platform changes required by RV32I must be explicit: identify the source
functions/constants, implement bounded integer/fixed-point equivalents, and
compare state trajectories with an original floating-point host reference.
Preserve action transitions, slope-dependent sliding and steering, mission
object rules, source warp endpoints, and source animation selection where they
are ported. Do not substitute a teleported finish trigger for a traversed slide.

Use the existing extended input transport for additional actions and preserve
legacy package input compatibility. Bind movement to WASD/arrows, jump to Space,
door/interaction to E, box attack to F/left mouse, and retry to R. Route those
inputs through the game-specific action adapter, not global changes to Quake.

Represent box state, star state, mission result, and progression through shared
object/event/save interfaces. Persist mission progress through a versioned host
save record during the connected Ethernet session; document that on-board RAM
alone does not survive power loss. Star collection is idempotent and re-entering
the slide must not award the same star twice.

Default verification uses a documented progression fixture with 70 course stars
and both castle keys, leaving the Secret Slide box star uncollected. This allows
all requested castle interior areas while retaining source star/key door checks.
It is test save state, not a claim that earlier courses or bosses were played.
Also test locked gates with a low-progress fixture. Keep progression values in
save/profile data, not compiled into common services.

Flat-color appearance remains the initial renderer target. Record unsupported
texture/alpha/decal effects explicitly; do not remove traversal geometry or make
transparent decoration into an unexplained collision obstacle. Faithful texture
appearance is a separate capability, with any necessary material approximation
documented in conversion output.

### 5. Prove reuse and deliver reproducible commands

Build the castle world and its SM64 gameplay module through the same generic
project command used by other game ports. Source import is a separate adapter
command; target compilation, capacity checks, packaging, loading, and diagnostics
remain common. Record source revisions, asset/port hashes, source-to-output
mappings, capability requirements, and numeric approximation reports.

Exercise multi-area loading and transition state with a small independently
authored two-area test scene as well as the castle. Rebuild/load an existing
Quake package using the same services. Provide a launcher that chooses the
package and matching input/save profile without FPGA reprogramming between
compatible games. Document the exact commands only when they are implemented
and tested; this milestone document does not advertise unimplemented commands.

## Acceptance checks

- One reproducible clean build from pinned source produces the castle/slide
  executable, SDRAM assets, manifest, conversion report, and source hashes.
  Mandatory RV32I audits pass, executable/state/stack and asset ranges fit, and
  unsupported route-critical source operations fail before upload.
- Original geometry/animation provenance passes independent comparison;
  quantization, appearance changes, and numeric port differences are reported.
  All hardware RTL, the programmed FPGA image, and upstream checkouts remain
  unchanged. Hardware bottlenecks are reported, not repaired in this milestone.
- Indexed collision matches exhaustive queries for floors/walls/ceilings,
  room boundaries, slopes, stairs, doorways, and camera paths. Exercise the
  slide's full vertical range and thin rails without clipping through them.
- Record successful routes from grounds to lobby, basement, upper floors,
  attic approach, and back. Test repeated two-way door/warp transitions,
  collision while looking away, falling/retry, and missing-destination handling.
- From the castle's original slide entrance, complete the slide under player
  control, open the original box, collect the star once, return to the source
  destination, and retain the result across reload. Replay partial runs,
  falling before completion, and attempts to collect twice.
- CPU-to-VGA integration captures prove Mario, doors, slide geometry, box/star,
  and mission state were rendered by the FPGA GPU. Hardware checks measure
  distinct frame completions and input responsiveness along recorded routes.
  Target 30 Hz steady play through software optimization; exclude and separately
  report transition loading. No claim of that target until the measured routes
  meet it. If unchanged hardware cannot meet that rate, report achieved frame
  times and the limiting subsystem without silently dropping content, changing
  mission behavior, or introducing hardware changes. Do not promise full scope
  fits unchanged hardware until the source/capacity audit and route tests pass.
- Version-1 Mario/Quake and shared-pipeline regressions pass. A source-neutral
  two-area test scene uses the same loading/query/transition services with no
  SM64 names in shared code. Switching compatible packages uses the same SOF.

## Delivery order

Accurate timing and source coverage -> original collision/area representation ->
shared visibility/cache and safe transitions -> castle traversal -> slide actions
and box/star mission -> save/retry and launcher -> full-render/hardware validation.
Each delivery remains a reusable extension of the existing pipeline. A rendered
castle screenshot, a separate slide viewer, or a hand-placed collectible alone
does not satisfy this milestone.
