# Lakitu controls and disappearing geometry correction

October 13, 2026. Before-change reference: `1cd022e`.

The supplied `IMG_6674.mov` shows large missing castle/ground surfaces and
reversed controls. This was a camera-to-renderer convention error in the new
adapter. No original game logic, terrain/model mesh or FPGA RTL changes are
included in this correction.

## Root cause and fix

Original SDK look-at matrices use negative forward. The initial adapter flipped
only the Z row to feed the renderer's positive-forward projection. That changed
a proper rotation into a reflection: its determinant became negative, so the
source triangles' projected winding reversed. The existing GPU culls triangles
by signed screen area; consequently many faces pointing toward the camera were
discarded and normally hidden backs became visible. Native/FPGA replay matched
the same faulty conversion, so its agreement did not establish correct visible
geometry.

`camera_adapter.c` now converts X and Z together, including both translation
components. This preserves a positive determinant and the existing renderer's
winding contract. Y remains upward; the GPU projection already subtracts Y from
screen center. The original SDK camera routines, positions, focus, smoothing,
collision geometry and triangle indices are unchanged.

The existing stick-X reflection is required by this renderer convention. With
the corrected view, WASD agrees with rendered right/forward. The previous mouse
mapping also used opposite directions: positive horizontal motion now emits
original C-left, and negative horizontal motion emits C-right; the sender's
positive/upward pitch now emits C-up. Negative/downward pitch emits C-down.
The first packet still establishes a reference. `camera_input.h` centralizes
the conversion and releases C-buttons between queued pulses so fast mouse
motion cannot consume later events as held buttons. UDP packet format and other
game adapters are unchanged.

## Reproduction and validation

`reproduce_lakitu_culling.py` freezes one original grounds view and renders it
through production terrain clipping/commands and the actual GPU RTL, including
setup overlap and two raster lanes. The before/after cases use identical source
geometry, camera eye/focus, palette and hardware; only the X view row and its
translation change. Actors are excluded from this terrain reproduction.

| Framebuffer fixture | Non-background pixels out of 76,800 |
| --- | ---: |
| Reflected camera | 16,822 |
| Corrected camera | 73,001 |

The saved framebuffer images reproduce the missing ground before the fix and
show restored visible ground afterward. These pixel counts are measurements of
this one diagnostic view, not performance or full-level completeness claims.
They do not establish that every unrelated geometry problem has been resolved.

All **211 tests across 26 host suites passed**. The corrected FPGA replay
matched all 96 native records; live walk/jump, camera rotation, zoom and
punch/crouch routes reported zero engine faults. Held reset returned to spawn
once, and the verified new package remains selected and running. The hardware
SHA-256 remains
`140fa00e9d66def31e6897be29bc927469de72a9a051481186f7d7b2bc30be15`.

New independent regressions check WASD displacement along actual rendered axes
at four headings, original front-facing ground triangles against the GPU's
culling convention, mouse signs/wrap and queued pressed edges. The original
camera tests now also require a positive view determinant. Remaining texture,
alpha/decal and mesh-switch limitations are unchanged.

Build and reproduce:

```powershell
.\scripts\run.ps1 test_camera_controls_fix.py
.\scripts\run.ps1 reproduce_lakitu_culling.py
.\scripts\run.ps1 test_sm64_visual_camera.py
.\scripts\run.ps1 sm64_engine_slice.py diagnostic --visual
.\scripts\run.ps1 sm64_engine_slice.py game
.\scripts\run.ps1 verify_sm64_visual_camera.py
```

The board verifier reads back uploaded packages and compares its 96 animation,
camera, view, pose and movement records to the corrected native reference, then
runs live movement, camera and reset smoke tests. Live routes are host paced and
other senders are not disabled; they are not exact input replays or sustained
FPS measurements. Raw results, regression logs, framebuffer captures and
package manifests are retained in `docs/benchmarks/lakitu-controls-culling-001`.
