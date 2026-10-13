# Use a real Python runtime rather than the Windows Store execution alias.
if ($args.Count -lt 1) { throw 'Usage: .\scripts\run.ps1 soc.py sm64-scene [options]' }
$runnerScript = [string]$args[0]
$runnerAllowed = @('soc.py', 'load_game.py', 'portable_game.py', 'test_portable_pipeline.py', 'test_sdram_package.py', 'test_game_packages.py', 'test_quake_pipeline.py', 'diagnose_quake.py', 'sm64_subset.py', 'scene_assets.py', 'game_assets.py', 'diagnose_game.py', 'diagnose_animation.py', 'rv32i_subset.py', 'keyboard_udp.py', 'test_scene_pipeline.py', 'test_player.py', 'test_camera.py', 'test_animation.py')
$runnerAllowed += @('test_all.py','test_audit_fixes.py','current_deployment.py')
$runnerAllowed += @('compare_sdram_execution.py','build_sdram_execution.py','test_sdram_execution.py','verify_sdram_execution.py')
$runnerAllowed += @('quake_demo.py','mouse_udp.py','test_interactive_demo.py')
$runnerAllowed += @('sm64_castle.py','test_world_pipeline.py','profile_game.py','profile_cpu.py')
$runnerAllowed += @('test_terrain_offload.py')
$runnerAllowed += @('build_setup_overlap.py','measure_setup_overlap.py','build_pixel_lanes.py','measure_pixel_lanes.py','build_geometry_worker.py','measure_geometry_worker.py','geometry_vectors.py','build_geometry_probe.py','compare_geometry_game.py','test_geometry_loader.py')
$runnerAllowed += @('measure_terrain_offload.py','test_game_clock.py','measure_render_cadence.py','audit_stage6_timing.py','test_render_fixes.py')
$runnerAllowed += @('test_screen_edges.py','diagnose_screen_edges.py','replay_render_route.py','compare_render_frames.py','test_gpu_fractional.py','test_render_replay.py','test_packed_gfx.py','measure_gfx_staging.py','test_gfx_staging.py','test_dma_gfx.py')
$runnerAllowed += @('test_castle_gameplay.py')
if ($runnerScript -notin $runnerAllowed) { throw "Unknown project command: $runnerScript" }
$runnerPython = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object Source -NotLike '*WindowsApps*' | Select-Object -First 1 -ExpandProperty Source
if (-not $runnerPython) {
    $runnerBundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $runnerBundled) { $runnerPython = $runnerBundled }
}
if (-not $runnerPython) { throw 'Install Python 3.10+ or use a configured Python interpreter to run scripts directly.' }
$runnerArguments = @($args | Select-Object -Skip 1)
$runnerRoot = Split-Path $PSScriptRoot -Parent
Push-Location -LiteralPath $runnerRoot
try {
    & $runnerPython (Join-Path $PSScriptRoot $runnerScript) @runnerArguments
    $runnerResult = $LASTEXITCODE
} finally { Pop-Location }
exit $runnerResult
