# Repository consistency audit — October 12, 2026

Audited commit: `6bfbce4` (render implementation `8f46e2c`). This is a review,
not a hardware/software deployment. Production RTL, firmware, models, packages
and the running FPGA were not changed. Untracked user programmer files
`Chain11.cdf`, `Chain12.cdf` and `Chain13.cdf` were inspected and left untouched.

## Scope and evidence

The inventory covers 2,412 tracked files: first-party RTL and generators, C
firmware and port interfaces, source adapters, profiles, schemas, package/input
loaders, simulation/native tests, build/measurement tools, CI, documentation
and archived benchmark records. Pinned external dependency identities/cleanliness
were checked rather than auditing every line of their engines. Historical
snapshots were inspected as evidence, not treated as current implementations.

- All 20 native test scripts were run separately: 158 checks, 157 passes,
  one failure, zero skips. Failure: `test_gpu_fractional.py`.
- 13 baseline directed RTL fixtures and three worker/counter fixtures pass.
  The initial worker-enabled MMIO fixture fails its hardcoded baseline feature
  expectation; this is recorded separately from RTL functional failures.
- 1,599 archived raw-evidence hash entries were checked: zero mismatches or
  unresolved paths. No broken local links in existing first-party Markdown.
- Every tracked Python file parses. One tracked `.json` is actually mixed
  loader stdout, and one first-party Markdown file is not UTF-8.
- CPU, renderer and SM64 clones are clean at their lock-file commits. The
  currently selected interpolated Castle package still passes its byte/hash
  validation. No loader/network operation, programming or Quartus refit was run.

A historical `geometry_game_tb` run was stopped; it uses fixed older package
names and is not counted as a completed current-package integration check.
Directed worker tests were completed separately. Generated local fixtures were
available for these tests; this is not a fresh-checkout acceptance claim.

[Raw summary](audits/2026-10-12/summary.json),
[test and inventory details](audits/2026-10-12/inventory-audit.json),
[contract reproductions](audits/2026-10-12/contract-reproductions.json),
[evidence hash checks](audits/2026-10-12/evidence-hashes.json).

## Findings, in recommended repair order

### AUD-01 — Package preflight permits invalid address types (P2)

Locations: `scripts/load_game.py:53`, `scripts/load_game.py:101`.
`package_segments` uses arithmetic/comparisons without requiring an integer
address. A valid hash-checked CPU segment at JSON address `0.0` passes preflight;
`packet(..., WRITE, 0.0, ...)` then raises `struct.error` because its address must
be an integer. `Loader.transfer` sends BEGIN before encoding the first WRITE,
so this can halt the running CPU and fail without releasing/restoring it.
The real transfer path was also called with a fake operations backend: it
issued BEGIN, then failed at the hexadecimal progress-message formatting of
that float, before any WRITE or COMMIT. No physical packet was sent.

Repair: validate complete manifest types, bounds and feature declarations before
any hold operation; define a transfer-failure state/recovery policy. Reject
booleans/floats where integer fields are required. Preserve readback-before-release.
[Reproduction](audits/2026-10-12/malformed-address-reproduction.json).

### AUD-02 — Accepted world coordinates exceed collision arithmetic bounds (P2)

Locations: `scripts/world_assets.py:14`, `firmware/src/player.c:86`,
`firmware/src/player.c:90`. The world compiler accepts coordinates in
[-16000,16000], but edge distance/length/dot sums use signed 32-bit arithmetic.
An edge from (-16000,-16000,-16000) to (16000,16000,16000) has squared length
3,072,000,000, exceeding INT32_MAX. Production `edge_hit` returns 0 for the
midpoint (0,0,0) with radius 60, although it is directly on the edge.

The complete generic world compiler also accepted a collision wall containing
that diagonal. This is a real valid-domain mismatch for future source imports. The current
castle's maximum squared source collision edge is 536,805,378, below that
threshold; this reproduction does not establish that the earlier Castle floor
problem was caused by this overflow.

Repair: make the full collision kernel safe over its advertised domain, or
reject unsupported edge/distance bounds explicitly at conversion until the
runtime supports them. Add independent long-diagonal/large-distance tests;
changing a mesh silently is not an acceptable fix.

### AUD-03 — World projection can disagree with CPU clipping (P2)

