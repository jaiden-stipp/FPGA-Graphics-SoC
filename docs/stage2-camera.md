# Stage 2: configurable following camera

The reusable fixed-point camera in `firmware/src/camera.c` runs on the RV32I
CPU. It submits a view matrix through the existing GPU command interface.
Original source models, the standing pose, player physics, CPU/GPU RTL and UDP
controls retain their stage 1 behavior.

## Behavior

Horizontal following filters the target position and adds bounded look-ahead
from actual movement. Stopping gradually removes the look-ahead. Vertical
following is slower in the air, so a jump moves Mario upward on the screen;
vertical lag is bounded to keep the character framed during falls. Manual
respawn, fall respawn and large teleports reset the follow history immediately.

The camera checks its target and eye segment against all 326 displayed terrain
triangles, including floors. Precomputed bounds and normals reject distant
surfaces before finite-triangle tests. The camera can choose a steeper pitch
or shorten its boom before crossing terrain. Obstacle response is immediate;
return to the base pitch and full distance is gradual. Preferred minimum
distance is a framing preference, never permission to cross a ceiling or wall.

Yaw stays fixed at zero. WASD/arrows, Space, R and the five-bit UDP protocol are
unchanged. Manual orbit and camera-relative movement remain later work.

## Profile settings

`profiles/sm64-mario.json` contains the `camera` object. Distances, heights and
clearance use the same integer Q8.8 world coordinates as the mesh/controller.
Pitch is in degrees; focal length is in framebuffer pixels.

| Setting | Current value | Meaning |
| --- | ---: | --- |
| `pitch_degrees` | 30 | Base pitch; conversion supplies 45, 60 and an overhead 90 degree fallback |
| `distance`, `min_distance` | 960, 384 | Preferred boom and minimum useful framing distance |
| `target_height` | 80 | Target above the character's feet |
| `follow_shift`, `look_shift` | 2, 2 | Horizontal target/look-ahead filters |
| `vertical_shift`, `air_shift` | 3, 4 | Grounded and airborne height filters |
| `lookahead_ticks`, `lookahead_limit` | 4, 48 | Movement prediction and maximum offset |
| `clearance` | 16 | Conservative margin around triangle planes/edges |
| `recovery_step` | 8 | Boom fraction recovered per tick, out of 256 |
| `max_vertical_lag`, `snap_distance` | 128, 256 | Height lag bound and teleport reset threshold |
| `focal`, `near_z` | 256, 128 | Existing GPU projection parameters |

Each filter advances by `(target-current) >> shift` per 30 Hz physics tick;
shift zero follows immediately. Small residuals snap to the target, avoiding
permanent integer drift. Configuration validation rejects unknown fields and
values outside bounded fixed-point ranges. Sine/cosine and surface metadata
are generated offline; runtime camera code uses no floating point or division
library. The software camera has no dependency on Mario display lists.

## Reproduction and checks

```powershell
.\scripts\run.ps1 soc.py sm64-mario --sim --fpga --quartus-bin "C:\intelFPGA_lite\18.1\quartus\bin64"
.\scripts\run.ps1 test_camera.py
.\scripts\run.ps1 diagnose_game.py
.\scripts\run.ps1 keyboard_udp.py --ip 192.168.7.2 --layout mario
```

Open `SoC.qpf` in Quartus Lite 18.1; program `build/quartus/SoC.sof`.
The tests execute the production C camera and controller on independent wall,
ceiling, slope, close-back-wall and floor fixtures, then walk and jump along the imported bridge
route. Independent floating-point segment/triangle intersections verify that
the camera-to-character segment stays outside those surfaces. View projection
checks character foot/head framing and visible jump rise.

The real RV32I stream test verifies jump movement in camera coordinates and
camera reset under command backpressure. Full board simulations send actual
MII UDP controls and capture GPU framebuffer RAM at spawn and the bridge,
standing and jumping. Capture JSON includes the exact emitted camera matrix
and projection, allowing independent coverage views to match each frame.

Camera avoidance covers the eye and its line to the character with a
conservative surface margin. It is not a full swept view-frustum collision
solver. Arbitrary narrow spaces and new profiles need their own framing tests.
Physical VGA smoothness, jumping and sustained FPS require an interactive
check on the programmed board. See [validation.md](validation.md) for results.

The Mario binary is 41,266 bytes, up from 25,338 in stage 1. Its BSS end is
`0xa158`, leaving 20,136 bytes before the reserved 4 KiB stack. Most added data
is the 326 camera surface records (12,388 bytes). This fits current RAM without
hardware changes; future animation/package data must retain the linker budget.
