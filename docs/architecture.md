# Integration architecture

For future parallel hardware work, follow [ARCH-UPGRADE-001: concrete architecture upgrade plan](architecture-upgrade-plan.md). It defines staged interfaces, acceptance gates, benchmark requirements and the execution ledger.

## Why this boundary

At the pinned RV32I revision, `RV32I_Pipeline.sv` directly instantiates
`UnifiedMem`. It has no request/ready bus, instruction-cache interface, interrupt
input, or general external-memory stall. Simply replacing the RAM with a slow
bus would let instructions retire with stale load data and lose blocked stores.

The scaffold externalizes that memory instance into `RV32I_SoC`, preserving the
pipeline, forwarding, load-use stalls, branch flushing, and trace outputs. MEM
read/write requests are additionally gated with `valid_MEM` and reset. The
generated adapter exports the fetch PC/instruction and the MEM address, write
data, width, read result, misalignment and write-performed signals. It has zero
wait states for on-chip RAM/MMIO; requests occupy one MEM cycle and commit once
on its falling edge. The optional SDRAM boundary adds a full pipeline clock
enable and completion handshake; see [sdram.md](sdram.md). Pinned upstream
sources remain unchanged.

The SoC adapter now adds integer `MUL` only: the generated `soc_ControlUnit`
decodes the full funct7 and selects `soc_ALU` control 0xB for the low 32-bit
product. It uses the existing EX/MEM, forwarding and writeback paths without a
new stall. MMIO 0x4000009C feature bit 0 advertises support. Portable builds
opt in with `--integer-mul`, retain the RV32I compiler target, audit emitted
M-family opcodes and reject incompatible hardware before using multiplication.
MULH and division are not implemented; this is not full RV32M or Zmmul.
See [implementation and physical results](integer-mul.md).

The original RAM is separately generated as `soc_ram`, retaining its byte/halfword
sign extension and falling-edge Intel `altsyncram` implementation. Simulation adds
zero initialization and `$readmemh`; its array write process uses `always` because
the initialization process also writes the array. The generator verifies exact
text anchors and fails if an upstream interface changes.

The RAM adapter selects the native memory branch with Quartus's built-in
`ALTERA_RESERVED_QIS` macro. Quartus 18.1 does not define `SYNTHESIS` automatically;
using that original upstream guard would synthesize the behavioral model and
hit the 16,384-entry initialization loop instead of creating block RAM.

The generated palette IP also adjusts its initialization-file path from the
renderer repository root to `external/renderer/rtl/memory/palette_default.mif`.
This preserves the default palette in simulation and synthesis without copying
or modifying the dependency tree.

Generated renderer wrappers add a separate `reference_clk` connection down to
the VGA PLL. The PLL receives the direct board clock; command processing and
rasterization retain the CPU's inverted clock. An inverter before an Intel PLL
reference input is illegal, even though the same phase arrangement works in
behavioral simulation. These generated changes leave upstream checkouts clean.

## Command transport

`soc_memory` selects RAM below 64 KiB and optional SDRAM at
`0x80000000..0x87ffffff`. Other data requests go to `soc_mmio`,
which validates the graphics region and access width. CPU data memory is
little-endian. The graphics peripheral transports one low byte per word store,
so the existing big-endian, versioned renderer command frames remain unchanged.

The FIFO presents stable data/valid during decoder backpressure and advances
only on valid/ready. A full write is rejected, even if a pop occurs on that same
edge, and sets overflow. After reading TX_READY, space cannot shrink before the
single CPU's next write unless that CPU submits another byte. This makes polling
safe for one producer without adding a CPU stall signal. Multiple independent
producers require arbitration/reservation or a different bus contract.

Use `graphics_stream_renderer` directly. It already composes the binary decoder
and `graphics_renderer_core`; the built-in scene, original board tops, and
command source mux are unnecessary for this path. All upstream
opcodes, bulk upload commands, CRC checks, mesh handles, Q8.8 transforms, depth
testing and vertical-blank swaps remain available to firmware.

The board now instantiates the upstream `ethernet_command_receiver` separately
inside `udp_controls`, reusing MII UDP reception, GP/GF framing/CRC, asynchronous
FIFOs and ARP/status transmission. Reserved input envelopes update held key
state, not the graphics stream. The CPU remains the only GPU command producer.
Fresh input sequences refresh a 300 ms release timer. Local buttons are ORed
with remote bits before the MMIO synchronizer. See [sm64-subset.md](sm64-subset.md).

## Clock/reset contract

The CPU is on `clk`; RAM accesses occur on its falling edge. MMIO, FIFO and
renderer receive `~clk`, so the FIFO and decoder run together without an
asynchronous crossing. MEM addresses settle from a rising edge to the falling
edge; RAM/read-register values settle for the next rising edge. TimeQuest must
time both half-cycle directions at the chosen frequency. The renderer's existing
PLL and video synchronization continue to handle its VGA pixel-clock domain.

The board wrapper asynchronously asserts reset from active-low KEY[0] and
synchronously releases it after two CPU clock edges. Reset drops pending bytes,
completion, errors and scratch; it resets CPU and renderer together. RAM contents
are initialized at simulation startup / FPGA configuration and are not restored
by KEY[0]. The firmware explicitly clears BSS on each boot. A renderer-only reset
is deliberately absent: recovering from a partial stream requires a whole-SoC
reset in this version.

Active-high left/right input bits enter a two-register synchronizer in the
peripheral clock domain. MMIO exposes the held states and a free-running 32-bit
cycle timer. The board maps active-low KEY[1] and KEY3 to left/right; pin assignments
come from the pinned renderer and CPU board projects. The game samples inputs at
each paced update and uses unsigned elapsed-time arithmetic across timer wrap.
The expanded eight-bit input register also carries zoom and reset-view bits.
Ethernet RX and TX use their independent 25 MHz PHY clocks; the asynchronous
FIFOs carry network data into the CPU domain. SDC times MII input/output delays
and groups PHY clocks asynchronously with CPU and VGA clocks.

## Completion and diagnostics

Hardware frame completion latches the last frame ID, all 13 upstream counters,
and a pending bit. Firmware acknowledges pending with a write of bit 0 to ACK.
A new hardware event wins over a same-edge acknowledgement. Error bits are
sticky and W1C; a new error wins over same-edge clearing. Counter snapshots remain
stable until the next displayed frame. There is no software-visible busy bit
claiming the renderer is idle: FIFO empty only means all queued bytes were handed
to the decoder, not that a frame finished rendering.

Frame IDs should be unique across outstanding work. The game keeps one frame
in flight and waits before submitting another. The pending register stores the most recent event,
not an event queue; submitting many frames without servicing it loses history.

## Resource planning

CPU RAM adds 524,288 memory bits plus the FIFO and CPU logic to the renderer's
existing color/Z/mesh memories. Both IPs target Cyclone IV E on the DE2-115. Actual
combined fit, memory packing, routing and half-cycle timing must be measured with
this top; upstream standalone build statistics do not prove combined timing.
