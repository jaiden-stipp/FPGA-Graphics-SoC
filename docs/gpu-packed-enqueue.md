# GPU-PACKED-001: atomic command-byte enqueue

Stage 2A of ARCH-UPGRADE-001. Protocol framing, decoder, CRC and GPU command meanings are unchanged. This is an optional MMIO transport capability shared by game ports through `gfx.c`; it does not change models, collision, camera, gameplay or the simulation timestep.

## Register contract

First check existing `SOC_CPU_FEATURES` (`0x4000009c`) bit 31 for GPU-register presence. Then `SOC_GPU_FEATURES` (`0x400000a8`) bit 1 advertises `packed-enqueue-v1`. Bit 0 remains fractional mesh support. Neither the presence bit nor fractional support alone authorizes packed writes. The existing SoC ID, MUL bit and legacy `GFX_DATA` contract remain unchanged.

| Word-write address | Bytes appended | Byte order |
| --- | --- | --- |
| `0x40000000` | 1, legacy | `wdata[7:0]`; ignore upper bits |
| `0x400000b0` | 1 | `wdata[7:0]` |
| `0x400000b4` | 2 | `[7:0]`, `[15:8]` |
| `0x400000b8` | 3 | `[7:0]`, `[15:8]`, `[23:16]` |
| `0x400000bc` | 4 | `[7:0]`, `[15:8]`, `[23:16]`, `[31:24]` |

Packed registers are write-only and require aligned 32-bit accesses. Other sizes, unaligned accesses or reading a write-only register raise existing invalid-access error bit 3. No address/data side effects occur for rejected accesses.

Acceptance is atomic. A valid enqueue is accepted only when the **pre-transaction** free-byte count is at least the requested length. Otherwise no bytes are appended, `write_performed` is false, and existing FIFO-capacity error bit 0 is raised. A simultaneous consumer pop does not authorize an otherwise insufficient write. Status readiness continues to mean room for one legacy byte; packed producers must check `GFX_FREE` (`0x40000008`) against their own length.

## Hardware and ownership

The real 256-byte FIFO keeps its capacity, one-byte ready/valid output, ordering, reset and error semantics. Four banks each accept at most one byte per enqueue. Bank choice follows byte-address low bits; row/carry/wrap logic handles a four-byte transaction crossing the ring boundary. Small and non-multiple-of-four parameter configurations retain a separately tested generic implementation. There is no new stall/wait-state signal: `soc_memory.sv` already passes MMIO acceptance through and requires no change.

The CPU is the only producer. Firmware reserves the reported free capacity locally and subtracts each committed group; consumer pops can only increase actual free space. The reservation resets for each command. Loader restart/reset cancels queued content through the existing reset path; the firmware cannot retain a reservation across restart. DMA and a second producer would require a separate ownership/arbitration contract.

## Firmware and compatibility

`--packed-gfx` defines `GFX_PACKED`, checks capability before emitting a command, accumulates up to four bytes in a word, and flushes the exact one-, two- or three-byte tail. It bounds readiness polling and checks errors at reservation refresh and command completion. The high CRC byte still precedes the low CRC byte in the byte stream. CRC is still calculated for every header/payload byte; packed enqueue does not eliminate that work.

Packed packages declare `required_gpu_features.packed-enqueue-v1`. Normal loading and profiling reject incompatible hardware **before BEGIN holds the CPU**, using advertised CPU/GPU feature words in the existing loader STATUS reply. The last two formerly reserved status words now carry CPU_FEATURES and GPU_FEATURES; older images report zero and are rejected without reading MMIO or restarting the game. Firmware has an additional guard. Legacy and batched packages remain selectable; `--packed-gfx` and `--batch-gfx` are mutually exclusive comparison modes. Fractional terrain drawing is independent and remains optional.

## Evidence and limits

Reference source commit: `460957e`; original MMIO and firmware sources are preserved in `docs/benchmarks/arch-upgrade-001-stage-2a`. FIFO tests cover six depths, all tail lengths, wrapping, rejected transactions, simultaneous pops, invalid sizes and reset. Native tests compile actual `gfx.c` in three modes and independently check bytes/CRC and store counts for every payload length 0..255. A maximum 255-byte payload makes a 262-byte command: the packed firmware must safely refill its reservation across the 256-byte FIFO capacity.

Full GPU replay routes inject packed writes through the actual MMIO FIFO and compare complete terrain color/depth, palette and ordered submitted triangles with preserved byte-stream references. These remain scoped terrain/static-scene tests, not full source-game engine acceptance. Synthetic replay timing is not physical CPU performance.

Fine profiling times CRC, checks and writes separately. Packed word assembly, function/loop work and instrumentation overhead remain outside or between these nested scopes; the scopes cannot be added to infer total frame time. Existing CPU `status_reads` count reads of `GFX_STATUS`, not packed `GFX_FREE` reads, so zero status reads does not imply zero readiness checks. Use fine invocation counts and coarse command/render spans together.

Physical measurements, fitted resources, timing, deployment decision and Stage 2B reassessment are recorded in `architecture-stage-2a.md` after testing. There is no assumed fourfold game speedup: packing affects transport writes, not CRC, transforms, animation or rasterization.
