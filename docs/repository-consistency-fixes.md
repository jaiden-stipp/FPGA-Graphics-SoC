# Repository consistency repairs — October 12, 2026

Comparison baseline: audit commit `625dd74`. All twelve findings have a defined
repair below. No hardware RTL was changed, no hardware image was rebuilt, and
no package was loaded onto the physical FPGA during this task. User-owned
Chain11/12/13.cdf files and immutable historical evidence remain intact.

| Finding | Resolution |
|---|---|
| AUD-01 | Package/wire/direct-transfer validation rejects invalid numeric types, unsafe ranges, overlap and malformed fields before CPU hold. Failed verified transfers keep partial code halted; recovery policy is documented/tested. |
| AUD-02 | World conversion rejects collision faces whose padded bounds exceed signed 32-bit length/dot/cross capacity. It retains accepted faces exactly; it does not rewrite geometry. |
| AUD-03 | Multi-area worlds reject projection settings other than the existing 256 focal / 257 near contract. |
| AUD-04 | Central CPU/GPU feature maps reject unknown names, non-boolean requirements and invalid legacy discovery metadata before probing hardware. |
| AUD-05 | Legacy firmware builds always generate from explicit profiles. SDRAM and on-chip defaults are selected independently of existing headers. |
| AUD-06 | Package/project schemas cover optional feature/cadence/diagnostic/DMA/interpolation declarations; world IR now has a published schema. Tests validate real generated packages and source worlds. |
| AUD-07 | Fractional-packing regression compares legacy semantic fields and independently checks default-zero render flags. |
| AUD-08 | Complete host runner bootstraps pins, generates isolated source/linked-package fixtures, runs each suite separately, and records every result. DMA/staging native harnesses support Windows and Unix flags. CI installs Clang/LLD and the pinned schema validator, and runs all host suites plus directed feature variants. |
| AUD-09 | MMIO and UDP-loader feature assertions follow baseline/worker configuration; both simulator backends receive the selected macros. |
| AUD-10 | README distinguishes the selected Stage 5 topology from generic historical builds. A selection profile/tool checks the exact SOF hash, package integrity and recorded hardware features, and generates an owned build/current-deployment.cdf. |
| AUD-11 | Worker result waits have a wrap-safe per-result progress deadline and reject inactive/no-output states; error/timeout paths abort. |
| AUD-12 | Current documents are normalized to UTF-8, mojibake is corrected, and a hash-linked typed status derivative accompanies the untouched mixed-stdout historical capture. |

## Verification

All 169 checks across 21 host suites pass using a newly created
`build/audit-fixes/clean-fixtures` directory, rather than previously linked game
packages. The source checkouts are cached but clean at their pinned revisions;
fixtures and CPU/asset packages are regenerated. Logs include the initial test
failure and final results. Linux CI configuration was updated; its remote job
was not executed locally on this Windows host.

Nine directed ModelSim tests pass with geometry worker, two pixel lanes, setup
overlap and DMA-disabled feature configuration. Counterexamples cover malformed
addresses, unknown/mistyped features, overlapping/partial transfer failure,
projection mismatch, the long diagonal, source preservation, profile selection,
schema conformance, and worker success/error/inactive/stall/timer-wrap behavior.
The deployment test rejects a known-but-incompatible DMA package and a changed
hardware hash.

Real builds verify SDRAM -> on-chip -> repeated on-chip order. The on-chip
outputs are byte-identical and correctly contain 326 terrain triangles instead
of accidentally retaining the 1,043-triangle SDRAM profile. The guarded Castle
normal/test packages pass C subset, linked instruction and asset checks. All
85 accepted RTL/SDC input hashes remain unchanged.

The new watchdog firmware CPU segment is 29,176 bytes versus the preserved
29,124-byte package: +52 bytes with this compiler/configuration. Both use the
same 883,160-byte asset segment, SHA-256
`65413afb4c49b42581291d48547d58407cd118678d02bca0bb1869f790b226d4`.
Models, collision, shaders' authored color policy and simulation timing remain
unchanged for this accepted Castle content. No FPS, latency, power, frequency
or resource improvement is claimed from these correctness repairs.

The default 5,000,000-cycle watchdog is a design failure budget (100 ms at the
configured 50 MHz), not a measured execution time or an optimal timeout.
The current collision subset intentionally rejects unsupported large faces;
a wider arithmetic implementation remains an explicit future upgrade.

## Reproduce

With Git, Clang, LLD and LLVM utilities on PATH:

```powershell
python -m pip install -r requirements-dev.txt
.\scripts\run.ps1 test_all.py --fixtures-dir build/fresh-test-fixtures --out build/tests
.\scripts\run.ps1 soc.py sim --full --simulator modelsim --geometry-worker --disable-command-dma --two-pixel-lanes --setup-overlap --tests soc_mmio_tb,cpu_geometry_tb,geometry_worker_tb,cpu_mul_tb,soc_cpu_counters_tb,cpu_counter_pipeline_tb,packed_mmio_tb,sdram_cache_tb,udp_loader_tb
```

The guarded package is retained separately at
`build/mario-castle-audit-fixed-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json`.
To verify that artifact and produce a programmer reference without programming:

```powershell
.\scripts\run.ps1 current_deployment.py --package build/mario-castle-audit-fixed-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json --write-cdf
```

The selection profile's default package names the established artifact; the
README recipe rebuilds that normal name from current source when requested.
The separate guarded build preserves the established local binary for comparison.
Physical loading was not part of these repository fixes. A later load must
still perform capability preflight and full memory readback.

[Validation summary](audits/2026-10-12/fixes/summary.json),
[real build-order comparison](audits/2026-10-12/fixes/build-order.json),
[hardware hashes](audits/2026-10-12/fixes/hardware-source-comparison.json),
[typed historical status](audits/2026-10-12/fixes/stage1-restored-status.extracted.json).

## Physical deployment, October 12, 2026

The guarded audit-fixed package was loaded onto the accepted Stage 5 hardware
image. Quartus programming succeeded with zero errors and warnings. Full
readback verified 29,176 CPU bytes and 883,160 asset bytes before CPU release.
The running CPU reported the expected capabilities and its frame counter
advanced from 2 to 62 across the one-second startup check. This verifies boot
and progress; it is not a performance comparison or a visual gameplay check.
The default deployment selection now references this guarded package. The
previous interpolated package remains available for rollback.

[Physical boot evidence](audits/2026-10-12/boot/boot-check.json),
[programming log](audits/2026-10-12/boot/programming.log),
[deployment log](audits/2026-10-12/boot/deployment.log).
