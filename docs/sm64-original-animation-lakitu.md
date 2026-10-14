# Original animation and normal Lakitu camera

October 13, 2026. Before-change repository reference: `6fd250e`.

Follow-up: the initial `1cd022e` release had a reflected camera conversion that
reversed GPU backface culling and mouse directions. Native/FPGA agreement alone
did not detect that renderer-contract error. The corrected X/Z conversion,
independent direction tests and actual GPU framebuffer reproduction are recorded
in [controls and culling correction](lakitu-controls-culling-fix.md). Measurements
below remain the historical milestone results, not verification of the old
conversion's visible geometry.

This software milestone replaces the original-engine grounds package's independent six-clip animation selector and custom orbit camera. It reuses the same source/asset conversion, game-package loader, renderer, CPU, GPU and accepted SDRAM-execution hardware. Original SM64 sources and mesh geometry are unchanged.

## Animation bridge

`visual_adapter.c` consumes the engine's actual animation ID/frame, original indexed channels, original translation flags and original translation multiplier. All 209 original animation descriptors remain available. The generated `visual.inc` preserves the selected low-poly GeoLayout's 20 parent-ordered joints and the packed mesh's 136 original local vertices/bindings. The outer model scale is extracted from `mario_geo`, rather than normalizing Mario to a chosen height. Full original object rotation/scale and graphics-position offsets are applied once; the renderer no longer adds its coarse facing rotation again.

Original SDK XYZ bone matrices, ZXY object/GeoLayout rotation matrices, matrix composition, torso tilt, head rotation and hand/foot punch scaling routines execute unchanged. Root X/Z translation is retained wherever the original flags permit it. Animation advancement occurs once per simulation tick, independently of repeated/interpolated rendered frames. The frame -1 initialization case samples zero without advancing the engine twice. The carried-object callback has no effect with no carried actor; its upstream implementation was inspected.

The first implementation transformed every vertex using software floating point. Board measurements showed that pose work alone exceeded the 30 Hz simulation interval. The final bridge calculates original SDK matrices, lowers the final matrices to Q14, then transforms vertices with integer arithmetic using the CPU's existing low-MUL instruction. Generated coordinate bounds and runtime coefficient/translation admissions prove the int32 sums cannot overflow. Out-of-range results return an explicit renderer fault. This changes final vertex quantization, not original animation channels or game behavior.

Native comparisons of the first and last frames of all 209 animations cover 418 poses and 56,848 vertices. Maximum coordinate difference from the SDK float-vertex reference is one GPU unit, equal to 0.25 source units. This bound applies to that tested normal model fixture, not every possible squish/cap/object state. The original SDK float reference remains callable in native tests and buildable as an alternative FPGA diagnostic.

## Camera bridge

`camera_adapter.c` includes unchanged `camera.c` and schedules its normal grounds modes: free roam/close Lakitu, behind Mario, water surface, eight directions and C-up. Original initialization, terrain queries, obstruction handling within those modes, focus/pan behavior, smoothing, transitions and camera shakes run through original routines. Mario's original first-person action now handles C-up entry/exit. SDK `mtxf_lookat` is converted to the renderer's positive-forward, player-relative Q8 view format. Render interpolation interpolates that view matrix instead of reconstructing the former orbit rotation.

The actual game initialization and respawns use the 180-degree heading extracted from the original grounds `MARIO_POS` script. The older zero-heading initialization remains an explicit controlled fixture for movement/visual diagnostics, so those comparisons use the same initial conditions. Gameplay movement uses the last original camera yaw; deterministic diagnostics may still request an explicit yaw.

The adapter schedules the normal camera path rather than the full `update_camera` orchestration. Castle grounds has no positional camera-trigger table or area-specific case in `camera_course_processing`. Other-level trigger dispatch, NPC/object cutscenes, intro/ending scenes, star/door cutscenes and R-button camera selection are not included. Their services are not replaced with successful fake behavior. Read-only star gating sees an empty slot because this grounds slice has no collected-star/save engine.

The current renderer retains focal length 256, near-plane conventions and its existing flat palette. This is an original normal-camera routine port within the current renderer, not pixel-identical N64 camera/projection output. The selected mesh still fixes cap-on/open-eye/closed-hand branches and does not relight animated normals. Textures, dynamic eye/hand/cap variants, alpha decoration, held actors, other castle areas, missions and full saves remain separate work.

## Input and reusable pipeline

The UDP IN-v1 packet and other game ports are unchanged. WASD/arrows remain relative to the actual camera; Space/A, F or left mouse/Z, E/B and R/reset retain their previous meanings. The mouse window's absolute look fields are converted to original C-button events: a 32-unit horizontal accumulated change emits C-left/right; a 16-unit vertical accumulated change emits C-up/down. The first packet establishes a reference and reset clears it. These are adapter input thresholds, not benchmark results. C-up first zooms in if zoomed out; another C-up enters first-person mode. A/B/C-side/down exits using original logic.

