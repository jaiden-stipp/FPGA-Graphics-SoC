# Equal-capacity cache-line comparison

CACHE-LINES-001 — measured October 10, 2026 on the DE2-115 at 50 MHz.

**Decision: retain 32-byte lines as the default.** 16-byte lines offer a small collision-kernel benefit but slow geometry; 8-byte lines slow both castle kernels. Smaller lines remain selectable for other workloads.

## Controlled configurations

| Line bytes | Data capacity | Direct-mapped lines | SDRAM read burst | Tag bits per line |
|---:|---:|---:|---|---:|
| 32 | 4 KiB | 128 | BL8 | 15 |
| 16 | 4 KiB | 256 | BL4 | 15 |
| 8 | 4 KiB | 512 | BL2 | 15 |

These are design settings, not measured performance. The data array, direct mapping, blocking completion, write-through/no-write-allocation policy, CPU ISA, GPU and game models stay the same. The number of tags/valid bits increases for smaller lines. MRS is 0x233/0x232/0x231 with CL3 and single-location writes. The refresh admission reserve tracks burst length (8/4/2 clocks). No prefetch, early restart, associativity or write-buffer change is included.

## Method and coverage

One identical 3,088-byte RV32I probe ran three times per image. Its SHA-256 is `abd76a715481d3376fcbef7098601a1325b54669b106dad7e91136b25c9e29d2`. Castle assets are identical in every test: `afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`. CPU MMIO cycle counters include loop/arithmetic and refresh costs; hit/miss/fill counters are sampled as differences. Host code independently computes expected collision and geometry hashes from the packaged bytes; every trial must match, and fill words must equal misses × line words.

- Collision: the unchanged production `world_collision` and `player_floor` functions query an 8×8 lattice in each of five areas. A pass makes 320 queries, examines 2,104 floor candidates and finds 182 floor contacts. This includes empty-space queries and is a broad floor-query workload, not a recorded walking route or wall/jump test.
- Geometry: sequential CPU traversal of all chunks reads 8,259 original vertices and 8,278 triangle records, folding every coordinate/index/color. This measures mesh-data loading locality; it does not execute visibility, transforms, GPU rasterization or a complete frame.
- Sparse control: 64 distinct reads with a fixed 32-byte stride, followed by the same reads again. The addresses stay identical for all line sizes.
- Before each cold workload, reads from a separate 4 KiB eviction buffer replace every cache index; eviction cost is outside the measurement. The immediate repeat is measured separately. Collision and geometry span more than the cache, so “repeat” does not imply everything is warm. The sparse repeat is entirely hits.

## Physical cycle results

Median of three trials; lower is better. Baseline is the original accepted BL8 bitstream. Percentages below are calculated from medians, not separate measurements.

| Workload | Original 32 B | 16 B | Change | 8 B | Change | Rebuilt 32 B |
|---|---:|---:|---:|---:|---:|---:|
| collision_cold | 683,981 | 683,074 | -0.133% | 690,294 | +0.923% | 683,957 |
| collision_repeat | 683,991 | 683,057 | -0.137% | 690,302 | +0.923% | 683,991 |
| geometry_cold | 491,988 | 512,638 | +4.197% | 554,482 | +12.702% | 491,988 |
| geometry_repeat | 491,992 | 512,614 | +4.192% | 554,476 | +12.700% | 491,992 |
| sparse_cold | 1,675 | 1,410 | -15.821% | 1,282 | -23.463% | 1,675 |
| sparse_repeat | 642 | 642 | +0.000% | 642 | +0.000% | 642 |

Every individual trial and checksum is preserved in the raw JSON files; ranges are not discarded. All four images passed all checksums. The rebuilt 32-byte configuration has the same hit/miss/fill counts as the original image and cycle counts consistent with the variation across repeated trials.

## Misses and fill traffic

Cold pass counters below. Fill bytes = measured fill words × 4. This measures SDRAM data traffic; it does not prove that each unrequested neighboring word was unused later.

