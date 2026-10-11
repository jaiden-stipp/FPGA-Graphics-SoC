# Command DMA v1 (experimental Stage 2B)

Optional shared graphics transport; no change to GPU command framing, CRC, model data, game logic, renderer arithmetic, clocks or CPU ISA. GPU_FEATURES bit 2 advertises support; CPU_FEATURES bit 31 must advertise the capability register. Loader STATUS returns these features before BEGIN. Unsupported targets keep features 3 and legacy/packed transport.

## Descriptor and ownership

MMIO addresses below are offsets from 0x40000000, aligned 32-bit accesses only:

| Offset | Access | Meaning |
| --- | --- | --- |
| c0 | R | ABI 0x444d0101 |
| c4 | RW | Source byte address, 32-byte aligned SDRAM |
| c8 | RW | Exact byte length 1..65536 |
| cc | RW | Submission ID |
| d0 | W | Write exactly 1 to start when idle |
| d4 | R | Bit 0 busy; bit 1 error; bits 15:8 error code |
| d8 | R | Last completely FIFO-accepted submission ID |
| dc | R | Reserved zero |
| e0 | R | Cumulative bytes accepted by FIFO |
| e4 | R | Cumulative SDRAM response words |
| e8 | R | Cumulative request-valid cycles without grant |
| ec | R | Cumulative byte-valid cycles without FIFO acceptance |

The engine latches source, length and ID at start. Source is at least 0x80000000; source plus length rounded up to 32 bytes must not exceed 0x87fff000. Overflow-safe 33-bit validation rejects malformed descriptors with DMA error 1 and no reads. Invalid/busy start writes produce sticky MMIO error bit 3. CPU enqueue while busy produces sticky MMIO capacity/ownership error bit 0 and appends nothing. A valid START clears the prior DMA descriptor error. Loader cancellation can retain the last error/ID, so firmware associates them only with its active descriptor. Configuration writes during a transfer do not change its latched descriptor. Completion means the last byte entered the FIFO, **not** that commands finished rendering or the VGA page swapped. Existing frame ID/ack semantics remain mandatory.

A read-only master bypasses the CPU cache and requests one eight-word SDRAM burst. It collects all eight responses into a 32-byte line and streams exact low-byte-first data into the existing command FIFO, respecting backpressure. It does not append rounded tail bytes. CPU stores use the existing acknowledged write-through path; publishing after the last staging store gives DMA committed SDRAM data. No dirty write-back data or speculative prefetch is involved.

The arbiter keeps each accepted transaction until all expected response beats arrive. It routes responses only to the owning CPU or DMA requester and alternates contested grants after whole transactions. CPU can be delayed by an already accepted burst; controller refresh still applies. The engine is supported only with SDRAM, cached burst reads and 32-byte CPU cache lines in this version. Other configurations keep the DMA capability clear.

## Firmware buffers

`--dma-gfx` selects shared gfx.c continuous serialization into two 1024-byte buffers at 0x87fe0000 and 0x87fe0400. This size is an experimental starting point, not a measured optimum. Each full buffer is published; the CPU switches to the other buffer while DMA owns the submitted buffer. Before submitting again the driver waits for prior completion, so that buffer is safe to reuse. Commands may span buffers; CRC and payload bytes stay unchanged. The final driver holds command-building state locally and persists it at command/buffer boundaries; the first global-state driver is retained as a measured unsuccessful candidate. END_FRAME publishes the exact tail, and gfx_wait_frame waits for transfer acceptance and normal GPU frame completion. Bounded error/status loops return failure rather than silently dropping bytes.

Packages declare command-dma-v1 and the 2048-byte reservation. The loader verifies capabilities and rejects overlapping assets before BEGIN. Existing packages remain usable on the candidate image. Loader hold or CPU reset cancels byte publication, clears the FIFO/decoder through the existing reset path, and drains an accepted memory burst before arbitration can service loader requests. Board SDRAM reset resets both engine and arbiter. There is no descriptor queue or DMA write master.

## Profiling interpretation

The existing command cycle span includes serialization and publication. In DMA builds, the historical fifo_wait_span_cycles field measures buffer ownership checks/waits, including check overhead; it is not solely FIFO-full latency. The final transfer can overlap presentation. Optional profile snapshots publish exact frame bytes/read words/request-grant waits/FIFO-publication waits with the frame ID. These spans overlap CPU/GPU work and must not be summed into serial frame time. Primary performance acceptance uses normal uninstrumented update-plus-render timers, with their existing live/non-atomic limitations.

## Reproduction

```powershell
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --integer-mul --dma-gfx
# Add --profile-detail for atomic phase and DMA diagnostics.
.\scripts\run.ps1 soc.py sim --tests gfx_dma_tb,sdram_arbiter_tb,gfx_dma_memory_tb,soc_mmio_tb,packed_mmio_tb,sdram_memory_tb,udp_loader_tb
.\scripts\run.ps1 test_dma_gfx.py
.\scripts\run.ps1 replay_render_route.py --out build/arch-stage2b/castle-dma --capture-only --dma --simulate
```

The last command needs the preserved input files in that directory. Full replays share build/render-replay and run serially. See architecture-stage-2b.md for the measured acceptance decision and exact artifact hashes.
