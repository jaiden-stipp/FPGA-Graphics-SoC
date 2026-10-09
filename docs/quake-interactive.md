# Interactive Quake scene demo

This milestone adds mouse look, a GPU-rendered HUD, one moving door, one armor
pickup and an animated soldier to the original E1M1 starting region. It is a
scoped demo, not a port of Quake's engine or QuakeC. The CPU/GPU cores, original
Mario logic and original Quake world selection stay unchanged. The owned SoC
input wrapper adds IN v1 packets and one feature register; this requires a new
FPGA image once. Existing keyboard packets and older packages remain supported.

## Run

From `C:\Users\Orb1t\Documents\Codex\FPGA-Game-SoC`:

```powershell
# Original shareware data is the same external PAK used by the Quake scene.
.\scripts\run.ps1 quake_demo.py
.\scripts\run.ps1 soc.py portable-game --project build/quake-interactive/game.project.json
# Stop other keyboard/mouse senders during loading.
.\scripts\run.ps1 load_game.py build/quake-interactive-sdram.package.json
.\scripts\run.ps1 mouse_udp.py
```

Click inside the control window to capture the pointer. Controls are active only
while this window has focus and capture. Tab releases it; Escape stops the
sender. W/S walks, A/D strafes, mouse movement looks horizontally/vertically,
Space jumps, E toggles the nearby door, left mouse or F fires, and R resets the
demo. Input expires after 300 ms without a valid packet. Camera movement has
256 yaw steps and pitch limited to +/-45 degrees; walking retains the shared
controller's eight movement headings.

The HUD reads left to right: red health number, gold armor number, white ammo
number, enemy health bar, door travel bar, and armor availability square
(gold available, green collected). A white crosshair stays centered. The HUD
uses original palette colors and existing GPU triangle commands; no software
framebuffer or host rendering is involved.
It is a camera-attached plane at 272 GPU units, rendered with the world view
because the GPU cannot change view/projection inside a frame. Fixed-point
rounding can move edges slightly; world geometry immediately at the near plane
can occlude portions. A dedicated screen-overlay primitive is future work.

The demo starts on an imported floor beyond the original spawn's blocking wall;
no world faces are removed to make a path. The armor is directly ahead. Continue toward the rising door and
press E within 600 GPU units of its center. The soldier patrols farther ahead,
to the right. Aim at its torso and fire three times to defeat it. The demo starts
with 100 health and 20 rounds; the pickup grants 50 armor. Contact damage is 10
per second, with up to five absorbed by armor. Shots have a six-tick cooldown.
Reset or falling out of the scene restores the objects and counters.

Demo shots use a projected-center target test. BSP ray traversal, weapon models,
projectiles, original enemy AI/QuakeC, source door timing/triggers, sound and
textures are not implemented. This is an explicit set of demo interaction rules.

## Reusable interfaces

`game_services.h`/`game_services.c` provide decoded input, a fixed-point camera,
camera-relative movement mapping, translated object bounds, door motion, one-shot
pickup triggers, animation frame selection, bulk vertex-frame upload and HUD
rectangles/numbers. Game-specific state and behavior live in
`firmware/ports/quake_demo.c`; these services contain no Quake names or models.
Another game can call them from the same three-function `game_port.h` interface.

The shared scene IR holds default actor meshes and the original world. Additional
original model frames are immutable SDRAM tables owned by the custom port, and
are uploaded only when the animation frame changes. This does not introduce a
general skeletal/vertex-animation asset schema or runtime scene streaming.

`quake_demo.py` imports original `progs/soldier.mdl` (all 328 triangles, eight
`run` frames), `progs/armor.mdl` (all 82 triangles) and E1M1 brush model `*1`.
Models keep their topology and source frame poses, with uniform scale, axis
conversion and a documented local floor rebase. The door and pickup are
relocated for this demo. Model faces receive an explicit flat skin-centroid
palette sample; the door uses explicit flat brown. Original textures remain
external and are not mapped by this renderer. The source report records hashes,
frame names, brush identity, origins, placements and approximation policies.

Original MDL seam/animation faces can have zero area in a pose. Actor meshes
explicitly opt into `retain_degenerate_actor_faces`; the compiler retains and
reports those faces so topology is not silently changed. Static world meshes
still reject degenerate/collapsed triangles. The GPU performs its existing
degenerate-face handling.

## Input and hardware contract

An IN v1 envelope is consumed by `udp_controls` before the GPU. It uses existing
GP v2/GF v2 CRC framing and a 24-byte SET_VIEW_MATRIX-shaped payload:

| Bytes | Value |
| --- | --- |
| 0..2 | `49 4e 01` (IN, version 1) |
| 3 | Modular eight-bit sequence |
| 4 | Buttons: left/right/forward/back/jump/fire/use/reset, bits 0..7 |
| 5 | Absolute yaw, 0..255 |
| 6 | Signed pitch, -32..32 |
| 7..23 | Reserved, must be zero |

Absolute angles tolerate packet loss without repeating mouse deltas. Duplicates
and stale sequence values do not change state. MMIO `SOC_BUTTONS` returns buttons
in bits 7:0, yaw in 15:8, signed pitch in 23:16 and extended-input-valid in bit 31.
Legacy packets return zero upper bits. `SOC_INPUT_ABI` at `0x40000064` returns
`0x494e0101`; loader STATUS replies advertise the same signature in statistics
word 10. The host checks it before holding the CPU for a mouse-dependent package.

Target `de2-115-fixed-v2` extends the existing limits with mouse/HUD/object/frame
capabilities. The runtime/asset ABI remains 1; `de2-115-fixed-v1` packages still
validate. Package checks do not guarantee arbitrary game performance.

To rebuild the input wrapper image, use the existing project:

```powershell
.\scripts\run.ps1 soc.py build-fpga --quartus-bin C:\intelFPGA_lite\18.1\quartus\bin64
# After successful timing and assembly:
& C:\intelFPGA_lite\18.1\quartus\bin64\quartus_pgm.exe -m jtag -c 'USB-Blaster [USB-0]' -o 'p;build/quartus/SoC.sof@1'
```

## Validation

```powershell
.\scripts\run.ps1 test_interactive_demo.py
.\scripts\run.ps1 soc.py sim --simulator modelsim --tests soc_mmio_tb,udp_controls_tb,udp_extended_input_tb,udp_loader_tb
.\scripts\run.ps1 soc.py sim --simulator modelsim --full --tests quake_interactive_top_tb
```

Native tests execute the production game module and services, including door
blocking/opening, pickup once, armor absorption, aimed shooting/ammo/cooldown,
frame changes, HUD command submission, movement/jump/reset, input stability,
original topology and pre-upload rejection of old hardware. MII tests exercise
actual Ethernet/CRC, modular sequence wrap, pitch limits, deadman and legacy
keyboard compatibility. Full integration captures post-depth GPU pixels after
the RV32I consumes mouse yaw/pitch, walking and jumping.

Format references: [id Software MDL6 definition](https://github.com/id-Software/Quake/blob/master/WinQuake/modelgen.h)
and [BSP29 definition](https://github.com/id-Software/Quake/blob/master/WinQuake/bspfile.h).
