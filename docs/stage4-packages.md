# Stage 4: Mario and Quake on one SoC

Stage 4 provides two distinct packages: animated Mario on original opaque
Bob-omb Battlefield terrain, and a first-person explorer of **Quake E1M1's
original starting area**. Both execute on the RV32I CPU, store immutable assets
in SDRAM and submit meshes through the same GPU interface. Switching packages
requires no changes to CPU, GPU, Ethernet or SDRAM RTL.

## Build, load and control

Run from the repository with the verified SDRAM FPGA image already programmed:

```powershell
# Downloads the pinned original shareware archive, extracts data only and builds both packages:
.\scripts\run.ps1 soc.py game-packages --fetch-quake
# Alternatively, supply an existing original shareware PAK:
.\scripts\run.ps1 soc.py game-packages --pak C:\path\to\pak0.pak

# Stop the keyboard sender while uploading, then choose one:
.\scripts\run.ps1 load_game.py build/quake-sdram.package.json
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout quake

# To switch back, stop the sender and run:
.\scripts\run.ps1 load_game.py build/mario-sdram.package.json
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout mario
```

Quake controls: **W/S** or Up/Down walk; **A/D** or Left/Right turn;
**Space** jumps; **R** returns to the original spawn. Esc stops the keyboard
sender. The camera has fixed pitch; walking uses the existing controller's
eight compass directions, selected relative to the 64-step camera heading.
Crossing the imported region boundary respawns the player.

The build requires `soc.py bootstrap` dependencies and the pinned SM64 checkout.
It writes both packages without changing `firmware.mif`, the selected boot image
or the Quartus project. A fresh board setup is described in [sdram.md](sdram.md).
Downloads use the archive at [idgames' original shareware location](https://www.gamers.org/pub/idgames/idstuff/quake/quake106.zip).
Only archive data is extracted; the installer is never executed. Windows uses
its libarchive `tar.exe`; a fresh Linux setup needs `libarchive-tools`.

Uploads hold the CPU and GPU, replace executable and assets, read back every
word and release the CPU. Each game runs the full 100 ms SDRAM retention test
before rendering. Reload after programming, power loss or KEY[0] reset.

## Original geometry and explicit conversion limits

`profiles/quake-e1m1.json` selects whole world-model faces overlapping a region
within 768 original units of `info_player_start`. It retains **786 triangles in
five GPU handles**, with 167 floor and 619 wall triangles. The complete static
world contains 14,752 triangles and exceeds resident mesh capacity. Omitted
faces, unsupported materials and source identities are recorded in
`build/quake.conversion.json`.

The adapter preserves selected source vertex positions and polygon topology,
triangulates polygons, applies a uniform scale of four, changes Quake's Z-up
coordinates to GPU Y-up and adjusts winding for that axis reflection. The
spawn and facing come from the original map. Geometry is checked independently
against the original BSP records. Colors come from each original texture's
average RGB, modulated by its first lightmap style; the GPU renders flat colors.
Sky/liquid/clip/trigger materials are explicitly omitted.

The near plane is 257 GPU units: the unchanged GPU stores the low eight bits
of `floor(65536 / camera_z)`. A smaller near plane can wrap inverse depth and
erase nearby surfaces. Scale, eye height and physics values are normalized
together, preserving source proportions and movement relative to the map.

This is a scene explorer using shared movement and triangle collision, rather
than a port of Quake's engine or physics. Enemies, weapons, brush-model doors,
triggers, entities, textures, audio and gameplay are not implemented. The source
PAK remains external build data. The profile/report pin its hashes; source ZIPs
exclude the downloaded archive and PAK. BSP parsing follows id Software's
[format definitions](https://raw.githubusercontent.com/id-Software/Quake/master/WinQuake/bspfile.h)
and [surface renderer](https://raw.githubusercontent.com/id-Software/Quake/master/WinQuake/gl_rsurf.c).

## Shared package and runtime contracts

[game-package-v1.schema.json](../schemas/game-package-v1.schema.json) describes
the manifest. Existing transport-only version 1 manifests remain loadable.
New manifests add a `soc-game-assets` version 1 record:

| Field | Contract |
| --- | --- |
| Runtime | ABI 1, direct RV32I C calls, no OS, heap or indirect dispatch |
| Meshes | Signed GPU Q8.8 positions; indexed triangles; at most 16 handles, 128 vertices and 256 triangles per handle |
| Appearance | At most 256 RGB palette entries; explicit flat color policy |
| Collision | Triangle ABI with Q12 normals; floor/wall counts and physics configuration |
| Animation | Original indexed joint/clip ABI with Q14 transforms, or explicit `none` |
| Configuration | Module, spawn, physics, camera and game settings |
| Provenance | Source profile and SHA-256; adapter report retains detailed source identities |
| Segments | Local executable at 0, immutable assets at `0x80000000`, sizes and SHA-256 |

`load_game.py` validates content versions, capacity, hashes, addresses, alignment
and overlap before holding the CPU. Metadata describes linked binary assets;
the FPGA does not parse arbitrary pointers from it. Executable and assets must
be built and loaded together. Asset layout changes require relinking.

`game_runtime.h` shares descriptor validation, mesh/palette upload, input,
wrap-safe 30 Hz timing with bounded catch-up, and displayed-frame completion.
Each game owns its update state and draws through the original typed GPU API.
Mario's player, camera, skeletal animation, source geometry and clip data remain
unchanged; only duplicated runtime plumbing moves to the shared module.
`first_person.c` adds a view/input adapter around the same collision controller.

The SM64 adapter remains in `game_assets.py`/`sm64_subset.py`; `quake_assets.py`
handles PAK/BSP data. An optional authored Beacon Run profile and native fixture
exercise the same contract independently of either source game.

## Validation

```powershell
.\scripts\run.ps1 test_game_packages.py
.\scripts\run.ps1 test_quake_pipeline.py
.\scripts\run.ps1 soc.py sim --simulator modelsim --full --tests quake_sdram_top_tb
.\scripts\run.ps1 soc.py sim --simulator modelsim --full --tests sdram_mario_top_tb
.\scripts\run.ps1 diagnose_quake.py
```

Host tests check original BSP provenance, all camera headings, walking, wall
stops, jumping, landing, reset and region bounds. Runtime tests cover capacity
rejection, upload failures, clock wrap/catch-up, input/frame IDs and linked
package compatibility. Full tests use actual MII controls, RV32I execution,
SDRAM and post-depth GPU frame captures. See [validation.md](validation.md) for
results and physical package switching.

The final coverage comparison finds 2/34 interior background pixels in the
standing/moving frames, within the 64-pixel diagnostic tolerance (under 0.09%
of a frame). Small pixel cracks remain in the moving view; this milestone does
not establish pixel-perfect raster coverage. Renderer precision needs a
separate investigation before treating this as a finished visual port.

Ethernet remains the loading path. Larger engines require deliberate ports,
streaming/culling and code capacity work. Future SD loading can feed the same
segment contract; no SD controller or filesystem is included.

