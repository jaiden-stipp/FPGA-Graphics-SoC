# SM64 scene conversion and UDP controls

The controllable-character milestone builds on this scene adapter. See
[mario-controller.md](mario-controller.md) for `sm64-mario`, movement, jumping,
collision, and reusable world/actor profiles. This document describes the retained
static viewer; use `--layout scene` with its keyboard sender.

The first target is a flat-colored static section of Bob-omb Battlefield, taken
from `sm64-port/sm64-port` at the commit in `sm64.lock.json`. It contains 184
triangles in two GPU handles. The CPU runs the viewer and controls its camera;
the FPGA performs model/view transforms, clipping, perspective projection,
backface culling, rasterization, Z testing and VGA presentation.

This milestone converts **display-list C and static vertex data**, and compiles
the viewer as RV32I firmware. It does not automatically rewrite arbitrary C,
port Mario movement/collision, run an N64 ROM, or execute the full SM64 engine.
Those need additional explicit lowering/porting work. The selected geometry is
present in the source checkout; this profile does not use extracted ROM textures.

## Commands

Run these from `C:\Users\Orb1t\Documents\Codex\FPGA-Game-SoC`. On this machine,
the bundled Python interpreter is
`C:\Users\Orb1t\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
Substitute that path for `python` if Windows' Python alias is not configured.
The provided Windows launcher selects a real Python installation or the bundled
runtime automatically:

```powershell
.\scripts\run.ps1 soc.py sm64-scene --sim --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout scene
```

```powershell
python scripts/soc.py bootstrap
python scripts/soc.py sm64-scene --sim --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
```

The combined command checks/fetches the pinned source, interprets its selected
display list, generates mesh data, audits the viewer/driver C subset when using
Clang, builds all firmware images, selects the scene
for boot, generates the Quartus project, runs all simulations, and builds the
programming image. Omit `--sim` or `--fpga` to skip those stages.

Individual reusable stages:

```powershell
python scripts/sm64_subset.py fetch
python scripts/sm64_subset.py inspect --source levels/bob/areas/1/1/model.inc.c
python scripts/sm64_subset.py convert --profile profiles/sm64-bob-flat.json
python scripts/soc.py build-fw --app scene --boot scene
python scripts/soc.py quartus-project
python scripts/soc.py build-fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
```

For hand-ported gameplay code, check each C translation unit before integration:

```powershell
python scripts/rv32i_subset.py --source firmware/src/scene.c
```

This uses Clang's C parser, rejects floating-point/64-bit arithmetic and indirect
calls, compiles for RV32I, then checks undefined symbols against the graphics
driver API. OS/heap calls and compiler software multiply/divide helpers fail the
audit. The generated `build/subset/*.json` files record the target, source hash,
functions and external dependencies. It validates an explicit integer/fixed-point
port; it does not automatically translate the full SM64 gameplay engine.

Generated artifacts:

- `build/sm64/scene.obj` and `.mtl`: geometry after interpreting the N64 vertex
  cache and nested display lists, before normalization.
- `build/sm64/conversion.json`: source revision/hash, visited commands, discarded
  appearance state, hardware mesh/triangle/palette counts and conversion scope.
- `firmware/generated/scene_data.h`: constant RV32I C data containing Q8.8
  vertices, indexed triangle/color records and camera rotation tables.
- `build/scene.elf`, `.hex`, `.mif`: compiled scene viewer; `build/firmware.*`
  copies the selected boot image.
- `build/quartus/SoC.sof`: final CPU + GPU + Ethernet programming image.

## Specialized graphics subset

Supported source operations are literal `Vtx` XYZ arrays, `gsSPVertex` loads into
the 32-slot cache, `gsSP1Triangle`, `gsSP2Triangles`, nested `gsSPDisplayList` and
`gsSPEndDisplayList`. The profile names the source file, root display list and
flat RGB replacement for each referenced texture. Original winding is retained.

The named appearance-state policies explicitly discard texture sampling, N64
combiner/AA modes, fog and dynamic lighting. Directional flat lighting is baked
offline into the color palette. Unknown geometry operations, matrix commands,
unresolved symbols, cyclic lists and invalid vertex loads stop conversion.
Changing profiles does not silently grant support for additional geometry
commands. New rules belong in `scripts/sm64_subset.py` with corresponding tests.

The selected geometry is centered and normalized to an 8-unit maximum span,
then quantized to signed Q8.8. Meshes are split at 128 vertices / 256 triangles
per handle, with 16 handles maximum and 255 face colors plus the background.
Degenerate triangles, including those caused by quantization, fail conversion.
No automatic geometry reduction hides missing surfaces. The linker reserves at
least 4 KiB of stack in the 64 KiB RAM and rejects oversized firmware.

To reuse the pipeline, copy the profile, use `inspect` to choose another static
display list, declare every texture replacement, then run `sm64-scene --profile
profiles/my-scene.json`. Lists in this version must resolve within that source
file. World-scale, original vertex colors/normals, UVs, actors, GeoLayout transforms,
animation, collision, transparency, HUD, audio and SM64 gameplay are outside the
first subset. The later game adapter adds source-preserving multi-root terrain,
collision and the selected original Mario hierarchy/clips; see
[mario-controller.md](mario-controller.md) and [stage3-animation.md](stage3-animation.md).
Extracted texture assets and renderer support are still needed for textured ports.

An exported triangulated OBJ can also replace the selected scene:

```powershell
python scripts/scene_assets.py --obj path/to/export.obj
python scripts/soc.py build-fw --app scene --boot scene
```

## Keyboard over UDP

Program `SoC.sof`, connect VGA and the board's **ENET0** port, set **JP1 to MII
before power-up**, and establish a 100 Mb/s link. The inherited network block
uses IP `192.168.7.2`, MAC `02:00:00:00:00:01`, and UDP port `4000`. Configure the
PC Ethernet adapter on the same subnet, for example `192.168.7.1/24`. The FPGA
answers ARP; its minimal receiver is not an ICMP ping server.

```powershell
python scripts/keyboard_udp.py --ip 192.168.7.2 --layout scene
```

| Keys | CPU action |
| --- | --- |
| A / Left arrow | Orbit camera left |
| D / Right arrow | Orbit camera right |
| W / Up arrow | Zoom in |
| S / Down arrow | Zoom out |
| R | Reset camera |
| Esc / Ctrl+C | Stop sender and send neutral key state |

The Windows sender polls global keyboard state while running. It transmits the
full key mask at 60 Hz, drains transport acknowledgements, and reports their
count on exit. The board releases remote keys after 300 ms without a fresh
control message. Duplicates and stale sequences do not refresh that timer.
Stop a sender and wait 300 ms before starting another sender/session. KEY[1]
and KEY3 still provide local left/right controls; KEY[0] resets the SoC.
LEDG[2] indicates recent remote input, LEDG[3] indicates a latched error.

For a fixed-mask connectivity check, without keyboard polling:

```powershell
python scripts/keyboard_udp.py --ip 192.168.7.2 --buttons 2 --seconds 2
```

The control datagram reuses GP transport version 2 (fresh frame ID, sequence 0,
start/end flags 3), containing one CRC-CCITT-protected GF version 2 `setPalette`
envelope. Its four payload bytes are `[255, 0x4b, input_sequence, key_mask]`.
Bits 0..4 mean left, right, forward, back and an application action (reset view
in the viewer, jump in the Mario controller). This reserved envelope
is consumed by `udp_controls`; it cannot write the GPU palette or submit draws.
The key mask crosses the existing asynchronous network FIFOs, then appears in
the CPU's `SOC_BUTTONS` register at `0x40000054`. Camera changes and drawing are
produced exclusively by RV32I firmware.

## Verification

```powershell
python scripts/test_scene_pipeline.py
python scripts/soc.py build-fw
python scripts/soc.py sim --simulator modelsim --full
```

Host tests exercise strict lowering, nested lists, winding, missing rules,
mesh remapping/capacity, invalid OBJ data and the keyboard wire format. RTL tests
exercise real MII packets, clock-domain crossings, CRC rejection, modular input
sequences and timeout release. The complete scene test sends UDP input to the
board wrapper, observes the RV32I camera change, and waits for the resulting
184-triangle frame to reach VGA. On October 7, 2026 the user supplied a photograph
of physical VGA terrain rendering (overlay reads 030 FPS) and confirmed working
UDP keyboard control. These board results are user verified; see validation.md.
