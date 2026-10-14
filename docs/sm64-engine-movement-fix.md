# Original-engine movement freeze correction

October 13, 2026. Before-change reference: `91215da`; original measured engine experiment: `ed85809`.

The later [grounds traversal milestone](sm64-engine-grounds-traversal.md) adds original water/health/group rules and broader movement coverage. Results below describe this earlier movement-fix binary.

The first engine slice's 96-update replay did not cover several ordinary movement transitions. Longer native replays reproduced unsupported `ACT_STEEP_JUMP` (`0x03000885`), `ACT_BACKWARD_ROLLOUT` (`0x010008ad`), and subsequently `ACT_AIR_HIT_WALL` (`0x000008a7`). The adapter latched those action IDs as faults. `castle.c` returned an error when that fault was set, so `portable_main.c` exited rendering and stopped advancing frames.

The user's stopped board did not answer either initial UDP status attempt. Its exact action/fault could therefore not be captured before reprogramming. The native failures establish a reproducible software cause matching movement/jump-triggered stops, not proof of the exact original board state. Loss of UDP response itself was not explained by these source-level failures.

## Changes

- Add unchanged original handlers for standing against a wall, steep jumps, forward/backward rollout, airborne butt slide, side flips and landing, wall kicks, airborne wall hits, soft bonks, and forward/backward air and ground knockback. The scoped dispatch now includes 43 action entries. Original source files and model data are unchanged.
- Keep frame rendering and input processing alive when the adapter encounters another unsupported state. The engine remains stopped with its fault latched; there is no substitute gameplay behavior. `castle_engine_fault` is a volatile telemetry symbol available through a held-memory read. Pressing R resets the slice so it can recover.
- Trigger reset on the input edge instead of every update while held. Reset increments the respawn count and clears camera/interpolation history, avoiding repeated expensive collision initialization and interpolation across the respawn.

Full original objects, camera, missions, transitions, and remaining actions are still incomplete. This correction does not turn the engine slice into the complete castle demo.

## Validation and measurement scope

The native engine suite passes eight tests. Its added movement regression runs eight yaw directions and six movement masks, each for 900 updates with repeated jump presses followed by 60 updates with movement released: 48 routes and 46,080 updates. All finish without an adapter fault. The test requires that steep-jump, backward-rollout, and airborne-wall-hit actions actually occur. The existing 13 default castle-gameplay tests also pass. Final target compilation retains the renderer subset audit, supported-instruction audit, and unresolved-symbol checks.

The first physical smoke-test attempt passed the backward-rollout route, advancing 491 frames with fault zero. Its diagonal route advanced 500 frames but latched `ACT_STANDING_AGAINST_WALL` (`0x0c400209`) when input was released near a wall. This confirmed both another missing handler and that the recovery patch prevented that fault from shutting down rendering. That failed attempt is retained separately as `movement-fix-physical-wall-fault.json` and its log. The original wall-standing handler was then added and movement-release checks incorporated into the native regression.

Reproduce:

```powershell
$env:PATH = 'C:\Program Files\LLVM\bin;' + $env:PATH
.\scripts\run.ps1 test_sm64_engine_slice.py
.\scripts\run.ps1 test_castle_gameplay.py
.\scripts\run.ps1 sm64_engine_slice.py game
.\scripts\run.ps1 verify_sm64_movement.py
```

The physical verifier uploads and readback-verifies the fixed package on the same existing `SdramExecSoC.sof`, drives two host-paced UDP movement/jump routes, reads the fault/player state while the CPU is held, and releases it again. It also checks that a held reset produces exactly one respawn. Other keyboard/mouse senders are not disabled; this is a live board smoke test, not a cycle-exact replay or controlled FPS benchmark. The test leaves the game running at spawn on success. Its raw record is `build/engine-slice/movement-fix-physical.json`, archived with the comparison evidence once complete.

The final physical pass succeeded: backward rollout advanced 490 frames with fault zero, and diagonal movement/steep jumping/wall contact advanced 499 frames with fault zero. Holding reset produced one respawn; the held-memory record returned the spawn coordinates `[-1328, 260, 4664]`. The final short frame-progress sample advanced from 51 to 81. These counts are liveness evidence, not a sustained FPS claim. All four uploaded segments passed readback verification. UDP replies resumed after programming the same hardware image; the reason the original stopped session lost its replies remains unconfirmed.

No RTL, clock, cache, or GPU change was made, and no performance improvement is claimed. The previous per-update timing distribution belongs to the earlier binary; it must not be attributed to this expanded action build. Exact package sizes and segment hashes are recorded in the new manifest.

Evidence is archived in `docs/benchmarks/sm64-engine-movement-fix-001/`, including pre-fix native failures, post-fix test logs, physical verification, source snapshots, manifests, and hashes.
