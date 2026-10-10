# CPU render function profiling: RENDER-PROFILE-001

Follow-up: [MUL-001](integer-mul.md) implements integer multiplication and records physical improvement using both normal gameplay and a separate controlled original-idle-pose fixture. The assessment below is the pre-MUL profiling record.

Measured on the physical DE2-115 on October 10, 2026. Terrain vertex transforms/outcodes are the largest individually measured CPU render section. Integer multiplication is the strongest general CPU hardware candidate; greater use of the existing GPU terrain path is also worth evaluating after its precision and fallback behavior are validated. Neither optimization was implemented or measured here.

Baseline source is `3ac198d`; optional profiling implementation is `9ead800`. The existing counter-enabled FPGA image was reused, without RTL changes. All measurements use the configured 50 MHz clock, original castle assets and `WORLD_FORCE_DIRECT=1`. The exact original FPGA image and Mario package are restored after collection.

## Physical results

Three trials per case, after a stationary warmup. Each trial records approximately five seconds of frame progress and then captures one atomic completed-frame snapshot. These are three sampled frames, not a distribution of every frame or a complete castle traversal. The moving case uses repeating wall-clock keyboard controls; its endpoints and simulation ticks differ between trials. Raw snapshots, input schedules, hashes and derived medians are in [measurements.json](benchmarks/render-profile-001/measurements.json).

| Measured section | Standing median cycles | Standing ms | Share of detailed render | Moving median ms |
|---|---:|---:|---:|---:|
| Terrain vertex transforms and frustum outcodes | 732,782 | 14.65564 | 43.626% | 14.65538 |
| Triangle classification and six-plane clipping | 297,742 | 5.95484 | 17.726% | 6.33652 |
| Animation joint rotations and hierarchy composition | 109,392 | 2.18784 | 6.513% | 2.14816 |
| Animation vertex posing and grounded sole adjustment | 160,161 | 3.20322 | 9.535% | 3.20296 |
| Chunk visibility/residency selection | 11,346 | 0.22692 | 0.675% | 0.22692 |

Detailed standing render median is 1,679,707 cycles (33.59414 ms); moving median is 1,802,912 cycles (36.05824 ms). The two animation render sections together have a standing median-sum of 5.39106 ms. Transform/outcodes, clipping and animation together have a median-sum of 26.00154 ms, approximately 77.4% of the detailed standing render interval. Summing separate medians is a descriptive breakdown, not a new paired timing measurement. Command submission is timed separately by the existing profiler: standing remains 294,210 cycles (5.88420 ms), with zero FIFO wait span.

Animation state stepping is in the update phase, rather than rendering: standing snapshots record 109 cycles per call, with one or two calls depending on catch-up updates. Camera work is also in update: approximately 39,278 cycles (0.78556 ms) per standing call. Moving snapshots contain one or two update calls; do not treat the doubled frame total as a doubled per-update cost.

All detailed snapshots record eight direct mesh transform batches and 785 source-triangle classification/clipping calls per frame. These clipping timings include trivially accepted/rejected triangles, polygon copies and intersections; they exclude output triangulation/packing and `gfx_command`. The vertex timing includes source reads, matrix arithmetic, six frustum tests and outcode storage. It is not a pure multiplication timer. Joint timing includes channel/sine reads, local rotations and parent composition. Skin timing includes source reads, joint transforms, output scaling and sole correction.

## Instrumentation overhead and correctness limits

The original 53-word CPU/GPU frame ABI is unchanged. `SOC_PROFILE_DETAIL` adds a separate double-buffered 16-word detail record: seven pairs of elapsed cycles/calls, a completed frame ID and ABI `0x44540101`. Both records use the same slot, committed only after both are written. The loader holds the CPU before reading and rejects mismatched detail frame IDs/ABI.

Section timers read `SOC_CYCLES`; they include timer access and call-entry overhead before the ending read. Accumulator bookkeeping after the ending read remains in the enclosing phase, outside the section total. No overhead subtraction is applied. The scopes do not nest with each other; their work is nested within the existing update/render phases. Visibility selection includes residency bookkeeping, and would include uploads if this timer were used on a resident build; the measured direct build performs no terrain uploads.

The new control run reproduces 1,655,341 standing render cycles. At matched completed frame 167, detail profiling measures 1,679,560 cycles: a net increase of 24,219 cycles, 0.48438 ms or 1.463%. This is the combined profiling/source/code-generation difference, not an isolated measurement of the timer instructions. The seven GPU raster-event counts match in this pair: submitted 444, clipped 6, culled 196, bounding-box pixels 263,682, inside 91,148, depth rejects 6,131, written 85,017. GPU timing counters differ with submission scheduling. Matching event counts do not replace framebuffer checks or complete traversal validation.

Median observed FPS is 19.977 for control standing, 19.988 for detail standing and 19.988 for detail moving. These windows establish no meaningful performance gain. The instrumented firmware is 30,288 bytes; the ordinary profile control is 29,960 bytes. Original firmware remains 28,936 bytes. All game asset bytes are unchanged: 883,124 bytes, SHA-256 `afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`.

The active detail build passes specialized RV32I C audits for all 15 production translation units. Eight animation tests and 29 world-pipeline tests pass, including original-channel/pose comparisons, geometry preservation, collision and command ordering. A fresh uninstrumented build is byte-identical to the preserved original CPU and assets. Existing geometry/collision defects are not claimed fixed.

