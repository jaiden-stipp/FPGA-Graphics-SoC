# Controllable Mario and reusable game assets

The RV32I CPU now controls a flat-colored Mario model on the imported terrain.
The graphics processor transforms and renders every terrain and character
triangle. CPU, GPU, Ethernet RTL, pins and graphics/control protocols are unchanged.

## Build and run

Open `C:\Users\Orb1t\Documents\Codex\FPGA-Game-SoC\SoC.qpf` in Quartus Lite 18.1.
The combined command generates the project and selects the Mario boot firmware:

```powershell
cd C:\Users\Orb1t\Documents\Codex\FPGA-Game-SoC
.\scripts\run.ps1 soc.py sm64-mario --sim --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
```

Program `build\quartus\SoC.sof` using the existing USB-Blaster setup. Keep the
working ENET0/JP1 MII and VGA wiring and the PC's `192.168.7.0/24` network setup.
Start keyboard input with:

```powershell
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout mario
```

| Keys | Action |
| --- | --- |
| WASD / arrow keys | Move across the terrain; turn toward movement |
| Space | Jump; release before another jump |
| R | Respawn at the initial position |
| Esc / Ctrl+C | Stop the sender and release input |

The configurable camera smoothly follows Mario with a fixed yaw, bounded
look-ahead, filtered jump height and terrain avoidance. See
[stage2-camera.md](stage2-camera.md) for settings and checks. KEY[1]/KEY3 retain local
left/right movement; KEY[0] resets the system. Global Windows keyboard polling,
60 Hz UDP updates and the 300 ms input timeout are unchanged. Jump uses bit 4;
respawn uses the four-direction chord `15`, allowing reuse of the existing
five-bit hardware transport. The old viewer uses `--layout scene`.

## Runtime and model preservation

`firmware/src/player.c` implements a reusable Q8.8 controller without renderer
or Mario dependencies. It handles movement and diagonal speed, eight facing
directions, gravity, a press-triggered jump, floor selection, walkable slopes,
small steps, wall sliding, ceilings, landing, and fall/manual respawn. The
capsule is approximated by overlapping spheres; horizontal motion is split
into axes. Profile validation limits movement and jump increments to avoid
skipping thin obstacles. Physics ticks at 30 Hz; catch-up is bounded to four
ticks after a slow frame. Input is sampled on those ticks.

Collision is generated from the exact quantized **displayed** terrain, avoiding
invisible surfaces from other level sections. Upward faces with slopes at most
60 degrees are floors; remaining faces are obstacles. Precomputed bounds,
normals and height planes reduce CPU work. Stage 1 imports the opaque terrain
around the starting field, path and bridge: 188 floor triangles and 138 obstacle
triangles. Falling outside the displayed area respawns the character. Distant
level sections and decorative alpha/decal layers remain outside this milestone.

The original 15 low-poly Mario part display lists supply all 212 actor triangles.
No source vertices, triangle ordering, upstream model files, or upstream game
code are edited. Stage 3 imports the original 20-node hierarchy and indexed
idle/walk/jump/land clips, evaluates poses on the CPU and normalizes them for the
existing world scale. See [stage3-animation.md](stage3-animation.md) for original
data, explicit adapter choices, limits and measured budgets. Original texture
sampling remains replaced by flat colors, including light-group colors.

The CPU uploads five mesh handles, indices and 151 palette colors once, then
updates 136 posed actor vertices and submits camera/frame commands and model
matrices. Terrain matrices stay identity;
actor matrices apply translation and yaw. `gfx_draw_matrix` wraps the renderer's
existing draw command. The GPU still handles projection, clipping, culling,
rasterization, depth testing and VGA presentation.

This is a small platformer controller around the original Mario mesh, not the
original SM64 gameplay engine. Walking, jumping, collisions and respawning are
implemented, with original skeletal clips; collectibles, enemies, original physics and audio remain
future software/asset work.

## Reusing the pipeline

`profiles/sm64-mario.json` separates world selection, actor display lists,
static pose/animation policy, appearance, physics and camera settings. `scripts/game_assets.py` confines
SM64-specific parsing to the import step. The runtime consumes the common
`assets.h` mesh layout and `player.h` collision/controller interfaces. A game
asset build uses its own output directory and generated header; it does not
overwrite a separately selected scene viewer.

