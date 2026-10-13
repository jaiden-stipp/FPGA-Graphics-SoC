# SDRAM execution architecture comparison — EXEC-SDRAM-001

October 12, 2026. Baseline commit: `7c90adc8276876095047ea368c86406af4c4d9d8`.

## Decision

Use a hybrid local-RAM/SDRAM executable layout with a **separate instruction
cache whose warm hits meet the existing falling-edge instruction timing**.
Keep boot code and deliberately selected critical routines in local RAM.
Use SDRAM for the larger executable, constants, assets and explicitly placed
state. Preserve the existing data cache and arbitrate complete SDRAM transactions
between the two caches.

This is the best general-purpose candidate in this experiment, not a deployed
upgrade or a measured SM64 performance result. No production RTL, generator,
deployment profile, programmed hardware or game package changed. The running
Mario image remains the audit-fixed image selected before this experiment.
No new synthesis, fit, timing analysis or physical board benchmark was performed.

## What was actually tested

The prototypes use the existing generated RV32I CPU with integer MUL, pipeline
freeze adapters, SDRAM data cache, CL3 controller, capture-clock model and sparse
JEDEC device model. The clock is the existing 20 ns period. Only the controller's
initialization delay is shortened to 20 cycles to speed simulation; measurement
starts after initialization. CPU execution and refresh/command timing are modeled.

Three authored assembly workloads exercise code/data interference, branches,
load dependencies, stores, integer multiplication, absolute indirect calls and
returns. These are synthetic diagnostics, **not traces from the SM64 engine**:

* **Hot routine:** 16 calls to one 36-byte routine; 256 read/modify/write iterations.
* **Alternating conflicts:** 32 calls alternating between two 36-byte routines
  placed 4 KiB apart. Data is deliberately mapped to a conflicting cache index.
  This is an adversarial placement, not evidence that SM64 has this access pattern.
* **Large streaming:** four calls alternating between two 8,196-byte routines,
  each containing 2,048 arithmetic instructions and a return. The second routine
  resides at `0x80020000`, beyond the existing 64 KiB instruction range.

Every design uses a cached SDRAM data path. Local-reference code is linked into
local RAM and establishes a resident-code comparison; it does not solve engine
capacity. The overlay variant copies into a single local slot before a routine
change, retaining the routine if the next call uses it again. Both copy cost and
the extra copy instructions are included in its measured total.

## Simulated cycle results

Lower is better. Counts cover execution through retirement of the checked result,
including memory freezes, dependencies, redirects and overlay copying.

| Architecture | Cache data-array capacity | Hot routine | Alternating conflicts | Large streaming |
| --- | --- | ---: | ---: | ---: |
| Uncached instruction fetch + data cache | 4 KiB D | 50,757 | 101,489 | 165,398 |
| Shared blocking cache | 4 KiB total | 21,844 | 44,603 | 49,288 |
| Separate blocking caches | 4 KiB I + 4 KiB D | 12,810 | 26,581 | 49,288 |
| **Separate fast-hit I-cache + data cache** | **4 KiB I + 4 KiB D** | **6,562** | **14,151** | **25,704** |
| Local resident-code reference | 4 KiB D | 6,525 | 13,026 | 8,228 |
| Local code overlays | 4 KiB D + local code slot | 6,661 | 18,046 | 123,036 |
| Shared blocking cache, equal total capacity | 8 KiB total | 21,844 | 35,824 | 49,288 |

Capacity is derived from the implemented word arrays. It excludes tags, valid
bits and other state and is **not a fitted M9K or logic-element count**. Overlay
storage is part of existing local RAM; it competes with local code/data/stack.
All SDRAM caches use 32-byte lines. This experiment does not select an optimal
instruction-cache capacity, associativity or line size for SM64.

At equal 8 KiB cache data-array capacity, fast split caching uses 69.96%, 60.50%
and 47.85% fewer simulated cycles than this blocking shared-cache implementation
in the three workloads respectively. Those are derived comparisons of these
totals, not board speedups. They combine topology, arbitration and hit-path
differences; they do not isolate the effect of separation alone. A future shared
cache with a fast instruction read port could narrow the difference and was not
implemented here.

The fast split cache costs just 37 cycles beyond the local reference in the hot
test. On the streaming test it still takes substantially longer than resident
local code: caching does not eliminate instruction-bandwidth limits.

## Why the alternatives behave differently

**Uncached fetch** is simple but requests memory for each new PC. This variant
keeps the controller in BL8 mode for the 32-byte data cache: a single-word
instruction read returns its first word after the physical burst drains. It is
not an optimized BL1-only controller comparison. Useful as a functional baseline,
it is a poor default for a large game engine in this configuration.

**Shared caching** reuses one cache but code and data can evict each other and
must share its transaction interface. Increasing capacity helps the deliberately
conflicting placement, but does not remove the request/response delay on warm
instruction hits. The 8 KiB variant is generated as an isolated capacity-
parameterized copy of the existing cache; the production source is untouched.

**Separate blocking caches** reduce code/data interference. However, treating
every instruction hit like a data request still freezes the CPU while the
handshake completes. Separation alone does not provide a fast fetch path.

