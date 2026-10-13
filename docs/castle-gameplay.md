# Castle gameplay software port

This adds a playable, scoped castle/Secret Slide game package. It is **not a
complete port of the original SM64 engine**. The full castle terrain and original
collision are available: grounds, ground-floor interior, upper-floor interior,
basement, and Peach's Secret Slide. Existing area transitions remain in use.

The prior implementation and deployment are preserved by commit `fcf1b8c`.
No CPU/GPU/SDRAM/Ethernet RTL, clocks, or fitted hardware is changed by this
implementation. The local-code gameplay package was deployed on 2026-10-13
and is now selected in `profiles/current-deployment.json`. CPU and SDRAM
segments passed full readback verification before release. A short status
sample advanced the frame counter from 1,833 to 1,893 over 1.015 seconds;
this confirms frame production, not mission completion or sustained FPS.
See `benchmarks/castle-gameplay-001/deployment-2026-10-13.json` for the record.
The earlier milestone smoke-test/restoration evidence remains historical.

## Gameplay implemented

- Accelerating camera-relative walking, jumping, slope sliding and air steering.
  Velocities use Q8, derived from selected source speed/steering rules. Collision
  still uses the shared capsule controller, not `mario_step.c`.
- Ground pound and attacks. Door/use input while airborne selects ground pound;
  attack remains separate so a jump can attack the star box.
- Original low-poly Mario model, skeleton and six losslessly imported clips:
  existing idle/walk/jump/land, original `anim_91` slide and `anim_3D` ground pound.
- Source-positioned wooden and castle local doors, with an authored open/close
  proxy and planar blocking. Original star-number alpha badges are deferred.
- Original star-box and star meshes. Nine source function bodies from
  `exclamation_box.inc.c` and `sparkle_spawn_star.inc.c` run through a compatibility
  boundary. Exact integral float literals are lowered to integers; US branches
  are selected, rumble and triangle-particle effects omitted. The squash rendering
  in box action 3 is adapted, while its vertical motion and timer are retained.
- Correct source macro preset: `macro_box_star_1` selects box contents 8.
  Correct spawned-star script initialization: second behavior byte 1 and
  `SET_HOME`, followed by the imported star init/loop functions.
- A solid dynamic box using bounds derived from all eight original collision
  vertices, at the original scale of 2. This is an axis-aligned shared collider,
  not the original dynamic-triangle solver.
- Jumping into the box, attacking it, or ground pounding it spawns the box star.
  Star-spawn control flow temporarily freezes movement. Collection sets the
  slide star bit, requests the original `F0` exit, and returns to the castle.
- Original individually placed yellow slide coins with collection state. Their
  original billboard vertices are retained; texture/alpha is a solid flat-color
  approximation. Coin formations and blue-coin switch behavior are not ported.
- HUD: total fixture stars, collected slide coins and the slide star bit.
- Mission state survives area changes and retries. It is RAM state and does not
  survive package reloads or power loss.

The existing unlocked traversal fixture starts with **70 stars and both key
bits**. The slide box star increases its total to 71 once; collecting it again
does not increment it again. This is not original new-save progression. The
under-21-second bonus star remains outside the selected mission.

## Reproduce and build

Run from `C:\Users\Orb1t\Documents\Codex\FPGA-Game-SoC` with LLVM on PATH:

```powershell
$env:PATH = 'C:\Program Files\LLVM\bin;' + $env:PATH
.\scripts\run.ps1 sm64_castle.py --gameplay --out build/castle-gameplay
.\scripts\run.ps1 soc.py portable-game --project build/castle-gameplay/game.project.json --terrain-direct --packed-gfx --integer-mul --geometry-offload --uncapped-render --interpolate-render
.\scripts\run.ps1 test_castle_gameplay.py
```

The local-code output is
`build/mario-castle-gameplay-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json`.
It uses the existing MUL/geometry hardware capabilities. Appending `--sdram-exec`
builds a separate `-exec.package.json` for the already implemented
`sdram-exec-v1` target. It cannot be loaded onto the currently selected Stage 5
image, which does not advertise that feature. Neither command fits or programs
hardware.

To load the local-code package later, using the selected Stage 5 hardware:

```powershell
.\scripts\run.ps1 load_game.py build/mario-castle-gameplay-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json --ip 192.168.7.2
.\scripts\run.ps1 mouse_udp.py --ip 192.168.7.2 --yaw 128
```

The adapter emits `gameplay-coverage.json`: pinned source commit, hashes of
original files/function bodies and generated bodies, model roots/scales,
collision bounds, numeric derivations, macro/script initialization, behavior
inventory and explicit limitations. The normal `sm64_castle.py` command without
`--gameplay` retains the traversal-only port.

Use the existing `mouse_udp.py` sender for the eight-bit input interface: WASD
movement, Space jump, E doors/use, E while airborne ground pound, F/left mouse
attack and R retry. The legacy `keyboard_udp.py` five-bit interface cannot send
attack or door-use buttons.

