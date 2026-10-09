"""Compare actual Quake GPU captures against independent original BSP coverage."""
import argparse
import json
from pathlib import Path
import diagnose_game
import quake_assets

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pak', type=Path, default=ROOT/'build/quake-shareware/pak0.pak')
    parser.add_argument('--profile', type=Path, default=ROOT/'profiles/quake-e1m1.json')
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    chunks, palette, _, _, provenance = quake_assets.prepare(args.pak, profile)
    diagnose_game.SKY = tuple(profile['appearance']['background'])
    out = ROOT/'build/quake-diagnostics'; out.mkdir(parents=True, exist_ok=True)
    results = []; states = {}
    for pose in ('standing', 'moving'):
        capture = ROOT/f'build/quake-sdram-{pose}.ppm'
        metadata = json.loads(capture.with_name(capture.name+'.json').read_text())
        states[pose] = {key: metadata[key] for key in ('x', 'y', 'z', 'view')}
        reference = diagnose_game.render(chunks, palette, view=metadata['view'],
            focal=profile['camera']['focal'], near_z=profile['camera']['near_z'])
        diagnose_game.ppm(out/f'{pose}-original-reference.ppm', reference)
        result = diagnose_game.compare(reference, capture)
        result['pose'] = pose
        results.append(result)
    if (states['moving']['y'] <= states['standing']['y'] or
        states['moving']['z'] <= states['standing']['z'] or
        states['moving']['view'][2] == states['standing']['view'][2]):
        raise SystemExit('FAIL: actual RV32I capture did not demonstrate turn, walk and jump')
    report = {'source_map_sha256': provenance['map_sha256'],
              'triangles': provenance['world_triangles'],
              'depth_policy': 'near_z >= 257 keeps floor(65536/z) within the unchanged 8-bit GPU depth format',
              'camera': profile['camera'], 'captures': results, 'observed_cpu_states': states,
              'maximum_interior_background_pixels_per_frame': 64,
              'scope': 'Interior geometry coverage, ignoring a 3-pixel reference-edge band; not bit-exact color/depth interpolation'}
    (ROOT/'build/quake-coverage.json').write_text(json.dumps(report, indent=2)+'\n')
    for item in results:
        print(item['pose'], 'interior background pixels:', item['interior_sky_pixels'])
    if any(item['interior_sky_pixels'] > 64 for item in results):
        raise SystemExit('FAIL: unexplained interior geometry gaps in actual GPU output')
    print('PASS original BSP coverage in actual post-depth GPU captures')

if __name__ == '__main__': main()
