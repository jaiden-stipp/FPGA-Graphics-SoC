# Original grounds traversal evidence

Read `../../sm64-engine-grounds-traversal.md` for implementation scope, test limitations, controls, and reproduction commands.

- `traversal-physical.json` and its log: uploaded package identities, the native-matched 96-update FPGA diagnostic, four live route checks, reset result, and final frame progression.
- `packages/`: final physically tested game/diagnostic segments, manifests, ELF/maps, and ISA audits.
- `native-trace.json` and `regressions/`: deterministic native reference and all 24 suites/203 tests.
- `source/`, `generated/`, and `provenance/`: authored source snapshots, generated inputs/warp deadlines, original-source function hashes, upstream locks, and hardware identity.
- `baseline/`: the earlier movement-fix manifest. Its exact bytes remain in `../sm64-engine-movement-fix-001/packages/`.
- `summary.json`: statistics calculated from saved artifacts, including scope limitations.
- `SHA256SUMS.json`: file identities for every other file in this evidence folder.

No hardware or FPS improvement is claimed. Native-only initial-condition helpers are absent from the target ELF. An isolated climb-state fixture is distinguished from a real grounds route; no completed hardware ledge-climb or hanging route is asserted.
