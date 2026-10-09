# SDRAM game packages

The DE2-115's 128 MiB SDRAM is a CPU data window at
`0x80000000..0x87ffffff`. Instructions, writable game state and the stack stay
in the existing 64 KiB dual-port RAM. Generated immutable level geometry,
collision surfaces, camera surfaces, model vertices and indexed animation
data are linked into `.game_assets` in SDRAM. The original player, camera,
animation evaluator and GPU algorithms continue to consume the same asset ABI.

The `sm64-mario-sdram.json` profile imports all 1,043 opaque terrain triangles
from the four original Bob-omb Battlefield display-list roots, plus the same
212-triangle Mario model and four clips. It uses nine GPU handles and 243 palette
colors. The initial package contains 99,840 bytes of assets and a 15,696-byte
CPU image; local `_bss_end=0x4338`, leaving ample room before the 4 KiB stack.
The subsequent [stage 4 shared runtime](stage4-packages.md) builds a 16,216-byte
Mario CPU image with `_bss_end=0x4540`; asset size and source model data remain
the same. Quake's second package uses 10,516 bytes of code and 36,464 asset bytes.
This is the complete opaque static terrain covered by those roots. Decorative
alpha/decal geometry, dynamic objects, textures, audio and original SM64 gameplay
are still outside the supported subset.

## Build, program and load

Run from the repository root:

```powershell
.\scripts\run.ps1 soc.py bootstrap
.\scripts\run.ps1 soc.py sdram-game --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
```

Program `build/quartus/SoC.sof` through the existing USB-Blaster. The SDRAM
configuration waits for a package before releasing the CPU. ENET0 remains
`192.168.7.2:4000`, JP1 MII, with the PC on `192.168.7.0/24`.

```powershell
.\scripts\run.ps1 load_game.py build/sdram-test-sdram.package.json --wait-self-test
.\scripts\run.ps1 load_game.py build/mario-sdram.package.json
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout mario
```

The first command is a dedicated board memory test and prints a pass only after
the real CPU checks data/address lines, byte masks, signed loads and 100 ms
retention through automatic refresh. The game repeats that test before booting.
The second command holds/reset the CPU and GPU, uploads the CPU image and assets,
reads back every uploaded word, then releases reset. Pause the keyboard sender
while loading: the inherited response transmitter returns completion to the
most recent UDP peer. Retries use new transport frame IDs with the same
idempotent memory operation.

Reload the game after FPGA programming, power loss or KEY[0] hardware reset.
SDRAM is volatile, and its initialization is not a copy of the assets. The R
respawn control leaves the package loaded. A failed upload leaves the CPU held;
rerun the loader after correcting the cause. `load_game.py --status` reads the
initialized/held flags, refresh count and firmware scratch value without
changing CPU state. During the game, a progressing scratch value is the displayed
frame number; `0xdead10xx` indicates a memory-test failure.

The legacy `soc.py sm64-mario` command retains the smaller on-chip asset build.
`build/boot.json` makes the Quartus generator select the corresponding board
parameter, so a legacy image does not require this loader.

## Reusing it for other games

```powershell
.\scripts\run.ps1 soc.py sdram-game --profile profiles/my-game.json
.\scripts\run.ps1 load_game.py build/mario-sdram.package.json
```

The game profile selects assets/normalization/controller configuration without
editing source models. The ELF linker resolves SDRAM pointers in generated tables;
the build extracts the local image and `.game_assets` into two files, avoiding a
2 GiB address gap or an on-chip copy. The versioned JSON manifest records each
segment's address, size and SHA-256. The host validates all files and ranges before
holding the CPU. Loading a different compatible CPU image and asset package
requires no FPGA rebuild. New game logic still needs a supported RV32I port;
this command does not automatically translate arbitrary game engines.

The current CPU cannot fetch instructions from SDRAM and has no cache. GPU mesh
storage remains 16 handles, 128 vertices/256 triangles per handle, and a 256-color
palette. External storage capacity therefore exceeds the currently renderable
resident scene; larger engines need runtime mesh streaming/eviction and a code
execution strategy in addition to asset storage.

## Hardware and transport

The owned generator wraps each upstream pipeline register and register file with
a clock enable. An outstanding external MEM transaction holds every pipeline
stage and suppresses retirement until the result is ready. Load-use hazards,
branch flushes and the existing falling-edge on-chip RAM/MMIO accesses retain
their original behavior. Pinned CPU/GPU source checkouts are not edited.

The controller uses a 32Mx32 organization (two x16 chips), 13 row bits, 10 column
bits and two bank bits. Address mapping is row=`addr[26:14]`, bank=`addr[13:12]`,
column=`addr[11:2]`. It waits 200 us at power-up, precharges all banks, performs
eight refreshes and programs CL3/burst-one/single-write mode. Closed-page accesses
use auto-precharge; refresh has priority every 375 cycles (7.5 us), including
while the CPU is held or idle. Command/data registers launch on CLOCK_50 rising
edges, DRAM_CLK rises 10 ns later, and unconditional I/O registers sample read
data using a PLL clock shifted +4.5 ns, before the controller forwards the sample
on the next CPU cycle. Initialization waits for PLL lock. Refresh, recovery and
I/O paths remain timed rather than false-pathed.

Pin assignments come from [Terasic's DE2-115 User Manual, Table 4-28](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf).
Timing margins use the [ISSI SDR SDRAM family datasheet](https://www.issi.com/WW/pdf/42-45R-S_86400D-16320D-32160D.pdf).

Loader envelopes reuse the existing CRC-protected graphics command transport.
Wire command 11 (`SET_VIEW_MATRIX`) carries 24 bytes:

| Bytes | Field |
| --- | --- |
| 0..2 | `53 44 01` (SD, version 1) |
| 3 | Operation high nibble, word count low nibble |
| 4..7 | Transaction ID, big endian |
| 8..11 | Aligned CPU byte address, big endian |
| 12..23 | Up to three 32-bit words, big endian; target stores little endian |

Operations 1..5 are BEGIN, WRITE, READ, COMMIT and STATUS. READ/WRITE require
the CPU held, initialization complete, one to three words and a range wholly
inside local RAM or SDRAM. MMIO, cross-boundary and unaligned transfers are
rejected. Completion uses the inherited 68-byte `GS` event 2 with the transaction
ID; its 13 statistics words contain signature `0x53440100`, status, three read
words, initialized/held flags, scratch, refresh count, address, count and zeros.
Packet receipt acknowledgements do not confirm a memory write.

## Validation

```powershell
.\scripts\run.ps1 test_sdram_package.py
.\scripts\run.ps1 soc.py sim --simulator modelsim --tests 'sdram_memory_tb,sdram_cpu_tb,udp_loader_tb'
.\scripts\run.ps1 soc.py sim --simulator modelsim --full --tests sdram_mario_top_tb
```

The sparse SDRAM model checks JEDEC command ordering, conservative recovery,
refresh deadlines, delayed CL3 reads and byte masks. The CPU test runs the same
memory self-test as the board and checks pipeline hold/retirement. The MII test
uploads and reads back both memory ranges, rejects invalid writes and exercises
keyboard input after COMMIT. The full-renderer test preloads the SDRAM device
model from the exact asset file, releases the CPU through an actual MII COMMIT,
then checks movement/jumping and captures actual post-depth GPU framebuffer
pixels. It is not a software-rendered preview. Physical self-test results and
frame performance are recorded in [validation.md](validation.md). The GPU fixture
shortens only the boot retention loop to 1,000 cycles; the dedicated CPU/board
tests retain the full 100 ms and game physics still runs on its real 30 Hz timer.
