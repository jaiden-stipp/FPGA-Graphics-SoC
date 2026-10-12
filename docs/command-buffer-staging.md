# Stage 2B buffer staging measurement

Measured October 11, 2026 on unchanged Stage 2A hardware. Preserved reference: 8488ff0; measurement commit: df9c539. The normal packed Mario image was restored after the probe. Original assets/models/collision/gameplay were untouched.

Three physical trials replay the saved seven-view castle command trace. The probe compares actual packed gfx.c submission against continuous CPU-RAM and SDRAM word staging with the same actual CRC routine and source bytes. Each staged result is independently verified byte for byte outside the timer. Destination 0x87ff0000 is reserved for the probe, checked against assets, and differs from the eventual DMA buffers. Prefix/setup and GPU drain are outside the timed replay. Source input lives in CPU RAM to isolate destination costs. Firmware is audited pure RV32I, with no optional per-scope profiling.

At 50 MHz, median elapsed CPU cycles:

| View | Bytes | Packed submit | RAM staging | SDRAM staging | SDRAM freezes | Staging reduction vs packed |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 6,050 | 267,233 | 177,007 | 193,692 | 16,685 | 27.52% |
| 2 | 8,208 | 338,447 | 240,122 | 262,749 | 22,627 | 22.37% |
| 3 | 8,208 | 338,447 | 240,122 | 262,753 | 22,631 | 22.37% |
| 4 | 9,248 | 372,767 | 270,542 | 296,044 | 25,502 | 20.58% |
| 5 | 4,776 | 225,191 | 139,736 | 152,904 | 13,168 | 32.10% |
| 6 | 4,256 | 208,031 | 124,526 | 136,259 | 11,733 | 34.50% |
| 7 | 278 | 9,313 | 8,176 | 8,950 | 774 | 3.90% |

The 6,050-byte view takes 5.34466 ms for packed submission and 3.87384 ms for SDRAM staging. The six larger streams use 20.6–34.5% fewer CPU cycles for staging; the 278-byte stream saves just 363 cycles. SDRAM write-through costs are visible in the freeze counter and vary with controller refresh. All three trials pass exact staged-byte/hash checks. Native tests independently cover all payload lengths 0..255 and randomized multi-command concatenations, including exact tails and no inter-command padding.

## Decision and limits

These results justify an experimental read-only command DMA master, with small double buffers to retain CPU/GPU overlap. They **do not measure game speedup**. Packed submission can encounter FIFO/GPU backpressure; staging excludes DMA reads, arbitration, byte publication, ownership checks and GPU drain. A whole-frame staging scheme could delay GPU work and regress performance. The actual game must be compared with packed submission on the same fitted candidate hardware before promotion.

The initial Stage 2B buffers are two 1 KiB regions at 0x87fe0000/0x87fe0400, chosen for the experiment rather than from an optimum-size claim. See [DMA ABI and ownership](gpu-command-dma.md) and [Stage 2B results](architecture-stage-2b.md).

## Reproduce / inspect

```powershell
.\scripts\run.ps1 test_gfx_staging.py
.\scripts\run.ps1 measure_gfx_staging.py --help
```

The measurement command's help describes input/restore arguments. The preserved compiled probe, all physical trials, source snapshots, exact wire trace, independent validation summary and SHA-256 manifest are in [raw staging evidence](benchmarks/arch-upgrade-001-stage-2b-staging/manifest.json). CPU counter snapshots have their fixed boundary overhead; median elapsed replay timer and freeze/store counters must not be represented as an end-to-end frame benchmark.
