# Integration milestones

The next selected goal is [traversable Peach's Castle and its Secret Slide star
mission](castle-milestone.md): grounds, all three interior areas, working
transitions, and the original slide box-star route through the shared porting
pipeline. This is planned work; the older milestone records below are retained
as implementation history.

1. **Boot and transport (included).** Pinned IP, CPU memory boundary, 64 KiB RAM,
   graphics FIFO/MMIO, C CRC encoder, firmware startup/linker and decoded-command
   test. Acceptance: actual RV32I execution emits the expected palette/view/frame/
   triangle/end commands and acknowledges completion with no errors.
2. **Render and display (simulation and Quartus verified, board work pending).** Full upstream
   rasterizer, depth/color memories, VGA path, frame counters and DE2-115 project.
   Full simulation renders pixels and swaps frames; the combined Quartus build
   fits and meets 50 MHz timing. Next acceptance: physical VGA displays the game.
3. **CPU game loop (included, board work pending).** Synchronized input, cycle
   timer, typed mesh API, and Catch firmware handle movement, collision and score
   on the CPU. Reuse uploaded mesh handles over multiple frames and poll display
   completion. Extend with a HUD, more game entities, view/projection helpers,
   and controller input. Keep game logic on the CPU and geometry/raster work on
   the renderer, rather than relying on the desktop UDP client during play.
4. **Wait-capable CPU memory boundary (included, SDRAM board verified).** Owned
   adapters hold the full pipeline for external accesses; stores complete once
   and loads resume with their result. The zero-wait path remains a regression
   baseline. See [sdram.md](sdram.md).
5. **DMA and larger scenes.** Once the CPU can tolerate wait states, add an
   arbitrated DMA command reader and external memory controller. Define ownership,
   byte order, bounds, abort/recovery, and completion semantics. Do not share the
   renderer's internal framebuffer ports without changing its memory arbitration.
6. **SM64 static scene and host input (included, board verified October 7, 2026).** Convert
   a declared display-list C subset to Q8.8 GPU meshes, audit fixed-point RV32I C,
   and send keyboard state over the inherited UDP interface. CPU camera updates
   continue to own every GPU command.
7. **Controllable Mario (included; new board image needs physical verification).**
   Preserve original low-poly model parts, assemble a declared rigid pose,
   and add a reusable integer controller with movement, facing, jump, slope/
   wall/ceiling collision, landing and respawn. Profiles supply world/actor assets
   independently of CPU/GPU RTL. Original skeletal animation and original SM64
   gameplay remain separate ports.
8. **Game loading (included; two-package reuse in stage 4).** Versioned CPU and
   external asset packages load over Ethernet with complete readback. Mario and
   an original Quake E1M1 scene explorer share a runtime ABI and the same hardware image;
   [stage4-packages.md](stage4-packages.md) describes switching. Larger engines
   still need a deliberate port and runtime mesh/code capacity strategy.
9. **Interrupts.** Add CPU trap/CSR/interrupt support before wiring frame_pending
   as an IRQ. Retain CPU frame/submission ownership.

Preserve upstream regressions when updating pinned commits, regenerate adapters,
and rerun both portable and full tests before accepting any dependency change.