## Integer multiplication assessment

Source inspection shows `fixed_mul` in `firmware/src/player.c` implements low-32-bit multiplication with a signed-magnitude setup and a shift/add loop. A terrain vertex transform calls it nine times; animation uses it for rotation composition, joint translations, posed vertices and scale conversion. This is an inference about an optimization target from measured hot sections plus source code, not a measured percentage of cycles spent inside multiplication. Clipping additionally uses a 12-step fractional interpolation routine; a multiplier alone would not remove that division-like work.

The next general hardware experiment should be an integer `MUL` operation and a controlled replacement of `fixed_mul`, preserving its low-32-bit wrap behavior. This can benefit multiple game adapters, animation and collision without changing imported models or floating-point policy. Keep the existing software routine as the RV32I fallback. Do not globally enable an ISA target that also emits unsupported multiply-high or divide instructions.

Implementation touches the decoder/ALU control, EX result selection, forwarding and writeback. A multi-cycle unit additionally needs an explicit execution-busy/advance protocol: younger instructions must wait, older instructions must not execute or retire repeatedly, and memory-freeze statistics must remain distinct from multiply waits. The existing `soc_stall` is a global memory hold; blindly reusing it would mislabel arithmetic waits. A one-cycle multiplier may instead lengthen the EX timing path. Resource use, achievable timing and game benefit require a separate fit and physical comparison. No speedup, DSP cost or frequency estimate is claimed from these profiles.

Acceptance should include signed operands, zero, `INT_MIN`, overflow/wrap equivalence, dependent instructions, branch flushes, memory freezes and exactly-once retirement, followed by identical game command/raster checks and the same standing/moving profiling workload. Select the implementation from measured cycles and fitted timing, rather than assuming single-cycle arithmetic is best.

## Greater GPU transform use

`indexed_mesh_store.sv` already provides mesh matrices and integer multipliers, with 16 handles, 128 vertices and 256 triangles per handle. Mario reserves two handles. The measured direct view has eight terrain batches, but this does not prove every later view fits; retain an unbounded visible-scene CPU fallback. `world_prepare`/`world_draw` already implement the optional resident terrain path.

There are two obstacles to a useful comparison. First, mesh and view transform outputs saturate to signed 16 bits before later GPU clipping. CPU terrain uses wider intermediates and clips before packing into signed 16-bit commands. GPU clipping is not identical to the CPU's explicit near/far/six-plane policy. Re-enabling resident terrain must therefore validate overflow, near-plane crossings, far terrain, seam/depth behavior and camera movement, especially given prior rendering defects.

Second, `world.c:matrix()` currently transforms every source vertex to prove the indexed path is representable. It can be called while validating cached meshes, during admission, and again at draw time. Simply enabling the path therefore retains substantial CPU transform work. A conservative bounds-based representability proof, with CPU fallback for inconclusive bounds, could remove those per-vertex admission checks without changing source meshes. That should be evaluated as a separate software experiment, comparing cold uploads and steady-state work independently.

The existing GPU transforms vertices per triangle; the direct CPU path shares each transformed vertex across faces. Moving work to the GPU may increase its geometry work and presentation wait. These results are not a prediction of FPS improvement from removing 14.66 ms of CPU work.

Mario already uses GPU actor model/view transforms after CPU posing. The GPU does not currently accept a joint palette or per-vertex joint IDs. Moving skeletal pose evaluation requires a new reusable animation interface or verified rigid-part decomposition; replacing skinning with one matrix per current mesh would change the animation. Keep that as a later feature, after integer multiplication and validated resident terrain have been measured.

## Reproduction and evidence

```powershell
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --profile-detail
.\scripts\run.ps1 profile_cpu.py build/mario-castle-sdram-direct-profile-detail.package.json --symbols build/mario-castle-sdram-direct-profile-detail.symbols.json --restore build/cpu-profile/baseline/mario-castle-sdram-direct.package.json --out build/render-profile/detail-standing.json --trials 3 --reuse-immutable-assets
```

`--profile-detail` implies `--cpu-profile`. Add `--moving` for the diagnostic movement case. Reuse immutable assets only when the candidate asset bytes match the restore package and the game does not modify them. Profiling requires the counter-enabled image, SHA-256 `6744adf087bea5139d0170b69e4ca4c1461efe275036333c3f446e65b2c15888`. The archived experiment helper contains exact image hashes, programming commands, cases and a `finally` restoration path. Archived manifests describe asset hashes; asset binaries remain local and are not copied into the evidence archive.

Original restored FPGA SHA-256 is `b9386eb9aad671dff8313ca61a22b6e04874dc22ab1e94f42c2732790576b4ce`. Detail CPU SHA-256 is `e7f9b63dba6d46404f4e5b6f3fa14a07133ebb363608a1466d9b988fe65e70a3`.

Resume-safe wording: "Built reproducible, atomic function profiles on an RV32I FPGA game SoC; measured terrain transforms/outcodes at 14.66 ms, clipping at 5.95 ms and skeletal pose evaluation at 5.39 ms in a fixed castle view, prioritizing integer arithmetic and validated GPU offload from physical measurements."
