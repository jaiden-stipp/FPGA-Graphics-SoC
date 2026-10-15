# GitHub Actions portability repair

Investigated October 15, 2026, against baseline commit
`52ea5d83d74472190a817915364fbfd72d1ba972` and
[failed job 115677347468](https://github.com/jaiden-stipp/FPGA-Graphics-SoC/actions/runs/38510402536/job/115677347468).

## Causes and changes

The first reported failure was Icarus 12 elaborating the associative array and
`.exists()` calls in `sim/sdram_device_model.sv`. The replacement is a sparse,
open-addressed table with full word-address tags. Testbench preloads and probes
use `write_word` and `read_word`. Unwritten words still read as zero. The default
table stores up to 2^21 distinct words (8 MiB of simulated data at arbitrary
locations across the 128 MiB address space). Larger fixtures can override
`STORAGE_BITS`; exhaustion stops the simulation rather than aliasing addresses.
The new `sdram_model_storage_tb` deliberately tests colliding addresses,
unwritten colliding locations, overwrites and the highest SDRAM word address.

Replaying the previously blocked steps exposed additional issues:

- Icarus 12 reported `$isunknown` on a variable byte slice even when the printed
  bus was `12345678`, with DQM zero. The equivalent reduction-XOR/case-equality
  assertion detects X/Z without this false failure.
- Icarus 12 cannot assign variable part-selects of a packed struct member in
  the upstream command decoder. `scripts/soc.py` generates a simulation-only
  copy indexing the same bits of the complete packed command. A layout check
  requires `payload` to remain the final, least-significant struct field.
- The original-engine native regressions assumed Windows LLVM executable names,
  COFF linker options and a DLL. They now resolve LLVM tools through PATH (with
  the existing Windows installation as fallback), use PIC and ELF linker flags
  on Linux, and load the matching native library filename.
- LLVM 18 emits `__mulsi3` calls for some ordinary 32-bit operations, while GCC
  can emit `memset` for aggregate initialization. The freestanding package
  linker now supplies an archive with a software RV32I multiply helper and the
  existing `game_memory.c` services. Only referenced archive members are pulled
  into a program. The source audit permits and reports the supplied multiply
  helper, while continuing to reject other unsupported arithmetic helpers.
  `test_rv32i_builtins.py` runs 164 edge/random products on the actual CPU RTL
  and fails if any M-extension instruction is fetched.
- The primary Quake shareware URL returned HTTP 403 during this investigation.
  An HTTPS GWDG mirror returned the identical pinned archive. Download errors
  permit fallback; a hash mismatch still fails immediately. Both archive and
  extracted PAK retain their existing SHA-256 checks. Regression tests cover
  unavailable sources and corrupt responses.
- Failed Icarus runs now print and save their captured output. The workflow
  uploads simulation logs and native regression diagnostics even on failure.
- The final geometry-worker workflow step referenced ungenerated probe firmware
  and vector files. Selecting these simulations now regenerates deterministic
  vectors and builds/audits the CPU probe before elaboration. Its builder uses
  portable LLVM tool resolution. Both instruction auditors accept LLVM's byte
  and word disassembly formats, retaining their existing opcode restrictions.

## Scope

No synthesizable RTL, hardware generator, game logic, model data or FPGA image
was changed. These changes make the existing checks portable; they do not
measure or claim a hardware performance improvement. No FPGA programming was
performed for this repair.

## Validation

Local Linux validation uses an isolated WSL Ubuntu 22.04 checkout, Python 3.10,
Icarus 12.0 built from tag `v12_0`, LLVM 18.1.8 and the RV32I GCC toolchain.
This matches the major simulator/compiler versions in the failed Actions job,
but is not an actual GitHub-hosted rerun on Ubuntu 24.04/Python 3.12.

The uninterrupted Linux replay passed **all 24 workflow commands** after
dependency installation, including the complete baseline CPU stream simulations,
package builds, native suite and both feature configurations. The Mario stream
test completed movement, jumping, landing, held-key and respawn checks in
19,166,925 simulated cycles; this is a regression-test result, not game FPS.
Machine-readable step results, native test totals and SHA-256 hashes of the
saved logs are in [ci-portability-results.json](audits/2026-10-15/ci-portability-results.json).
Raw local logs are retained under `build/ci-portability/`; they are ignored by
Git. A new GitHub-hosted result requires pushing this fix and running Actions.

Windows ModelSim 10.5b passed `sdram_model_storage_tb`, `sdram_memory_tb`,
`sdram_instruction_cache_tb`, `sdram_exec_protection_tb` and `udp_loader_tb`.
The Windows camera-controls regression passed all three tests. The Linux
original-engine regression passed all 13 tests.
The final Linux native run passed **27 suites / 216 tests**, including the new
software-multiply CPU test, the disassembly-format regression and three download
failure/integrity checks. The software-multiply CPU test also passed Windows
ModelSim. All three geometry-worker feature tests passed under both simulators.

After adding the runtime archive, rebuilding with GCC produced byte-identical
`triangle.bin`, `game-test.bin`, `scene-test.bin` and `mario-test.bin` files to
those under baseline simulation. Their hashes are retained with the local logs.

A fresh Linux shareware download and extraction passed both existing hashes:

```text
ZIP ec6c9d34b1ae0252ac0066045b6611a7919c2a0d78a3a66d9387a8f597553239
PAK 35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af
```
