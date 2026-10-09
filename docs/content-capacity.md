# Content capacity and the next memory step

Measured against the stage 3 animated Mario image on October 8, 2026. These
are asset/storage estimates, not a claim that the complete original SM64
gameplay engine runs on this CPU.

The subsequent [SDRAM implementation](sdram.md) adds the external data window,
CPU wait states and a UDP package loader. Its full opaque terrain package builds
with 99,840 bytes of external assets and 15,696 bytes of local CPU code.
The table and unconnected-memory discussion below describe the earlier stage 3
baseline; current hardware checks are in [validation.md](validation.md).

| Configuration | Practical content target | Evidence / remaining work |
| --- | --- | --- |
| Current 64 KiB CPU RAM | Selected field/bridge and animated Mario | 538 triangles; 57,572-byte BSS end, 4 KiB reserved stack, 3,868 bytes left |
| 128 KiB internal CPU RAM | Full opaque Bob-omb Battlefield terrain and animated Mario | Estimated 116,076-byte code/data end before extra palette/alignment changes; new memory sizing and frame-time validation required |
| Board external SDRAM plus asset streaming | Store many levels or an entire game's assets; keep visible batches in the GPU | Requires SDRAM controller, latency-capable CPU memory bus, loading/streaming and a deliberate engine port |

The full opaque conversion retains all 1,043 original terrain triangles at the
4096-unit normalization. Together with the unchanged 212-triangle Mario mesh,
it uses nine of 16 GPU handles and 243 of 256 palette colors. There are 516
floor and 527 obstacle triangles. Original separately instantiated objects,
34 decal and 24 alpha triangles, textures, enemies, collectibles and audio
are outside this estimate. More colors and material features need a separate
budget; the flat palette is already close to its limit.

The full terrain's current record formats require 9,554 bytes of mesh data,
35,506 bytes of player collision data and 39,634 bytes of camera surfaces.
That is 58,504 additional bytes over the selected terrain, keeping the same
animation/code as the baseline. Sharing indexed triangle positions between
rendering, camera and collision could reduce this duplication, but its runtime
cost needs measurement. Spatial filtering/culling can reduce work as the area
grows; triangle count alone does not predict rasterization cost.

Quartus currently uses 338 of 432 M9K blocks (78% physical block utilization),
although the logical memory-bit report says 66%. A second 64 KiB CPU RAM bank
would nominally consume another 64 M9Ks, leaving roughly 30 blocks. Thus 128
KiB internal RAM is a reasonable candidate to synthesize and validate; there
is limited room for simultaneous framebuffer/depth/geometry RAM expansion.
This estimate does not establish fit, timing or playable full-level frame rate.

The DE2-115 has 128 MB SDRAM and 2 MB SRAM according to the
[Terasic hardware manual](https://www.terasic.com.tw/attachment/archive/502/DE2_115_User_manual.pdf).
Neither is currently connected to the SoC memory bus. The existing CPU assumes
zero-wait accesses; external memory requires a stall/wait interface or a
carefully designed cache/DMA arrangement. Larger storage makes full-game
asset capacity plausible, while CPU throughput, renderer features and the
gameplay port remain independent limits.

The estimate was generated in `build/capacity-estimate/` using a copy of the
current world profile with `selection_bounds` removed and
`sm64_subset.convert(..., emit_scene_header=False)`. It does not change the
active game profile, generated firmware header or programmed board scene.