```powershell
.\scripts\run.ps1 sm64_engine_slice.py game
.\scripts\run.ps1 load_game.py build/mario-original-engine-grounds-exec.package.json
.\scripts\run.ps1 mouse_udp.py --ip 192.168.7.2 --yaw 128
```

The source-specific code lives in `firmware/engine` and the engine variant of `castle.c`. Shared scene/mesh commands, package contracts, loader and other game adapters remain reusable. Native closure generation tracks camera function-pointer table dependencies, preserves retained original function bodies, and omits unused cinematic actors. Target builds compile unchanged upstream sources; disabling compiler global-variable merging for the camera lets linker section collection discard unrelated cutscenes. ISA audits permit RV32I plus the already implemented low MUL; no FPU/RTL change is included.

## Verification and measured evidence

The diagnostic performs 96 fixed, unpaced movement/camera/pose updates, including C-right and C-down events, without GPU rendering. It records XYZ/action/fault, animation ID/frame, camera mode/yaw and float bits, pose/view hashes, view matrix entries, and separate cycle timers. These timers include timer-read overhead and execute in a diagnostic memory/cache context; they are not full-frame or steady-state game costs.

The first float-vertex attempt matched all 96 native records. Its live verifier then falsely rejected progress because a loader BEGIN/read/COMMIT sequence clears the scratch register before the next frame; the held `game_frame` value showed progression and engine fault was zero. The baseline was automatically restored. Raw failed-attempt records are preserved. The corrected verifier compares held frame counters and restores the archived baseline on genuine failure.

The measured float-vertex and final Q14 diagnostic records, package identities, tests and summaries are preserved under `docs/benchmarks/sm64-visual-camera-001`. The hardware identity remains `140fa00e9d66def31e6897be29bc927469de72a9a051481186f7d7b2bc30be15`. Compare measured diagnostic work and linked sizes with the results summary; do not interpret short live frame samples as sustained FPS or this scoped reference comparison as N64-console equivalence.

All 208 host tests across 25 suites passed, including five new visual/camera tests and the 13 existing engine tests. The final FPGA diagnostic matched all 96 native records; the non-pose state/camera fields also match between the float-vertex and Q14 replays. All four live routes had fault zero, and held reset produced exactly one reset at the original grounds spawn. The final package is loaded and selected.

| Diagnostic phase | Float-vertex median cycles | Q14-vertex median cycles |
| --- | ---: | ---: |
| Original movement | 28,304 | 26,122.5 |
| Original camera | 255,857.5 | 244,475.5 |
| Pose | 2,087,726.5 | 769,589.5 |

Pose median cycles decreased 63.137% in this 96-update replay. The original camera/movement algorithms were not optimized; their small timing differences occur with changed software/data layout and cache context. At the configured 50 MHz, the pose medians correspond to about 41.75 and 15.39 milliseconds. This compares two implementations of the newly added visual bridge, not a 63% speedup over the previous game or a whole-game FPS improvement.

| Linked game region | `6fd250e` bytes | Final bytes |
| --- | ---: | ---: |
| Local boot | 1,744 | 1,744 |
| SDRAM code/constants | 120,948 | 170,208 |
| Initialized state | 22,852 | 22,952 |
| BSS | 91,968 | 95,308 |
| Assets | 1,479,080 | 1,478,336 |

The new original software routines add code and simulation cost compared with the earlier custom visual/camera path. Full per-vertex floating point was too costly for the tick budget; bounded integer vertex lowering makes that addition more practical. A controlled scene/movement FPS comparison remains future profiling work.

Reproduce host checks and board verification:

```powershell
.\scripts\run.ps1 test_sm64_visual_camera.py
.\scripts\run.ps1 test_all.py --out build/tests-visual-camera --fixtures-dir build/tests-visual-camera/fixtures
.\scripts\run.ps1 sm64_engine_slice.py diagnostic --visual
.\scripts\run.ps1 sm64_engine_slice.py game
.\scripts\run.ps1 verify_sm64_visual_camera.py
.\scripts\run.ps1 summarize_sm64_visual_camera.py
# Alternative SDK float-vertex replay package, for comparison:
.\scripts\run.ps1 sm64_engine_slice.py diagnostic --visual --float-vertices
```

The board verifier uploads and reads back complete packages, compares the 96 records, runs live walk/jump, camera rotation, zoom and punch/crouch smoke tests, and checks held reset. Live inputs are host paced, and other senders are not disabled. A successful run leaves the new game at spawn. The report does not establish full-level traversal, hanging routes or mission completion.

Resume-safe scope: ported original engine-selected skeletal animation and normal Lakitu camera routines to the existing RV32I/SoftFloat SoC, validated a native/FPGA replay, and measured a bounded integer lowering of final vertex transforms. No new hardware-performance claim follows from this milestone.