| Workload | Line bytes | Read hits | Read misses | Fill words | Fill bytes |
|---|---:|---:|---:|---:|---:|
| collision_cold | 32 | 15,748 | 2,828 | 22,624 | 90,496 |
| collision_cold | 16 | 14,882 | 3,694 | 14,776 | 59,104 |
| collision_cold | 8 | 13,431 | 5,145 | 10,290 | 41,160 |
| geometry_cold | 32 | 55,495 | 2,692 | 21,536 | 86,144 |
| geometry_cold | 16 | 52,886 | 5,301 | 21,204 | 84,816 |
| geometry_cold | 8 | 47,682 | 10,505 | 21,010 | 84,040 |
| sparse_cold | 32 | 0 | 64 | 512 | 2,048 |
| sparse_cold | 16 | 0 | 64 | 256 | 1,024 |
| sparse_cold | 8 | 0 | 64 | 128 | 512 |

The collision workload fetches fewer words with smaller lines, but misses more often. The production collision kernel also performs substantial arithmetic and control work. Reduced fill traffic produces very little total-cycle benefit at 16 bytes and a regression at 8 bytes; traffic reduction alone is not a speedup measurement. Geometry fill traffic changes little while miss count rises sharply; each miss repeats SDRAM activation/CAS/recovery overhead. This explains why the larger line wins geometry even though its isolated miss takes longer.

## Fitted resources and timing

Measured whole-SoC Quartus Lite 18.1 Build 625 summaries; every image passed all reported timing summaries at the existing clocks. Placement/routing changes in slack are not a maximum-frequency measurement.

| Image | Logic elements | Memory bits | 9-bit DSP elements | PLLs | CLOCK_50 setup slack ns | Min reported slack ns |
|---|---:|---:|---:|---:|---:|---:|
| baseline32 | 20,979 | 2,659,668 | 74 | 2 | 0.749 | 0.116 |
| candidate16 | 21,467 | 2,661,588 | 74 | 2 | 0.761 | 0.110 |
| candidate8 | 22,790 | 2,665,428 | 74 | 2 | 0.653 | 0.103 |
| candidate32 | 20,979 | 2,659,668 | 74 | 2 | 0.749 | 0.116 |

## Simulation and correctness

| Line bytes | Burst cold read cycles | Hit cycles | Loader bypass read cycles | BL1 cold fill cycles |
|---:|---:|---:|---:|---:|
| 32 | 19 | 3 | 22 | 107 |
| 16 | 15 | 3 | 18 | 55 |
| 8 | 13 | 3 | 16 | 29 |

These are actual controller/bridge/device-model simulation results, not board latency measurements. Each burst miss uses one READ; BL1 fills use 8/4/2 READs. Cache and controller tests passed all three sizes in burst and BL1 modes, including every critical-word offset at row/bank ends, all address lines, signed byte/half loads, masked stores, refresh, conflicts, no write allocation, loader bypass, and in-flight/last-beat invalidation. Real RV32I self-tests passed at every size with pipeline holding and no duplicate retirement. UDP-loader protocol/readback tests passed. The cache-disabled 8-byte-parameter control retains 13-cycle single-word reads and loader reads. The sparse SDRAM model retains the earlier physical first-beat calibration; this is not independent vendor-model timing qualification.

On each physical image, the full assets and temporary eviction buffer were uploaded/readback-verified before the probe. After measurement, the complete original Mario CPU and assets package was uploaded/readback-verified again and completed frames. This verifies data loading and execution; no automated visual traversal/collision regression claim is made. Existing depth/rendering issues are outside this experiment.

## Supplementary standing Mario observations

Three windows per candidate, each with 12 status samples separated by 0.25 seconds. Each window records actual elapsed time and completed-frame delta. Player position was checked after each window; all were (-1328, 260, 4664). Camera/input were not scripted, so these are supplementary observations, not a controlled traversal benchmark. Frame-counter quantization over about 2.75 seconds limits resolution; tiny FPS differences are not evidence of a gain. CPU/stage globals are last-published/partial-next-frame snapshots and must not be added to infer frame time.