## Reusable implementation boundary

`sm64_gameplay.py` is the game-specific source adapter. `castle_controller.c`
implements the selected SM64 speed-rule lowering; `castle_gameplay.c` adapts its
objects, mission and save state. `castle_game.c` selects this variant while
retaining the previous `castle.c` traversal package entry point.

Shared services added for other games:

| Interface | Purpose |
|---|---|
| `player_move_horizontal` / `player_step_motion` | External controllers reuse collision and vertical integration. Long motion is split and spatial queries rebound. Legacy `player_step` keeps its original profile behavior. |
| `game_movement_heading` | Camera-relative headings retain the full eight-bit input angle instead of reducing steering to eight global directions. |
| `game_object_resolve_box` | Solid dynamic box landing, ceiling and side responses. |
| `world_draw_instance` | Moving meshes use the existing six-plane terrain clipper, including partially visible objects at screen edges. |
| `animation_step_clip` | A game can select additional original clips without advancing animation during repeated rendering. |
| `game_memory.c` | Explicit freestanding `memset`, `memcpy`, `memmove`; bodies are audited and linked instead of accepting unresolved compiler helpers. |
| Display-list `gsSPBranchList` lowering | Correct N64 tail-call semantics, retaining cache/material state and not returning to the parent list. |

The reusable pipeline remains pinned source adapter â†’ shared scene/world IR â†’
strict target compiler â†’ direct-call game-port ABI â†’ verified package loader.
This is not an automatic translator of arbitrary engine C.

## Validation and limits

The native regression suite executes production game/controller/object/camera/
animation/collision code on the complete imported world, with graphics calls
recorded rather than sent to physical hardware. It covers all five area spawn
landings, jump/ground pound, an original interior area transition, movement,
slope acceleration, solid box top, star spawning/collection/return, and
repeat-safe rendering.

Its continuous slide test supplies normal input words from the original spawn,
traverses the slide, opens the box, collects the star and exits to the castle,
without position injection after the initial spawn and without respawns. The
input/position/mission trace is emitted to
`build/castle-gameplay-tests/full-slide-inputs.json`. Isolated placement tests
are identified separately; neither is a measured FPGA playthrough or FPS result.

The full-system `castle_gameplay_top_tb` runs the linked SDRAM-execution firmware
on the CPU/SDRAM/GPU simulation and checks two presented frames and populated
world geometry. It does not replay the full mission in RTL simulation.

Remaining original-engine work includes the full `MarioState` action dispatch,
original quarter-step wall/floor/ceiling collision, ledges, double/triple/long
jumps, diving, swimming, original Lakitu and cutscene cameras, original door
animation/interaction, NPCs/dialog, caps, audio/particles, other missions and
persistent save storage. The strict current C subset still rejects original
floating-point arithmetic and indirect callback calls. A faithful full-engine
port needs an explicit software-float/runtime and dispatch strategy; SDRAM
execution solves capacity, not those semantics.

No performance improvement is claimed by this feature port. New code/model
payload sizes are build measurements; native replay ticks are functional test
evidence. Board FPS, input-route timing and hardware resource changes require
separate measurement. The previously selected FPGA/game remains active until
a game package is explicitly deployed.

## Recorded checkpoint: CASTLE-GAMEPLAY-001

Evidence is preserved in `docs/benchmarks/castle-gameplay-001/`.

| Verification | Recorded result | Scope |
|---|---|---|
| Host regressions | 188 checks, 23 suites passed | Includes 11 production castle gameplay tests; native execution rather than FPGA timing. |
| Continuous slide mission | 1,059 input updates; slide star bit 1; returned to interior area 1; zero respawns | Native production-code replay, no mid-route position injection. Tick count is functional evidence, not measured board elapsed time. |
| Local-code payload | 41,488 bytes | Initialized CPU image; excludes separate SDRAM assets and zeroed BSS/stack. |
| SDRAM-execution payload | 1,900 local boot/hot-code bytes; 39,652 external code/constant bytes; 12 initialized external-state bytes; 9,856 external BSS bytes | Final linked image measurements. |
| Assets | 887,500 bytes per placement variant | Relocated pointer contents differ between placements. |
| Full-system simulation | Two valid presented frames; 4,128,366 cycles including boot/startup | Linked SDRAM-execution test firmware with retention shortened to 1,000 cycles; not normal boot timing or steady-state FPGA FPS. |
| Physical software load | Complete CPU and asset readback passed on the existing Stage 5 image | Local-code package only; no hardware programming. |
| Physical frame sample | Scratch/frame counter 113 â†’ 173 across one second after two-second warmup | Single short frame-production sample, not movement/mission FPS or an optimization comparison. |
| Baseline restoration | Complete old package readback passed; counter 113 â†’ 173 after restore | The old selected game/image was restored. |

The complete SM64 engine, original new-save progression and a physical full
castle/slide playthrough remain unverified. This checkpoint supplies executable
game code and a reproducible mission test, not a claim of an entire faithful
SM64 castle-engine port.
