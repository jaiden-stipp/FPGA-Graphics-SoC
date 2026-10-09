# Memory map and register ABI v1

| Address range | Owner | Behavior |
| --- | --- | --- |
| `0x00000000..0x0000ffff` | Unified 64 KiB CPU RAM | Code, constants, data, stack; RV32I subword operations |
| `0x40000000..0x400000ff` | Graphics MMIO | Aligned 32-bit accesses only |
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