The world profile `sm64-bob-playable.json` declares four original opaque roots
in four source files, source-space selection bounds and a shared normalized
extent of 4096 Q8.8 units. Selection retains whole original triangles whose
bounds intersect the area; it does not clip, fill, decimate or change winding.
Triangles can extend beyond the selection box. The distant mountain is omitted
because this milestone targets the start-field/bridge route. The all-level
2048-unit normalization collapses four tiny distant triangles; this is a
converter precision limitation, not evidence of a rasterizer defect.

The original spawn `[-6558,0,6464]` is mapped through the same world transform and
checked for floor support around the capsule. The generated spawn is
`[-1576,-208,1616]`. Explicit flat RGB policies represent newly imported textures;
texture samples and transparency are still unsupported. The conversion report
records every source hash, root count, selected count, omission and transform.
See [stage1-playable-area.md](stage1-playable-area.md) for the area and validation.

```powershell
# Rebuild assets independently, or use a copied/edited profile.
.\scripts\run.ps1 game_assets.py --profile profiles/sm64-mario.json
.\scripts\run.ps1 soc.py sm64-mario --profile profiles/my-game.json

# Firmware and hardware stages can also run separately.
.\scripts\run.ps1 soc.py build-fw --app mario --boot mario
.\scripts\run.ps1 soc.py build-fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
```

Another static SM64 scene/actor can use another declared profile. Another game's
formats need an importer producing the same mesh/collision ABI, and its gameplay
needs an explicit RV32I software port. The existing OBJ converter can feed such
an importer. Changing a profile does not convert arbitrary game code automatically.
Unsupported geometry, unresolved lists, transparency and capacity violations
stop conversion instead of silently changing a model.

Assets currently compile into the 64 KiB CPU boot image. This milestone does not
provide a live game chooser, binary download service, or runtime executable loader.
Those can be added behind a software loading interface later; the controller and
GPU command interface do not depend on a particular game. Existing limits remain
16 handles, 128 vertices/256 triangles per handle, 256 palette colors, signed
Q8.8 coordinates, and at least 4 KiB of stack.

Generated outputs include `build/game/world/scene.obj`, `build/game/actor.obj`,
`build/game/conversion.json`, `firmware/generated/game_data.h`, and `build/mario.*`.
The conversion report records source hashes, selected parts, triangle counts,
collision counts, spawn position and physics settings.

## Verification

```powershell
.\scripts\run.ps1 test_player.py
.\scripts\run.ps1 test_camera.py
.\scripts\run.ps1 test_animation.py
.\scripts\run.ps1 test_scene_pipeline.py
.\scripts\run.ps1 soc.py sim --tests mario_stream_tb
.\scripts\run.ps1 soc.py sim --full --tests soc_mario_top_tb
.\scripts\run.ps1 soc.py sim --full --tests soc_mario_bridge_top_tb
.\scripts\run.ps1 diagnose_game.py
```

The host tests execute the production C controller on floor, slope, wall,
ceiling, jump, edge/fall and actual imported-terrain fixtures. `mario_stream_tb`
runs the real RV32I firmware with command backpressure and verifies one-time
static uploads, per-frame actor vertex updates, all four animation states,
movement/facing, jumping, landing, held-key behavior and respawn.
`soc_mario_top_tb` sends actual MII Ethernet/UDP move+jump packets through the
board wrapper and waits for GPU/VGA completion. It captures the real post-depth
framebuffer RAM writes to `build/mario-standing.ppm` and `mario-jumping.ppm` and
checks that Mario's red geometry is visible. The full test uses accelerated
physics ticks; the board image uses 30 Hz.

The bridge fixture uses the same firmware with a simulation-only initial
position. Its independent captures are `build/mario-bridge-standing.ppm` and
`mario-bridge-jumping.ppm`. Capture metadata records GPU stage counters and checks
active GPU work against a 30 Hz budget. Metadata includes the emitted view
matrix and projection for each capture. `diagnose_game.py` writes source coverage,
independent world projections and an interior-sky comparison under
`build/game/diagnostics`; it does not simulate FPGA edge/depth quantization.

See [validation.md](validation.md) for measured results and the distinction
between simulated behavior and physical-board verification.