| Image | Individual observed FPS |
|---|---|
| candidate32 | 20.246, 20.000, 20.000 |
| candidate16 | 19.892, 20.000, 20.000 |
| candidate8 | 19.884, 19.892, 19.884 |

The standing view remains about 20 FPS across sizes. This experiment does not establish a game-FPS improvement.

## Selection and reuse

Retain 32 bytes: geometry is fastest, collision nearly ties 16 bytes, and tag/valid overhead is lowest. 16 bytes remains useful to try for a measured collision-heavy workload; 8 bytes benefits truly sparse reads but loses both tested castle kernels. No unmeasured game-frequency weighting is used to invent an overall speedup. A traversal replay with input/camera control would be needed to choose differently for a specific complete game.

Generate a selected configuration with `python scripts/soc.py quartus-project --cache-line-bytes 16` (or 8/32). `--disable-burst` still compares BL1 filling without changing the selected cache line or total capacity. Generation does not build or program hardware.

From the repository root, on the recorded Windows LLVM/Quartus/ModelSim setup, reproduce the experiment after recreating the same castle direct package:

```powershell
python scripts/soc.py portable-game --project build/castle/game.project.json --terrain-direct
python scripts/cache_line_probe.py
python docs/benchmarks/cache-lines-001/run_line_tests.py
python docs/benchmarks/cache-lines-001/build_cache_lines.py
python scripts/cache_line_measure.py --size 32 --sof build/quartus-burst/BurstSoC.sof --label baseline32
python scripts/cache_line_measure.py --size 8 --sof build/quartus-line8/CacheLine8SoC.sof --label candidate8
python scripts/cache_line_game_sample.py --size 8 --label candidate8
python scripts/cache_line_measure.py --size 16 --sof build/quartus-line16/CacheLine16SoC.sof --label candidate16
python scripts/cache_line_game_sample.py --size 16 --label candidate16
python scripts/cache_line_measure.py --size 32 --sof build/quartus-line32/CacheLine32SoC.sof --label candidate32
python scripts/cache_line_game_sample.py --size 32 --label candidate32
```

The build helper uses the preserved QSF template, separate outputs and checks timing before assembly. Test/measurement scripts use local tool paths; edit tool locations when reproducing on another host. The probe builder derives the area address/count from the newly packaged assets and recomputes golden hashes; any changed package is a new experiment. The physical runner verifies the original baseline hash or candidate timing summary, checks data/counter results and restores Mario in `finally`; on measurement failure it first restores the proven BL8 bitstream. Reproduction requires locally supplied game assets and the prior baseline SOF; neither is committed as game data.

## Preserved references

- Original source: `b4616a3370484ada1dc5597da195fa9820376600`.
- Candidate RTL/probe source: `a75c02b4e8bc099231aaf4514daa2cb57574d480`.
- Baseline and candidate SOFs remain in separate ignored build directories; exact hashes and all raw trial values are in [measurements.json](benchmarks/cache-lines-001/measurements.json).
- [Raw evidence directory](benchmarks/cache-lines-001/) contains simulation logs, QSF snapshots, Quartus summaries/logs, compiler version, own probe binary/config/map, physical trial JSON and source snapshots; game assets are referenced only by hashes.
- Selected FPGA image SHA-256: `b9386eb9aad671dff8313ca61a22b6e04874dc22ab1e94f42c2732790576b4ce`. Mario is restored on this 32-byte image.

Resume-safe statement: “Benchmarked equal-capacity BL2/BL4/BL8 SDRAM cache fills on an RV32I FPGA SoC with production collision queries and original mesh-data traversal, and retained 32-byte lines based on measured locality/resource tradeoffs.” Do not claim that shrinking lines improved game FPS.
