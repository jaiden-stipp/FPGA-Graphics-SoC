# Original Mario grounds traversal milestone

October 13, 2026. Before-change comparison: `8f485f8`.

This extends the original-engine grounds port with swimming, ledge and hanging actions, crouching/crawling, acrobatic moves, attacks, health/damage, and death recovery. It uses the existing SDRAM-execution image and shared scene/game-package pipeline. No RTL, clock, GPU, model mesh, or original SM64 source file was changed.

## What changed

The earlier adapter dispatched individual actions but omitted the original action-group cancellation rules. In particular, walking or falling into the moat could continue through land actions instead of entering swimming. `engine_adapter.c` now calls the original stationary, moving, airborne, and automatic cancellation routines before its scoped action dispatch, including their original quicksand rules. Original special-floor handling, health updates, squish/shape updates, and camera-state bookkeeping run as well. Actor interaction processing and the complete original `execute_mario_action` entry remain outside this milestone.

`submerged_adapter.c` includes the unchanged original submerged translation unit to reach its private action functions. It retains original submerged cancellation, swimming-state initialization, and the selected normal-cap swimming/death actions. Water idle, plunge, breaststroke, swimming end, flutter kick, water jump/shore exit, water knockback, drowning, and water death use original movement code. Original health decreases underwater and recovers near the surface. Swimming's private timers are reset when restarting the area so replay/reset is deterministic.

The combined scoped dispatch has 94 explicit action entries, counted from the adapter sources. Added original actions include ledge grab/slow or fast climb/drop, hanging, squish recovery, crouch/crawl, crouch slide, backflip, long jump, ground pound, dive, slide kick, jump kick, punch, and relevant landing/knockback/death states. This is not the complete SM64 action set; held objects, caps, NPC-dependent states, and unrelated cutscenes remain incomplete. Unknown actions still latch a visible-to-tools fault while rendering/reset remain available.

Death and out-of-bounds requests cross a platform service. The adapter maps them back to the grounds spawn, reusing the already loaded collision pools. The death/floor warp deadlines are extracted from the pinned original `level_update.c` into `respawn.inc` during generation, rather than maintaining unrelated timer values. This is a scoped grounds respawn service, not the full original warp, lives/game-over, area-transition, or save engine. Automatic respawn updates the shared player's respawn count and resets camera/interpolation history.

Original interaction helpers replace the former drop/stop stubs, but no actor interpreter or actors are created. Behavior arrays in `platform_effects.c` are explicitly identity-only tokens for comparisons, not executable object behaviors. An attempt to use a held-object, slide mission timer, or star-spawn service faults explicitly. Audio, text, and camera effects remain omitted presentation services. The renderer still uses its existing imported visual clips and camera; original visual animation and Lakitu remain separate follow-up work.

## Controls

The existing IN-v1 eight-bit input ABI is unchanged:

| Input bit | Original Mario button |
| --- | --- |
| 16 | A: jump/swim/ledge climb |
| 32 | Z: crouch, crawl, ground pound; combine with A for original acrobatics |
| 64 | B: punch, kick, dive |
| 128 | Adapter reset, once per press |

The existing captured `mouse_udp.py` window sends Space for A, F or left mouse for Z, E for B, and R for reset. WASD/arrows steer; mouse look remains the existing camera adapter. The legacy five-bit `keyboard_udp.py` sender supports movement/jump/reset, but does not expose Z/B. Launch the eight-bit window with:

```powershell
.\scripts\run.ps1 mouse_udp.py --ip 192.168.7.2 --yaw 128
```

The adapter reflects stick X and converts renderer yaw to original camera yaw using the previously verified coordinate mapping. Input packet format and the other game adapters were not altered.

## Verification

All 24 repository regression suites passed: **203 tests**, including **13 original-engine tests**. The long movement regression exercises 48 routes of 900 moving/jumping updates plus 60 released-input updates each. Additional tests cover:

