# Memory map and register ABI v1

| Address range | Owner | Behavior |
| --- | --- | --- |
| `0x00000000..0x0000ffff` | Unified 64 KiB CPU RAM | Code, constants, data, stack; RV32I subword operations |
| `0x40000000..0x400000ff` | Graphics, CPU counters and optional DMA MMIO | Aligned 32-bit accesses only |
| `0x40000100..0x400001ff` | Optional geometry-worker MMIO | Present only when CPU feature bit 1 is set |
| `0x80000000..0x87ffffff` | Optional 128 MiB SDRAM | RV32I data loads/stores with pipeline wait states; volatile assets and data |
| Other data addresses | Unmapped | Reads zero, writes rejected, BAD_ACCESS sticky |

Instruction fetch can only address CPU RAM; out-of-range fetch returns RV32I NOP
(`0x00000013`). Misaligned RAM data accesses are suppressed by the upstream RAM.
RAM contents persist across reset. MMIO bytes/halfwords and misaligned accesses
are rejected; misaligned accesses also drive the CPU's misalignment indication.
The CPU has no precise exception/trap delivery for these conditions.

SDRAM is enabled by the `sdram-game` board build. Its final 4 KiB is reserved
for memory testing, and `.game_assets` must end below `0x87fff000`.
The UDP loader can replace local code and external assets while CPU/GPU reset
is held. SDRAM initialization/refresh continue during loading. See
[sdram.md](sdram.md) for package commands, reset behavior and the loader ABI.

All offsets below are relative to `0x40000000`.

| Offset | Name | Access | Meaning |
| --- | --- | --- | --- |
| `0x00` | DATA | W | Enqueue `wdata[7:0]`; poll TX_READY first |
| `0x04` | STATUS | R | Bit 0 TX_READY; 1 FIFO_EMPTY; 2 FRAME_PENDING; 3 ANY_ERROR |
| `0x08` | FIFO_FREE | R | Free byte slots (0..256) |
| `0x0c` | FRAME_ID | R | Last displayed frame ID |
| `0x10` | ACK | W | Bit 0 clears FRAME_PENDING; other bits ignored |
| `0x14` | ERRORS | R/W1C | Bit 0 FIFO_OVERFLOW; 1 DECODER_ERROR; 2 COMMAND_ERROR; 3 BAD_ACCESS |
| `0x18` | SCRATCH | R/W | Firmware/test mailbox; reset value 0 |
| `0x1c` | SOC_ID | R | `0x534f4301` (SoC ABI 1) |
| `0x20` | TRIANGLES_SUBMITTED | R | Displayed-frame snapshot |
| `0x24` | TRIANGLES_CLIPPED | R | Displayed-frame snapshot |
| `0x28` | TRIANGLES_CULLED | R | Displayed-frame snapshot |
| `0x2c` | BOUNDING_BOX_PIXELS | R | Displayed-frame snapshot |
| `0x30` | PIXELS_INSIDE | R | Displayed-frame snapshot |
| `0x34` | DEPTH_REJECTED | R | Displayed-frame snapshot |
| `0x38` | PIXELS_WRITTEN | R | Displayed-frame snapshot |
| `0x3c` | GEOMETRY_CYCLES | R | Displayed-frame snapshot |
| `0x40` | GEOMETRY_STALL_CYCLES | R | Displayed-frame snapshot |
| `0x44` | RASTER_CYCLES | R | Displayed-frame snapshot |
| `0x48` | CLEAR_CYCLES | R | Displayed-frame snapshot |
| `0x4c` | TOTAL_CYCLES | R | Displayed-frame snapshot |
| `0x50` | SWAP_WAIT_CYCLES | R | Displayed-frame snapshot |
| `0x54` | BUTTONS | R | Bits 0..4: left, right, forward/zoom-in, back/zoom-out, reset-view; active-high, synchronized |
| `0x58` | CYCLES | R | Free-running 32-bit clock counter, reset to zero |
| `0x5c` | CLOCK_HZ | R | Peripheral/CPU clock frequency; default 50,000,000 |
| `0x64` | INPUT_ABI | R | `0x494e0101` |
| `0x68` | CACHE_ABI | R | `0x43410101` when enabled; otherwise zero |
| `0x6c` | CACHE_READ_HITS | R | Live cached CPU read hits |
| `0x70` | CACHE_READ_MISSES | R | Live cached CPU read misses |
| `0x74` | CACHE_FILL_WORDS | R | Live returned line-fill words, including discarded fills |
| `0x78` | CACHE_WRITE_REQUESTS | R | Live stores, including loader bypass stores |
| `0x7c` | CACHE_BUSY_CYCLES | R | Live non-IDLE cache cycles, including loader work |

Cache counters reset on SDRAM reset, wrap at 32 bits and are not atomically
snapshotted. See [cache architecture and counter definitions](sdram-cache.md).

