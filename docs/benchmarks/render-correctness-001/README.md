# RENDER-001 evidence

See ../../render-correctness-fixes.md for diagnosis, measurements and limitations.
The measurement runner snapshot must be copied to build/render-fixes/measure.py
in the repository checkout before executing: its parent-relative imports and
rollback paths deliberately refer to the repo and preserved local asset package.
Restore the exact local baseline package before repeating; CPU binaries alone
are insufficient because asset binaries are intentionally omitted here.

Physical trial JSON contains raw timestamps, input packets, atomic snapshots,
package hashes and automatic restore status. Measurements are summary statistics
computed from those files. selected-running-check.json establishes full-readback
release and frame progress on the selected package. No experimental hardware
was deployed. Source snapshots are reference copies, not independent projects.

Replay ZIPs contain full commands/framebuffer captures and test logs. The old
appearance replay uses the current canonical CPU clipper with old asset policy;
it is not a byte-exact replay of the old firmware. replay-final uses accepted,
regenerated RTL. Native integration tests cover actor pose/state separately.
The floating oracle is diagnostic only. The unsuccessful hardware experiments
and raw 12-bit fit reports are retained under experiments/.
