# SDRAM data cache

The cache sits between `sdram_bridge` and `sdram_controller`. It caches only
CPU SDRAM data accesses. Instructions, local RAM and MMIO retain their paths.
The upstream CPU and GPU sources and game models are unchanged.

Default configuration: 4 KiB data, 128 direct-mapped lines, 32 bytes per line, one
outstanding request, write-through and no write allocation. Addresses entering
the cache are 25-bit word offsets within SDRAM; bits 2:0 select a word, 9:3 a
line, and 24:10 its tag. Byte/halfword alignment and sign extension stay in the
existing bridge. Byte-enable stores update a matching line and always wait for
the backing SDRAM write to finish. There are no dirty lines to flush.

The data array uses a synchronous read intended for Cyclone IV M9K inference.
Valid bits and tags are separate. Synthesis/fitting reports, rather than the
array declaration alone, determine actual resource consumption.

A default-size miss fetches all eight words with one aligned BL8 SDRAM READ. The CPU
resumes only after the complete line arrives. `ENABLE_BURST=0` retains the
independent single-word transactions for comparisons. No
prefetching, early restart, write buffer or nonblocking misses are implemented.
The [burst-fill record](burst-cache-fills.md) separates the original baseline
from the new simulation and physical-board measurements.

`load_hold` bypasses and invalidates the cache. CPU reset also invalidates it.
An in-flight fill drains without installing a valid entry after invalidation;
SDRAM reset resets the cache and controller together. Loader readback accesses
therefore reach backing SDRAM. The existing loader sequence holds the CPU before
transferring data. Other future SDRAM writers, including GPU DMA, would require
explicit coherence/invalidation handling.

`ENABLE_CACHE=0` on `de2_115_soc_top`, `soc_top` or `soc_memory` selects the old
direct bridge-to-controller path for controlled comparisons. Default is 1;
`ENABLE_SDRAM=0` still removes the entire SDRAM path. Regenerating the Quartus
project through `soc.py quartus-project` includes the new cache source.
Use `soc.py quartus-project --disable-cache` to generate an uncached baseline;
regenerate without that flag to select the cache again. Generating a project
does not compile or program it.

`ENABLE_BURST=1` is propagated through the same three modules. Use
`soc.py quartus-project --disable-burst` to keep the cache with BL1 fills.
When the cache is disabled, the controller also uses BL1. With burst mode
enabled, loader bypass reads drain the selected burst before returning its first word;
single-word writes retain byte masks and the SDRAM single-write mode.

`CACHE_LINE_BYTES` supports 8, 16 and 32 (default) through the board wrapper,
SoC, memory, cache and controller. Total data capacity stays 4 KiB: these sizes
use 512, 256 and 128 lines respectively, with BL2, BL4 and BL8 SDRAM reads.
Tags remain address bits 24:10; the word-offset and line-index widths change.
Smaller lines require more tag/valid storage. Use
`soc.py quartus-project --cache-line-bytes 16` to select a comparison build.
The [line-size experiment](cache-line-comparison.md) records physical workload
results and explains the retained default. The cache ABI is unchanged; use the
bitstream hash/QSF parameter to identify the tested size.

## Diagnostics

Read-only aligned word registers at the graphics MMIO base `0x40000000`:

| Offset | Value |
|---|---|
| 0x68 | Cache ABI `0x43410101`; zero when disabled |
| 0x6c | Cached CPU read hits |
| 0x70 | Cached CPU read misses |
| 0x74 | Words returned during cache line fills, including discarded fills |
| 0x78 | Accepted stores, including loader bypass stores |
| 0x7c | Cache state-machine cycles spent outside IDLE, including loader accesses |

Counters are 32-bit, wrap modulo 2^32 and reset on SDRAM reset. CPU reset/loading
invalidates lines but does not clear counters. They are live, not an atomic
snapshot. Use differences across a defined interval and do not call busy cycles
CPU stall cycles: their boundaries differ. Bypassed reads do not increment
hits/misses. A future measurement routine can copy these registers into local
RAM; this change does not modify game execution to do that.

## Reproduce functional simulation

With ModelSim tools on PATH:

```powershell
.\scripts\run.ps1 soc.py sim --simulator modelsim --work-dir build/cache-simlib --tests sdram_cache_tb,sdram_memory_tb,udp_loader_tb,soc_mmio_tb,soc_memory_tb
vsim -c -L altera_mf -lib build/cache-simlib sdram_memory_tb -gCACHE_ENABLED=0 -do "onerror {quit -code 1}; run -all; quit -code 0"
.\scripts\run.ps1 soc.py sim --simulator modelsim --work-dir build/cache-cpu-simlib --tests sdram_cpu_tb
```

The CPU test requires the existing `build/sdram-test-sdram.hex` fixture, generated
by the `soc.py sdram-game` software build path (without `--fpga`). That command
also regenerates the Mario boot artifacts; preserve a desired boot build before
using it solely to recreate the test fixture. The cache unit test uses a synthetic
handshake memory; the memory integration test uses the production SDRAM
controller and device model. These are not physical-board benchmarks.

See the [hardware improvement record](hardware-improvement-record.md) for raw
evidence, measured limitations, synthesis status and permitted resume claims.

## Original CACHE-001 build status and separate candidate

The first candidate passed Quartus synthesis, fit, reported timing constraints
and assembly. Its file is `build/quartus-cache/CacheSoC.sof`. The board has not
been reprogrammed, and the prior `build/quartus/SoC.sof` is preserved.

To recreate a separate cache build after generating `SoC.qsf`:

```powershell
$cacheQsf = (Get-Content SoC.qsf -Raw).Replace('PROJECT_OUTPUT_DIRECTORY build/quartus', 'PROJECT_OUTPUT_DIRECTORY build/quartus-cache')
Set-Content CacheSoC.qsf $cacheQsf
Set-Content CacheSoC.qpf 'PROJECT_REVISION = "CacheSoC"'
# With the Quartus Lite bin64 directory on PATH:
quartus_map CacheSoC
quartus_fit CacheSoC
quartus_sta CacheSoC
# Inspect the timing summary and require nonnegative reported slack first:
quartus_asm CacheSoC
```

The actual candidate assignments are archived in the
[evidence directory](benchmarks/cache-001/CacheSoC.qsf.txt). An on-board cache
benchmark needs a matching uncached build and identical software/input workload;
historical software FPS samples cannot substitute for that comparison.
