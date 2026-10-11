# Stage 2A acceptance

Accepted as an optional packed transport, selected in normal Mario on the FPGA; legacy remains the global build default. DMA is deferred.

- Baseline source: 460957e; implementation: 2f226d6.
- Full terrain/static/fixture color-depth-palette and triangle equality: PASS. Actors, source-game transitions, physical framebuffer and full-level traversal remain out of scope.
- Firmware serialization/CRC/tails, atomic FIFO/backpressure/reset, existing MMIO/memory/loader/MUL, capability gates, specialized ISA audits: PASS.
- Final Quartus fit/assembly and all reported timing slacks: PASS. No increased clock or measured Fmax claim.
- Three trials each: legacy/batched/packed detailed, legacy/batched/packed fine, legacy/packed ordinary; three additional packed moving diagnostics. Raw scope and every observation are retained.
- Ordinary standing CPU update+render median improves 0.864%; FPS stays approximately 30. Larger detailed-profile gains include profiling overhead.
- Final normal packed CPU image readback and frame progress: PASS. Immutable asset reuse is explicitly recorded after preceding full readback.
- Initial syntax failure and status-preflight rejection retained; no unsupported MMIO loader access was enabled. First fitted/programmed image is distinct from the final status-capable image.
- Rollback SOF/package remain local with SHA-256 identities in manifest.json. Do not upload an archived package without its locally extracted matching assets.
