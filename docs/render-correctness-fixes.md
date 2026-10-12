# Gameplay rendering fixes

Comparison baseline: Stage 6 result commit 15ce91c8080c965166296fae999d37387bba7f77.
Accepted 50 MHz Stage 5 image and Stage 6 uncapped firmware remain the rollback.
User video IMG_6600.mov shows thin ground/wall artifacts, weak castle definition,
and repeated 30 Hz poses at higher presentation rates.

Separate experiments: original baked vertex shading in the source adapter;
render-only interpolation with unchanged fixed-tick simulation; controlled depth
precision comparison before promoting any hardware change. Preserve face counts,
positions/winding, collision data, transitions and imported animation. Record
hardware timing/resources and physical trials for any selected hardware variant.
Do not infer complete-level correctness or performance from the phone recording.
