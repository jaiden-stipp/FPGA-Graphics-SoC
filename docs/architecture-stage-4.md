# ARCH-UPGRADE-001 Stage 4: two adjacent pixel lanes

## Baseline and acceptance contract

Accepted source baseline: `0a6434b` (Stage 3 setup/raster overlap).
Accepted image: `build/quartus-arch-stage3-overlap/ArchStage3SoC.sof`.
SHA256: `eb28b7007c48fc799ec729655d83a823112ea15c73a06cac665c32e9f1037f62`.
Normal packed Mario package: `build/mario-castle-sdram-direct-packed-mul.package.json`.
CPU binary SHA256: `4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda`.
Assets SHA256: `afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`.

This baseline is recorded before Stage 4 hardware edits. Keep clocks, game logic,
assets, command ABI and the rejected command DMA path unchanged. Stage 4 is
optional until correctness, fitting, timing and physical trials pass.

The candidate rasterizes adjacent even/odd X pixels in the same ordered triangle.
Each lane has its own depth test and parity bank. Bank address is
`y * (FRAME_WIDTH/2) + (x >> 1)`; odd bounds mask the unused lane. Vertex-extrema
depth clamping and strict greater-than depth testing remain unchanged.
Depth reads explicitly forward a simultaneous same-address write. Triangle drain
precedes the next ordered triangle. Clear owns both banks exclusively and clears
them together. VGA registers read parity alongside read validity, preserving the
existing framebuffer/palette display latency.

Pixel counters must count pixels (0..2 per cycle), while activity counters count
cycles. Banking changes clear duration as well as raster duration; report both
separately. Compare exact color/depth/palette results and submitted triangle order.
Check odd bounds, equal depths, winding, shared edges, reset, clear, bank parity,
read/write bypass, asynchronous display clocks and page swap before promotion.

Measurements and selection: pending. No Stage 4 speedup or FPGA acceptance is
claimed by this baseline document.