Reserved offsets, reads of write-only registers, and writes of read-only registers
set BAD_ACCESS. A full-FIFO DATA store does not enqueue and sets FIFO_OVERFLOW.
Writes to ERRORS clear only the supplied 1 bits. New hardware events win over
simultaneous software acknowledgement or clearing. Hardware errors remain latched
until explicitly cleared or reset; clearing does not repair a broken command
stream, and firmware should reset after a failed submission.

## Sending a command

```c
while (!(GFX_STATUS & GFX_TX_READY)) { /* also check GFX_ERRORS */ }
GFX_DATA = next_byte;
```

The firmware driver repeats this for each byte and includes bounded polling and
error checks. The renderer frame is:

```text
47 46 | command version | opcode | payload length | payload | CRC high | CRC low
```

CRC-16/CCITT-FALSE covers all preceding frame bytes, starting at `0xffff`, with
polynomial `0x1021`. Payload multibyte values are big-endian. This register ABI
version and the upstream graphics protocol version are separate. Protocol macros
are generated from the pinned upstream JSON rather than duplicated by hand.

The FIFO has one writer. Frame completion requires FRAME_PENDING and a matching
FRAME_ID; FIFO_EMPTY cannot substitute for completion. Acknowledge a displayed
frame before submitting another with a reused ID.

Use unsigned subtraction `(uint32_t)(SOC_CYCLES - previous)` to measure intervals
across timer rollover. The 50 MHz counter wraps about every 85.9 seconds. Buttons
have two synchronization registers; the game samples held states once per tick
rather than counting raw mechanical edges. Simultaneously held left/right is
neutral in the sample game.

The board ORs local KEY[1]/KEY3 with UDP key state before synchronization. The
remote state is released after 300 ms without a fresh control envelope; see
[sm64-subset.md](sm64-subset.md) for its wire format and Windows sender.


## CPU counters, feature discovery and packed writes

| Offset | Register | Behavior |
|---|---|---|
| 0x80 | CPU_ABI | 0x43500101 |
| 0x84 / 0x88 | CPU_CYCLES / RETIRED | Counter snapshot |
| 0x8c / 0x90 / 0x94 | MEMORY_FREEZES / DEPENDENCY_BUBBLES / REDIRECTS | Counter snapshot |
| 0x98 | CPU_SNAPSHOT | Write captures CPU counters and GPU polling counts atomically |
| 0x9c | CPU_FEATURES | Bit 0 MUL, bit 1 geometry worker, bit 31 GPU feature registers present |
| 0xa0 / 0xa4 | GPU_STATUS_READS / GPU_FULL_READS | Same CPU snapshot |
| 0xa8 | GPU_FEATURES | Bit 0 fractional mesh transform, bit 1 packed enqueue, bit 2 command DMA |
| 0xb0 / 0xb4 / 0xb8 / 0xbc | PACKED_DATA | Enqueue 1 / 2 / 3 / 4 bytes, earliest byte in low eight bits |

Packed writes require reservation of enough FIFO space; one pop does not
permit an otherwise full write. Probe GPU_FEATURES only after confirming
CPU_FEATURES bit 31. Probe geometry registers only after CPU_FEATURES bit 1.
Original RV32I includes no multiply, but the current owned CPU adapter adds
MUL only; it does not implement MULH/DIV or the complete M extension.

## Optional command DMA

Offsets 0xc0 ABI (0x444d0101), 0xc4 source, 0xc8 length, 0xcc submission ID,
0xd0 START, 0xd4 status, 0xd8 completed ID and 0xe0/0xe4/0xe8/0xec counters
are present only with GPU_FEATURES bit 2. Status bit 0 is busy, bit 1 is error,
and bits 15:8 hold the error code. A descriptor completes after FIFO acceptance;
frame completion still requires the ordinary presentation handshake. Current
selected Stage 5 hardware keeps DMA disabled. See [DMA contract](gpu-command-dma.md).

## Optional geometry worker

Geometry offsets are relative to 0x40000100: 0 ABI (0x47570101), 4 status,
8 received count, 0xc generated count, 0x10..0x3c matrix, 0x40..0x48 reference
position, 0x50..0x58 chunk origin, 0x60 vertex count and 0x64 control
(1 start, 2 abort). Inputs are written at 0x70 packed XY and 0x74 Z. Read
output XYZ at 0x80/0x84/0x88, then read 0x8c outcode to consume that result.
Status bit 0 is active, bit 1 error, bits 15:8 output count and bits 6:4
input slots free. 0x90/0x94 report active/stall cycles. The driver retains at
most four outstanding inputs and aborts on missing progress. Its default
5,000,000-cycle timeout is an authored 100 ms failure budget at 50 MHz,
not a measured geometry latency. See [worker architecture](architecture-stage-5.md).
