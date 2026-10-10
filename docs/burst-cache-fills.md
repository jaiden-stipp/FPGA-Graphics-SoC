# BURST-001: eight-word SDRAM cache fills

Experiment date: October 9, 2026. The clock remains 50 MHz. The cache remains
4 KiB, direct-mapped, blocking, write-through, with no write allocation.
Game models, CPU instruction execution, renderer arithmetic and the command
protocol are unchanged by this experiment.

## Reference and implementation

The pre-change source is Git commit `1f3fbf3`; the preserved physical baseline
is `build/quartus-projection/ProjectionSoC.sof`, SHA-256
`8326b76009f681087f3615256ff45f7f7bb5922dc43dfebca2d77387f499105b`.
The initial implementation is commit `a90844e`. That first candidate failed
physical data integrity and is **rejected**, despite passing simulation and
Quartus timing. The subsequent alignment correction is a separate commit.
Exact accepted source revision and artifact hashes are recorded in
`benchmarks/burst-001/measurements.json`.

`rtl/sdram_cache.sv` now issues one aligned request for the whole 32-byte line.
It consumes eight consecutive response beats and writes each to the existing
RAM port. It installs the tag/valid bit and returns the requested word only
after all eight beats arrive. Invalidation still drains an active fill without
installing it, including invalidation on the last beat.

`rtl/sdram_controller.sv` programs mode `0x233`: sequential BL8 reads, CL3 and
single-location writes. It retains closed-page auto-precharge access and the
existing phase-shifted input sampling clock. The read-return state streams the
eight words without backpressure. Controller readiness waits for recovery;
refresh begins eight clocks earlier to reserve room for the longer transaction.
Loader bypass reads drain the entire burst but expose only its first word.
Stores keep the existing byte masks and single-write behavior.

`ENABLE_BURST` propagates through `soc_memory`, `soc_top` and the board wrapper.
Default is 1; `ENABLE_BURST=0` keeps the cache but fills each line through eight
BL1 transactions. Disabling the cache also selects BL1 in the controller.
The MMIO counter layout and ABI remain unchanged; identify the implementation
by its source/bitstream hash rather than the cache ABI alone.