Locations: `scripts/world_assets.py:54`, `scripts/world_assets.py:191`,
`firmware/src/world.c:99`, `firmware/src/portable_main.c:29`.
The resident scene compiler accepts focal lengths 128..512 and near planes
257..1024. Multi-area world compilation inherits that configuration, but world
CPU visibility/clipping fixes focal=256 and near=257; metadata also reports
those fixed world values. Firmware configures the GPU from PORTABLE_FOCAL and
PORTABLE_NEAR_Z generated from the resident scene.

Reproduction: a world with resident focal=128 compiles successfully. Camera
point (900,0,1000) projects to screen x=275.2 and is visible at focal 128, but
its CPU right-plane value at focal 256 is -70,400, outside the CPU frustum.
Geometry can therefore be dropped before the wider GPU projection sees it.
The current Castle uses 256/257, so that specific package is consistent.

Repair: parameterize one shared frustum contract, or require exactly 256/257
for this world runtime and reject mismatches before emitting assets. Make replay
projection and package metadata use the same selected values.

### AUD-04 — Unknown hardware requirements are silently ignored (P2)

Location: `scripts/load_game.py:121`. CPU/GPU feature maps are tested only for
recognized keys. A requirement such as `packed-enqueue-v2: true` or a misspelled
`integer-multiply: true` succeeds against a fake board with zero features,
without making even a STATUS call. A typo/new extension can therefore bypass
what the project describes as a compatibility gate.

Repair: reject unknown requirement keys and non-boolean feature values; centralize
feature-bit definitions and validate the complete declaration before loading.
Do not interpret an unknown requirement as optional. Keep old-image preflight
from probing unsupported MMIO addresses.

### AUD-05 — Legacy firmware builds depend on prior asset generation (P2)

Location: `scripts/soc.py:295`. The Mario builder regenerates `game_data.h`
only when it does not exist. An existing header from `sm64-mario-sdram` contains
1,043 terrain faces; a later ordinary on-chip Mario build silently reuses it
instead of the intended on-chip profile. The audit reproduced a linker failure
using a unique `repo-audit-mario` stem: `.rodata` exceeded RAM by 52,406 bytes.
No established firmware output was overwritten.

Repair: generate from the explicitly selected profile every time, or cache by
profile/source/configuration hashes in per-project output directories. Include
an SDRAM-build then on-chip-build order regression. Scene headers use a similar
existence-based cache and should be handled consistently.
[Build failure](audits/2026-10-12/cached-mario-build.log).

### AUD-06 — Published schemas lag generated/runtime contracts (P2)

Location: `schemas/game-package-v1.schema.json:4`. The schema forbids additional
properties but does not define `required_cpu_features`, `required_gpu_features`,
`cadence` or `diagnostic`, all present in the current generated Castle manifest.
It therefore rejects a package that the compiler emits and loader accepts.
DMA packages also add `command_buffers`, which is absent from the schema.
The project schema omits typed render-repeat/interpolation declarations; no
published schema describes the supported `soc-world-ir` area/flag contract.

Repair: update schemas alongside runtime validators, share validation where
practical, and test every generated normal/diagnostic/optional-feature package
against the published schema. Add explicit world IR and interpolation fields.
The audit verified the additionalProperties contradiction directly from the
property sets; no external JSON Schema validator was installed or used.

### AUD-07 — Recent chunk metadata breaks a regression assertion (P2)

Location: `scripts/test_gpu_fractional.py:40`. The test compares entire current
chunk dictionaries with an archived pre-flag dictionary. Current chunks include
`render_flags: 0`; the archived format does not. The assertion fails even when
ordered geometry and room membership are unchanged. This was missed by the
last task's narrower test selection.

Repair: compare explicitly versioned semantic fields and independently assert
that legacy inputs default to flag zero. Keep preservation assertions meaningful;
do not weaken the test by dropping geometry/order checks.
[Actual failure](audits/2026-10-12/test_gpu_fractional.log).

### AUD-08 — Test reproducibility and CI coverage are incomplete (P2)

Locations: `scripts/test_render_fixes.py:48`, `scripts/test_world_pipeline.py:160`,
`.github/workflows/sim.yml:10`. Several tests need ignored generated files.
The new source-preservation tests specifically require
`build/render-fixes/baseline/world.json` and `build/castle-shaded/world.json`,
without building or locating reproducible baseline fixtures. A clean checkout
cannot run them using only checked-in test inputs.

