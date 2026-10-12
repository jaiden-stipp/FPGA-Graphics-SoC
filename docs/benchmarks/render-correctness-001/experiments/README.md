# Unselected depth experiments

These source snapshots were tested before the transparent-decal root cause was
identified. They are archived experiments, not part of the accepted generator.
12-bit depth and Q4 depth-plane setup rearranged artifacts and did not solve
the opaque tree-shadow problem. No experimental SOF was programmed and no
physical FPS was measured for either experiment. The 12-bit fit reports are
actual Quartus results; the Q4 variant was not fitted.

For reconstruction, use baseline Stage 6 source plus these matching archived
scripts/soc.py, generators and testbench snapshots. Restore them in an isolated
checkout; do not copy over the accepted tree for normal builds. Refer to the
saved QSF/logs and hashes. The float oracle uses integer-projected triangles
without exact hardware rounding/alpha semantics and is diagnostic only; its
pixel disagreements are not original-game accuracy scores.
