"""Derive animation/Lakitu evidence summary from archived raw records."""
import hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/benchmarks/sm64-visual-camera-001'

def main():
    before=json.loads((OUT/'float-vertices/visual-physical.json').read_text())
    after=json.loads((OUT/'final/visual-physical.json').read_text())
    tests=json.loads((OUT/'final/summary.json').read_text())
    if not after['success'] or any(r['exit_code'] for r in tests):raise ValueError('Validation is incomplete')
    for record in (before,after):
        if record['diagnostic']['mismatches'] or record['diagnostic']['report'][2] or record['diagnostic']['report'][3]!=96:raise ValueError('Diagnostic incomplete')
    phases={}
    for column,name in enumerate(('movement','camera','pose')):
        phases[name]={}
        for label,record in (('float_vertices',before),('q14_vertices',after)):
            values=[r[column] for r in record['diagnostic']['trace']]
            phases[name][label]={'minimum_cycles':min(values),'median_cycles':statistics.median(values),'maximum_cycles':max(values)}
    old=phases['pose']['float_vertices']['median_cycles'];new=phases['pose']['q14_vertices']['median_cycles']
    mismatch=[i for i,(a,b) in enumerate(zip(before['diagnostic']['trace'],after['diagnostic']['trace'])) if a[3:18]!=b[3:18] or a[19:]!=b[19:]]
    if mismatch:raise ValueError('Replay state/camera differ between vertex backends: '+str(mismatch))
    package=after['candidate'];baseline=json.loads((ROOT/'docs/benchmarks/sm64-grounds-traversal-001/packages/mario-original-engine-grounds-exec.package.json').read_text())
    def sizes(p):return {'segments':{s['file']:s['bytes'] for s in p['segments']},'bss_bytes':p['execution']['bss_bytes']}
    result={'before_repository_commit':'6fd250e','hardware':after['hardware'],'host_suites':len(tests),'host_tests':sum(r['tests'] or 0 for r in tests),'native_fpga_replay_records':96,
            'cross_backend_non_pose_mismatch_ticks':mismatch,'diagnostic_phases':phases,'median_pose_cycle_reduction_percent':100*(old-new)/old,
            'quantization':json.loads((OUT/'final/visual-quantization.json').read_text()),'linked_sizes':{'baseline':sizes(baseline),'candidate':sizes(package)},
            'live_routes':[{'name':r['name'],'seconds':r['elapsed_seconds'],'frame_progress':r['fields']['game_frame'][0]-r['start_fields']['game_frame'][0],'fault':r['fields']['castle_engine_fault'][0]} for r in after['routes']],
            'reset':after['reset'],'scope':'Pose-backend comparison in a 96-update diagnostic; timer-read overhead included. Software/code/data layouts differ; hardware unchanged. No sustained FPS, full-game speedup or N64-console equivalence claim.',
            'artifacts_sha256':{p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='results-summary.json'}}
    (OUT/'results-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Verified',result['host_tests'],'tests;',result['native_fpga_replay_records'],'FPGA replay records; pose median reduction',round(result['median_pose_cycle_reduction_percent'],3),'percent')
    print(json.dumps(result['diagnostic_phases'],indent=2));print(json.dumps(result['linked_sizes'],indent=2))

if __name__=='__main__':main()
