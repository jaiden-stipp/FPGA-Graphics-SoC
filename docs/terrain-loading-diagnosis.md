# TERRAIN-001: movement-dependent terrain faults

October 9, 2026. Status: diagnosis in progress; no confirmed root cause or
hardware performance improvement. User reports missing rendered geometry and
falling through terrain across the castle while moving.

The complete current level package is resident in SDRAM. Movement selects
visible chunks and uploads them into the GPU's resident mesh handles. Collision
queries use separate source-derived surfaces and a padded spatial index; they
do not depend on which terrain meshes are visible or resident in the GPU.

## Measured checks

Raw evidence and the exact diagnostic sources are in
[benchmarks/terrain-001](benchmarks/terrain-001/). Each check below was run once.

| Check | Result | Scope |
| --- | --- | --- |
| Board loader readback | CPU `.text` matches; all 883,124 asset bytes match SHA-256 | Reads backing SDRAM while CPU is held; does not exercise cache reads |
| CPU SDRAM probe on physical board | 220,781 words checked; zero width/repeated-read disagreements; CRC-16 = 17,615, matching host calculation | Word, halfword and byte loads, with intervening reads 4 KiB away to exercise replacements; cache ABI observed as `0x43410101` |
| Native floor-centroid queries | 2,816 samples; zero missing floors and zero indexed/full-scan differences | Covers compiled floor centroids, not arbitrary movement or visual correctness |
| Native movement comparison | 270,336 ticks, including 8,710 cell crossings; zero indexed/full-scan state differences | Eight headings, twelve ticks per heading from each floor centroid in all five areas; both paths use the same production collision arithmetic |
| World pipeline regression suite | 26 tests pass | Includes direct diagnostic submission, cache overflow fallback and large-triangle clipping |

The physical probe restores the original Mario CPU image after completion.
The programmed bitstream's file hash is unknown; the observed ABI establishes
that a compatible cache implementation is active, not which exact SOF was used.
These checks do not prove collision correctness everywhere, absence of transient
memory faults, or correct GPU mesh uploads and clipping during play.

## Direct-terrain comparison build

`WORLD_FORCE_DIRECT=1` suppresses terrain mesh uploads and cached terrain draws.
All visible terrain is transformed and frustum-clipped by the existing CPU path,
then rasterized by the same GPU. Actor meshes, source geometry, physics,
camera, room visibility and SDRAM cache remain in use. This changes both terrain
submission and clipping path, so a better image would not by itself prove a
mesh-upload bug. It is a diagnostic, not a proposed performance optimization.

Build from the repository root, after creating the castle project using the
[existing pipeline](castle-world-pipeline.md):

```powershell
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct
.\scripts\run.ps1 load_game.py build/mario-castle-sdram-direct.package.json
```

This writes separate `-direct` and `-direct-test` packages and preserves the
normal package. The diagnostic asset binary was compared with the baseline and
is byte-for-byte identical. The physical comparison was loaded using only the
27,832-byte CPU segment; its first frame completed and the CPU was released.
Backing assets and the programmed FPGA image were not changed.

The diagnostic package is currently running on the board with the subsequent
[GPU-001 projection correction](projection-precision.md), which required a new
FPGA image and a verified package reload. The earlier readback and CPU probe
above tested the previous bitstream. Hardware visual acceptance and the user's
movement comparison remain pending. There is no measured FPS comparison and no
claim that all reported faults are fixed.

Restore the normal game:

```powershell
.\scripts\run.ps1 load_game.py build/mario-castle-sdram.package.json
```

## Follow-up decision

- If terrain gaps improve: investigate resident mesh replacement, the cached
  transform path and differences between GPU and CPU clipping. Repeat the same
  moving camera sequence through both paths before attributing the cause.
- If gaps remain: investigate shared visibility, projection, depth precision,
  source geometry and camera behavior.
- For falling: capture positions, previous/current supporting surfaces,
  grounded state and floor heights at the failure; verify the physical CPU's
  collision result against an independent source-surface calculation. The
  indexed/full-scan comparison cannot detect a bug shared by both paths.

Retain the full-level source assets. Do not hide missing terrain with a spawn
floor, remove geometry, or interpret this diagnostic as the completed mission.

## Reproducing the recorded probes

The scripts stored under `benchmarks/terrain-001` are exact experiment snapshots,
including addresses and package length for this package. Run them from the
repository root with Clang/LLVM on PATH and the castle outputs already present.
The CPU probe temporarily replaces the game and restores its CPU image; it
requires a connected board at the loader's configured address. Audit scripts
are native-host tests and do not contact the board.

```powershell
$terrainPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $terrainPython docs/benchmarks/terrain-001/terrain_audit.py
& $terrainPython docs/benchmarks/terrain-001/terrain_movement_audit.py
clang --target=riscv32-unknown-elf -fuse-ld=lld -march=rv32i -mabi=ilp32 -O2 -nostdlib -ffreestanding -fno-builtin -mno-relax '-Wl,--no-relax' '-Wl,-T,firmware/link.ld' firmware/start.S docs/benchmarks/terrain-001/sdram_read_probe.c -o build/sdram-read-probe.elf
llvm-objcopy -O binary build/sdram-read-probe.elf build/sdram-read-probe.bin
llvm-nm --defined-only build/sdram-read-probe.elf
# Check probe variable addresses against the snapshot runner before using it.
& $terrainPython docs/benchmarks/terrain-001/run_sdram_read_probe.py
```

The CRC is an integrity check, not proof against every possible corruption.
The independent loader SHA-256 comparison and consistency checks provide
additional evidence. No resume performance claim is supported by this record.

The subsequent [COLLISION-001 investigation](floor-penetration-correction.md)
reproduces horizontal movement through rising floors in the software controller.
Its separate correction has native evidence; the attempted board load failed
before uploading. This does not prove every reported gap or fall has the same cause.
