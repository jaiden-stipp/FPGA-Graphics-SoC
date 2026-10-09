# Games run on the CPU; scenes render on the graphics processor

The CPU owns the executable, input handling, game state, collision, AI, scoring,
and scene decisions. The graphics processor owns model/view transforms,
projection, clipping, rasterization, Z testing, palette/color memory, and VGA
presentation. Mesh indices/palettes and static assets are uploaded once; each
frame sends draw commands with model transforms. Animated actors also receive
CPU-evaluated posed vertices before rendering. No external PC runs game logic
at runtime.

The current board image is the **Mario controller** described in
[mario-controller.md](mario-controller.md): original low-poly character geometry,
RV32I movement/jumping/collision, FPGA rendering and UDP keyboard input. World
and actor profiles compile independently of the retained
[scene viewer](sm64-subset.md). The original **Catch** demo
remains available with `build-fw --app game --boot game`. It uses flat quads in the
renderer’s 3D world: move a blue paddle with KEY[1]/KEY3 to catch a falling block.
KEY[0] resets. Block color provides catch/miss feedback. `game_score` and
`game_misses` are inspectable CPU-RAM variables; there is no text HUD yet.

```c
initialize_input_and_graphics();
upload_mesh_assets_once();
for (;;) {
    wait_for_tick();
    buttons = read_input();
    update_game_state(buttons);
    gfx_begin_frame(++frame_id);
    draw_scene_using_mesh_handles();
    gfx_end_frame();
    gfx_wait_frame(frame_id);
}
```

The Catch implementation lives in `firmware/src/game.c`, with a typed graphics
API in `firmware/include/gfx.h`. It uploads two meshes, then sends two translated
mesh draws per frame. CPU movement and collision use integers in Q8.8 units; no
floating point, general matrix multiply, runtime division, or RV32M instructions
are needed. `gfx_scene.c` converts typed arguments to big-endian payloads, while
`gfx.c` adds framing/CRC and handles FIFO backpressure and completion.

The 32-bit MMIO cycle timer paces updates at nominally 30 Hz at 50 MHz. The loop
waits for each displayed frame before continuing, so at most one frame is in
flight. When rendering exceeds the tick budget, game updates run more slowly;
this starter has one update per frame and deliberately avoids unlimited catch-up.
The Mario application in `firmware/src/mario.c` uses the reusable controller in
`firmware/src/player.c`, with bounded catch-up to four physics ticks and a
following camera. Its settings and collision data come from a separate game
profile, while all character transforms use the existing GPU draw command.

## Build and verification

```sh
python scripts/soc.py bootstrap
python scripts/soc.py build-fw
python scripts/soc.py sim --full
python scripts/soc.py quartus-project
```

`build/firmware.mif` is the selected board image (scene by default). The game never exits during normal
play. `SOC_SCRATCH` tracks the last acknowledged displayed frame.
`build/triangle.hex` preserves the small one-frame regression.
`build/game-test.hex` compiles the same game with a 256-cycle tick period for
simulation. Its physics/input/render logic is identical to the board build.

`game_stream_tb` runs actual RV32I game firmware for 56 ticks, changes inputs,
checks movement limits, both-buttons neutrality, falling-block respawn and catch/miss
feedback, and verifies that meshes are uploaded only once. It uses synthetic
display completion after decoding each frame.
`soc_game_top_tb` uses the actual renderer and Intel memories, verifying two
displayed frames containing four rendered triangles each. Hardware resource fit,
timing, input feel and physical display still need board validation.

## Growing into a larger game

Start with a small fixed-point game compiled specifically for RV32I. Keep code,
stack, and game state within the 64 KiB CPU RAM budget. Use the renderer's 16 mesh
handles and indexed uploads for reusable geometry. Existing renderer limits are
128 vertices and 256 triangles per handle, Q8.8 coordinates, and indexed flat
colors; gameplay and assets should be designed around them.

Next additions can include a HUD made of mesh glyphs, controller input, audio,
larger asset storage, and a more efficient command encoder. External SDRAM/DMA
requires a CPU interface that supports wait states and memory arbitration; add
that only after preserving this working game-loop regression. CPU interrupts
also need trap/CSR support before frame completion can become an IRQ.
