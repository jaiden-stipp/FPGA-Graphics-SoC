# ARCH-UPGRADE-001 Stage 5: optional queued geometry worker

Accepted baseline: `e0d776c` (Stage 4), selected SOF SHA256
`52f7f8e3baf5d827a9dd18b3dc54f177aef666fce2ba361463830dfe8a0a8235`.
Preserve the Stage 4 image and normal packed Mario package as rollback.

## Selection from measurements

Stage 4 standing-frame detailed trials measure transform/outcode costs of
312,328 / 312,333 / 312,328 cycles, clipping at 231,073 each, and skinning at
35,547 / 35,550 / 35,547. These are instrumented scope costs, not predicted
savings. Choose the transform/outcode worker; do not add a skinning accelerator.
The ordinary Stage 4 CPU median is 905,274 update/render cycles at 50 MHz.

## Contract before hardware changes

An optional worker accepts the existing signed 16-bit local XYZ mesh format,
32-bit origin/reference position and signed 16-bit 3x4 Q8 view matrix. It returns
three signed 32-bit camera coordinates and the six existing frustum bits in
submission order. Preserve low-32-bit MUL/sum semantics, arithmetic right shift
by eight, translations, near 257/far 30000 and the existing screen planes.
Clipping intersections and their 16-bit fraction stay in the CPU unchanged.

The worker uses a separate versioned MMIO page at 0x40000100, bounded four-entry
input/result queues, and descriptors of 1..128 vertices (the current mesh bound).
These queue sizes are design choices, not measured optimum sizes. The CPU streams
cached source vertices and copies returned coordinates/outcodes into its existing
render scratch buffer. The worker has no SDRAM access and no cache-coherency role.
Active descriptors exclusively own configuration; results remain stable under
CPU backpressure. Reset/abort discard all queued work. Completion/credit checks
must prevent stale results, overwrite, partial output and descriptor overflow.

Feature-gated firmware retains the CPU kernel on old hardware. The worker is
independently selectable; Stage 4 raster/transport/clocks/game logic/models remain
unchanged. Physical comparisons must include matrix setup, streaming, polling
and returned-result copies, plus ordinary game time. Do not promote the worker
based on standalone multiply throughput.

Acceptance requires independent arithmetic fixtures, FIFO/reset/config ownership
tests, exact ordered game-stream/frame equivalence, full fit/timing/constraint
checks, package capability gates and at least three matched physical trials.
Archive raw measurements and hashes; restore Stage 4 after experiments. No Stage
5 performance improvement or deployment is claimed yet.