**Separate fast-hit caching** reads instruction RAM on the falling edge, matching
the existing local-RAM schedule. A valid tag allows the next rising pipeline edge
to proceed; a miss freezes the pipeline until an entire burst installs the line.
The experimental two-client arbiter routes responses to the transaction owner
until every beat has completed. SDRAM remains one shared resource: separate
caches do not give two simultaneous SDRAM transactions or a superscalar CPU.

**Overlays** need no new instruction-fetch hardware on this design and work well
when a small module stays resident. The large test copies 32,784 bytes across four
loads and retires 57,400 instructions versus 8,208 for direct execution. Copying
dominates that diagnostic. Its two simple routines use relative internal branches
and returns, so relocation is uncomplicated. A real engine would need overlay
VMA/LMA linking, resident call trampolines, nested-call rules and safe handling of
function pointers. Arbitrary engine functions cannot be copied with this example
and assumed to work. Overlays remain useful for coarse, infrequent area changes.

## Correctness and evidence

All **21 CPU/controller runs** pass independent expected arithmetic results and
final SDRAM values. Stored values detect lost/repeated update writes. Each freeze
checks that all pipeline PCs remain unchanged and no instruction retires.
For each workload, the five direct-SDRAM designs retire **byte-identical complete
traces** containing PC, instruction, register-write flag, destination and value.
SHA-256 identities are recorded in results; a rolling diagnostic signature is
also retained but is not the basis for the byte-equivalence assertion.

The separate fetch-cache test passes every line offset, warm hits, conflicting
tags, addresses beyond 64 KiB, mid-fill invalidation, final-beat invalidation and
explicit invalidation after code replacement. Partial fills never become valid.
The device model checks refresh and SDRAM command timing throughout.

Two initial harness defects were corrected: the overlay copy temporary initially
used the completion register, and the focused cache test initially observed the
previous combinational hit before a PC-change delta cycle settled. The latter's
raw failing log is retained. Neither was a production hardware change.
The diagnostic linker initially grouped widely separated executable addresses
into oversized sparse ELF files. Explicit load segments corrected that packaging
issue; all section/fixture bytes, complete traces and measured result rows remain
identical. The largest final diagnostic ELF is 29,380 bytes. A fixture-size guard
now rejects an unexpected segment-layout regression.

Full instruction-fetch and MEM stalls can overlap. The reported `i_freeze` and
`d_freeze` counters must not be added without subtracting `both_freeze`. Shared
cache hit/miss/fill counters are aggregate I/D events, despite their `i_*` result
field names; their `d_*` cache counters are zero. Pipeline freeze counters remain
separately attributed.

The snapshots and [raw measurements](benchmarks/exec-sdram-001/results.json)
include [baseline identities](benchmarks/exec-sdram-001/baseline.json), source,
compiler/simulator logs, binaries, full traces and fixture inputs. The archive
manifest records SHA-256 for every archived file. Production sources and the
selected SOF/profile match their captured pre-experiment hashes.

## Production implementation still required

1. Add an opt-in SDRAM instruction-fetch path to `soc_memory.sv`; preserve the
   local falling-edge RAM path. Integrate a separate fast instruction cache and
   complete-transaction arbitration with the existing data path. Keep results
   stable until both fetch and MEM allow global pipeline advancement. The
   prototype explicitly holds MEM completion across an overlapping fetch miss.
2. Define executable ranges, reset/loader priority and instruction-cache
   invalidation. Initially require immutable executable bytes while CPU runs.
   Self-modifying code would require a real instruction-coherence operation;
   the experiments do not implement `FENCE.I` or make executable stores coherent.
3. Extend the linker/startup and package contract: local boot/critical sections,
   SDRAM text/constants/state, nonoverlapping assets and reserved scratch, entry
   address, external BSS initialization and an advertised execution capability.
   Existing loaders must reject executable-SDRAM packages on the old image.
4. Verify loader writes and invalidation through the actual SoC wrapper; test
   redirects during miss handling, byte/halfword data operations, reset during
   outstanding transactions, near-boundary PCs and optional DMA contention.
   The CPU experiments cover aligned word data accesses and do not include GPU,
   Ethernet-loader or DMA traffic. CPU cache hits do not establish whole-SoC
   timing or concurrent-client fairness.
5. Fit the opt-in candidate with the accepted graphics configuration, approve
   timing/resource use, then load a verified diagnostic on the board. Compare
   the same executable and deterministic route against a preserved baseline.
6. Compile and measure the scoped original SM64 gameplay core, including its
   floating-point helpers, before selecting cache size or claiming a game frame
   rate. Instruction capacity and floating-point execution are separate issues.

## Reproduce

With the pinned upstream dependencies already present, LLVM and ModelSim at the
documented local installation paths, run from the repository:

```powershell
.\scripts\run.ps1 compare_sdram_execution.py
```

The driver writes only `build/sdram-execution`, reads the selected deployment
reference for hashes, and invokes Clang/LLVM and ModelSim. It never rebuilds or
programs a Quartus image, changes firmware selection or sends network packets.
Use `--smoke` for the seven hot-workload variants plus the focused cache test.

Resume-safe wording: developed and compared isolated SDRAM execution prototypes
using an existing RISC-V pipeline and JEDEC SDRAM model; verified matching
retirement traces and characterized cache-hit latency, code/data conflicts and
overlay costs. Do not describe these simulation results as physical FPGA or
SM64 gameplay speed improvements.