The workflow runs nine of the 20 native suites and no Castle export/world or
new render-fix regression. MUL/worker/packed/staging/clipping/cadence tests are
also absent from its native coverage. Two native staging/DMA harnesses hardcode
Windows Clang and DLL linker flags, so merely adding them to Ubuntu CI will not
work without portability changes.

Repair: document/bootstrap fixtures deterministically, provide a single supported
audit/test entry point, make native harnesses platform-aware, and extend CI to
current contracts. Generate archived baselines from a known revision/source
policy rather than requiring one developer's build directory.

### AUD-09 — MMIO fixture assumes one feature configuration (P3)

Location: `sim/soc_mmio_tb.sv:72`. It always expects CPU feature word
0x80000001. Running the fixture with `--geometry-worker` correctly returns
0x80000003 and the fixture fails. Baseline configuration passes, as do the
separate directed CPU worker/counter tests.

Repair: derive expected feature words from the selected configuration or keep
explicit baseline/worker parameterized test cases. This is an expectation
mismatch; it is not evidence of incorrect feature advertisement by the RTL.

### AUD-10 — Primary programming instructions point at an older topology (P3)

Locations: `README.md:236`, `scripts/soc.py:501`, local `Chain11.cdf` /
`Chain12.cdf` / `Chain13.cdf`. README and programmer files direct users to
`build/quartus/SoC.sof`. The generic Quartus generator does not select the
accepted overlap/two-lane/geometry-worker macros. The current Castle firmware
requires the worker; its verified image is
`build/quartus-arch-stage5-worker/ArchStage5SoC.sof`.

Older instructions remain valid for their older examples, but README calls the
generic image the current image and offers no clear current-selection manifest.
Using it for the current Castle package will fail the worker capability gate
or restore an older topology. The three local CDF files were not edited.

Repair: expose a current build/deployment recipe and image identity at the main
entry point; label historical instructions by revision. Generate current
programmer references from the selected artifact, leaving user-owned references
under the user's control.

### AUD-11 — Geometry-result polling has no completion bound (P2)

Location: `firmware/include/geometry_worker.h:35`. The adapter waits until a
result count appears and checks the worker error bit, but has no cycle timeout
or check for inactive-with-no-output. If progress stops without that error bit,
the CPU loops forever and never reaches the normal firmware failure mailbox.
Other graphics waits already have finite budgets.

Repair: add a bounded, timer-wrap-safe completion/progress guard and an abort/
failure policy, then inject absent/stalled results in a native or RTL fixture.
This is a source-confirmed missing failure bound, not a reproduced physical
worker fault or an explanation of the earlier terrain bug.

### AUD-12 — Evidence and document encodings are inconsistent (P3)

`docs/benchmarks/arch-upgrade-001-stage-1/restored-status.json` contains loader
progress text followed by status output, so `json.loads` fails at its first
character. Its archive hash matches: evidence was not corrupted after capture,
but its extension/schema is misleading. `docs/command-buffer-staging.md` uses
an invalid UTF-8 byte (0x96), and `docs/architecture-upgrade-plan.md` contains
visible mojibake in stage headings.

Repair: preserve immutable raw benchmark bytes, add typed extracted status
records with provenance, and label mixed stdout as a log. Normalize current
first-party documentation to UTF-8 without rewriting historical raw captures.

## Recommended sequence

1. Fix strict package validation and unknown-feature handling together, then
   synchronize the published package schemas.
2. Align world projection and collision arithmetic/import bounds, with minimal
   independent counterexamples and no silent geometry changes.
3. Remove generated-profile build-order dependence and make current deployment
   identity discoverable.
4. Fix the stale regression/variant assertions, provide clean-checkout fixtures,
   and add the missing suites to platform-correct CI.
5. Bound worker failure waits and clean up current documentation/typed evidence.

None of these findings requires speculative CPU superscalar work, floating-point
conversion or a resource-heavy GPU redesign. Existing measured improvement
claims and raw historical hashes were not altered. This audit establishes the
listed reproductions and coverage; it does not certify every game/area, perform
formal hardware verification, or replace physical VGA/timing acceptance.


## Resolution

The original findings above remain the immutable review context. All twelve
are addressed by the subsequent [repair record](repository-consistency-fixes.md),
with independent regression cases, fresh generated fixtures and raw logs.
The running FPGA and historical benchmark captures were preserved.
