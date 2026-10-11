# ARCH-UPGRADE-001 Stage 3: setup/raster overlap

Status: baseline recorded; implementation and acceptance pending.

Source baseline: f8b9c45. Accepted board image: Stage 2A packed, SHA256
917ed067296ef2405c7d4706dea4224da261add9a9a481ff1e5c4b45d94c9a32.
Normal firmware SHA256: 4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda.
Immutable castle assets SHA256: afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6.

Experiment: retain existing arithmetic, split setup from raster traversal, and
place two stable ordered records between them. Preserve strict depth comparison,
per-triangle depth drain, command order, clear and swap barriers. Test both
serial and overlapped modes with identical packed firmware and clocks. Keep the
rejected command DMA disabled in both physical variants. No improvement is
claimed before measurement. Queue depth two is an experiment, not an optimum.

Internal record contract v1: viewport bounds (10-bit X, 9-bit Y), three signed
22-bit initial edges and six steps, signed 32-bit depth gradients, signed 36-bit
depth start, vertex depth extrema, color, winding sign, and skip flag. Each
accepted triangle yields exactly one ordered record, including empty/degenerate
triangles. Only one frame can own the pipeline at a time; frame metadata stays
in the existing command processor, and END_FRAME waits for the entire pipeline.

Physical framebuffer, actors and full-level route acceptance remain outside the
existing terrain replay coverage. Report synthetic overlap gains separately
from ordinary game CPU timings, GPU spans and frame cadence.