The device family supports programmable BL8 and burst-read/single-write modes;
see the [ISSI SDRAM product brief](https://www.issi.com/WW/pdf/3.3V-SDR-SDRAM.pdf).
The local model is a sparse board-oriented model, not a vendor qualification model.

## Physical rejection and correction

The first candidate returned the wrong data during the CPU benchmark and failed
loader readback at `0x80000000`. The fallback reprogrammed the preserved baseline
and verified the full Mario CPU/asset package before releasing the CPU.

A diagnostic held the CPU, wrote 32 distinct numbered words, and read 24 word
addresses. Every read returned the next word, wrapping within its eight-word
block: word 0 returned word 1; word 7 returned word 0. This demonstrated a
one-beat forwarding misalignment, rather than a game/collision defect.

The corrected burst path forwards the sampled data one core clock earlier.
The sparse model's BL8 return alignment was adjusted using this physical probe;
the old BL1 fixture remains available for comparisons. Consequently, the
calibrated simulation is **not independent proof of SDRAM timing**. Acceptance
requires physical checks as well. The failed candidate, raw logs, numbered-word
results and source snapshot are retained under `rejected-stream/`.

One diagnostic attempt also timed out during Ethernet link negotiation after
programming. Retrying BEGIN with the loader's normal post-programming retry
window allowed the numbered-word test to complete; it was separate from the
confirmed wrong-word failure. One added loader timing fixture initially counted
its extra read inside the cold-fill command measurement; it was moved outside
that interval and the failed log is retained.

## Simulation measurements

Same production bridge/cache/controller fixture, 20 ns clock period:

| Operation | BL1 baseline | Corrected BL8 |
|---|---:|---:|
| Cold cache read | 107 cycles | 19 cycles |
| Repeated cache hit | 3 cycles | 3 cycles |
| SDRAM READ commands per cold fill | 8 | 1 |
| Loader bypass single-word read | 16 cycles | 22 cycles |
| Cache-disabled read | 13 cycles | 13 cycles |

These cycle counts include the fixture's bridge/completion boundaries. The
loader result is a measured regression from draining a full burst; it is not a
measurement of Ethernet transfer throughput. Unit-test toy-backend waits are
kept in the raw logs and must not be substituted for these results.

Tests check every requested word offset with distinct data at bank/row ends,
all SDRAM address bits, signed byte/halfword loads, byte masks, refresh, conflict
replacement, no write allocation, loader bypass and in-flight invalidation.
The real RV32I self-test checks that pipeline registers hold during stalls and
that instructions do not retire twice. Source hashes identify its model revision.

## Physical benchmark and build

The identical 648-byte temporary RV32I benchmark is run three times per image.
It initializes two arrays, then measures 64 cold line reads, 512 warm word reads,
and 512 deliberate direct-mapped conflict misses. Cycle counts include loop
execution and refresh effects, not just SDRAM latency. Phase counters must match
the expected hits, misses and eight returned words per miss. Host checksums and
1,024 exact word comparisons per run check data integrity.

All three runs of each image passed with zero integrity errors, matching phase
checksums, hit/miss counts and eight fill words per miss.

| Physical workload | Baseline cycles (all runs) | BL8 cycles (all runs) | Median reduction, calculated |
|---|---|---|---:|
| 64 cold-line reads | 7239, 7235, 7240 | 1539, 1539, 1539 | 78.7402% |
| 512 warm-word reads | 4098, 4098, 4098 | 4098, 4098, 4098 | 0% |
| 512 conflict reads | 57330, 57335, 57335 | 11794, 11794, 11799 | 79.4297% |

Percentages use `(baseline median - candidate median) / baseline median * 100`.
The corresponding medians are 7,239/1,539, 4,098/4,098 and 57,335/11,794 cycles.
These are three sequential trials per image, not a confidence interval or a
randomized temperature/voltage study.

| Quartus whole-SoC result | Preserved baseline | Corrected BL8 |
|---|---:|---:|
| Logic elements | 20,918 | 20,979 |
| Memory bits | 2,659,668 | 2,659,668 |
| 9-bit multiplier elements | 74 | 74 |
| PLLs | 2 | 2 |
| CLOCK_50 setup slack | +0.199 ns | +0.749 ns |
| Lowest reported slack across summaries | +0.104 ns | +0.116 ns |

Resource delta: **61 logic elements**; no additional memory bits, multipliers
or PLLs. Both builds target EP4CE115F29C7 in Quartus Lite 18.1 Build 625 with
the same pins, SDC, boot firmware and corrected GPU projection source. The
project/output names differ to preserve the baseline. Slack differences include
placement/routing effects and do not establish a new maximum clock frequency.

The final calibrated-model CPU self-test reports **2,325 held cycles**, compared
with **5,892** in the preserved baseline simulation. Its overall run includes a
retention wait, so these stall counts must not be presented as a total-runtime
or FPS reduction. The rejected candidate's 2,368 held cycles and +1.017 ns setup
slack belong to the rejected image, not the accepted results above.

The corrected image was programmed over JTAG. The benchmark runner then
uploaded and readback-verified the complete Mario CPU image (28,936 bytes) and
SDRAM assets (883,124 bytes), and observed the first completed frame with the
CPU released and SDRAM initialized. The running software remains the direct
terrain diagnostic, including the controller collision correction. Visual
rendering and collision acceptance still require gameplay testing.

Quartus and final programming/restoration results are recorded in the evidence
manifest. Neither a positive timing slack nor this microbenchmark establishes
maximum clock frequency or a game FPS improvement. The gameplay rendering and
collision investigations remain separate.

## Reproduce and compare

With ModelSim on PATH, from the repository root:

```powershell
.\scripts\run.ps1 soc.py sim --simulator modelsim --work-dir build/burst-check --tests sdram_cache_tb,sdram_memory_tb,sdram_cpu_tb,udp_loader_tb,soc_memory_tb,soc_mmio_tb
vsim -c -L altera_mf -lib build/burst-check sdram_memory_tb -gBURST_ENABLED=0 -do "onerror {quit -code 1}; run -all; quit -code 0"
vsim -c -L altera_mf -lib build/burst-check sdram_cache_tb -gBURST_ENABLED=0 -do "onerror {quit -code 1}; run -all; quit -code 0"
vsim -c -L altera_mf -lib build/burst-check sdram_memory_tb -gCACHE_ENABLED=0 -do "onerror {quit -code 1}; run -all; quit -code 0"
# Separate project generation; preserve existing QSF/SOF artifacts first:
.\scripts\run.ps1 soc.py quartus-project --disable-burst
```

Regenerate without `--disable-burst` for BL8. Generating a project does not
compile/program it. `BurstSoC.qpf` is the separate build used in this experiment;
its exact QSF, build runner, summaries and logs are archived.

Archived physical runners are experiment snapshots with fixed local tool paths,
symbol addresses and restore-package paths. Before reusing them, compile the
archived C source with RV32I/ILP32, `-O1`, `-fno-builtin`, `-ffreestanding`,
`-msmall-data-limit=0`, `-mno-relax`, `-nostdlib`, `firmware/start.S` and
`firmware/link.ld`. Verify `llvm-nm` output: `burst_errors=0x288`,
`burst_clock=0x28c`, `burst_results=0x290`. The runner holds the CPU to read these
results and restores the full Mario package afterward. A different compiler or
changed source can move these symbols and requires updating the runner.