- Genuine moat entry and exit along a route on the original grounds collision mesh.
- Original underwater health loss and near-surface recovery.
- Drowning animation followed by the adapter's grounds respawn.
- Out-of-bounds death request and recovery.
- Repeated high falls: the first injures Mario; a further fall leads through original death handling and respawn.
- Original crouch, backflip, long jump, ground pound, and punch transitions.
- A genuine steep ledge grab on grounds that original logic correctly rejects, followed by an isolated climb-state fixture on a real flat castle floor.

The isolated health/fall/climb tests use a native-only initial-condition helper. It sets test starting position, action, and health; original queries, action bodies, damage, animations, and transitions still execute. The helper is not compiled into the FPGA executable. The climb fixture does not establish that an entire climbable castle ledge has been traversed in hardware. Hanging handlers are included, but no dedicated hanging route is claimed by this test set.

The new FPGA diagnostic compares its 96-update XYZ float bits, action IDs, and fault fields to the native build. The native-matched replay is a scoped reference comparison, not an N64-console equivalence claim. Its counter intervals include snapshot/read instrumentation; GPU, rendering, and full object updates are excluded.

The physical traversal verifier uploads/readback-verifies both diagnostic and game packages, then drives host-paced water-entry, shore-exit, ledge-approach, and advanced-control routes. It reads action, health, water level, pending warp timer, fault, position, and frame progression while the CPU is held. Other senders are not disabled, so live routes are smoke tests rather than cycle-exact replays or controlled FPS benchmarks. The final raw result is archived with its log. It leaves the verified game running at spawn after testing reset.

The final pass matched all 96 FPGA diagnostic states to native with no mismatches, and all four live routes had fault zero. Water entry ended in the submerged action group; the shore route ended outside it. The ledge-approach route ended swimming, so it is not evidence of a completed hardware ledge climb. The final held-reset record was `[-1328, 260, 4664]` with one respawn and full initial health. The unchanged hardware SHA-256 is `140fa00e9d66def31e6897be29bc927469de72a9a051481186f7d7b2bc30be15`.

## Recorded sizes and diagnostic intervals

These values are from the linked manifests or raw FPGA counters, not estimates of the complete game:

| Rendered package region | Bytes |
| --- | ---: |
| Local boot | 1,744 |
| SDRAM executable | 120,948 |
| Initialized state | 22,852 |
| BSS | 91,968 |
| Assets | 1,479,080 |

Initialized state plus BSS is 114,820 bytes. Compared with the archived `8f485f8` game, executable size increased from 89,364 bytes; this is added software functionality, not a performance improvement.

For the 96-update instrumented FPGA diagnostic, cycles were 24,674 minimum, 25,417 median, and 117,787 maximum. At the image's configured 50 MHz, median/max intervals calculate to 0.50834/2.35574 ms. The frequency was not externally calibrated, intervals include measurement instrumentation, and rendering/full gameplay work is excluded. The diagnostic observed 712 bytes of stack high water; that is not a bound for live water traversal or the full engine. No frame-rate or causal speedup comparison is claimed.

## Reproduce

```powershell
$env:PATH = 'C:\Program Files\LLVM\bin;' + $env:PATH
.\scripts\run.ps1 test_all.py --out build/engine-slice/traversal-regressions
.\scripts\run.ps1 sm64_engine_slice.py game
.\scripts\run.ps1 sm64_engine_slice.py diagnostic
.\scripts\run.ps1 verify_sm64_movement.py --traversal
```

Source is pinned by `sm64.lock.json`, software arithmetic by `softfloat.lock.json`. `source-report.json` hashes the additional original action/interaction units and the original warp service supplying delay constants. Target ELF auditing rejects unsupported instructions and unresolved helpers. The fixed-point renderer subset audit remains intact.

`docs/benchmarks/sm64-grounds-traversal-001/` preserves tests, native reference, original source-body hashes, final package segments/maps/ISA audits, physical records, source snapshots, and a SHA-256 manifest. Package-size and counter summaries are calculated from these artifacts. No hardware optimization or performance improvement is claimed. Earlier benchmark distributions belong to their earlier binaries and must not be attributed to this expanded movement build.
