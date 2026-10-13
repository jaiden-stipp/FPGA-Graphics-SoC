# SM64 engine slice evidence

Read `../../sm64-original-engine-slice.md` for implementation scope and interpretation.

- `physical-diagnostic-measured.json`: corrected physical replay; valid CPU counter deltas, 96 updates, native comparison, and restoration status.
- `physical-initial-state-only.json`: initial run retained unchanged. State comparison is useful, but zero CPU deltas are invalid because the diagnostic omitted snapshot triggers.
- `physical-rendered-memory.json`: separate live rendered sample and stack/state inspection. Input is uncontrolled; frame progression does not establish sustained gameplay FPS.
- `summary.json`: statistics calculated from the corrected trace, links to record names, measurement errata, and regression count. It makes no speedup claim.
- `packages/`: exact experimental diagnostic and rendered binary segments, ELF/maps, package manifests, and final ISA audits tested on the board.
- `baseline/`: the exact prior castle package restored to the board after the experiment.
- `source/`, `generated/`, and `provenance/`: authored source snapshot, generated inputs, upstream lock files, input hashes, license, hardware identity, and compiler version.
- `regressions/`: 24 suites, 197 tests, all passing. The native replay and its individual test log are also preserved separately.
- `SHA256SUMS.json`: hashes of every other file in this evidence folder. These establish file identity, not independent certification of the measurement method.

The raw first two passes call some frame samples “idle.” Neutral input was not enforced. That label is superseded by the report's explicit correction; the records are preserved rather than rewritten.
