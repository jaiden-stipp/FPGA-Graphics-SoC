import hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,package_segments,require_hardware
from current_deployment import selection
root=Path.cwd()
chosen,_,baseline=selection()
candidate=root/'build/mario-castle-gameplay-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json'
selection(candidate)
loader=Loader(timeout=0.3,retries=8)
result={'scope':'Physical local-code package loading and frame production; no hardware programming or full mission replay','candidate':str(candidate.relative_to(root)),'baseline':str(baseline.relative_to(root)),'hardware':chosen['hardware'],'candidate_segments':[{'address':a,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for a,b,_ in package_segments(candidate)]}
try:
    result['before']=loader.operation(STATUS)
    require_hardware(loader,json.loads(candidate.read_text()))
    loader.transfer(package_segments(candidate))
    time.sleep(2)
    result['sample_start']=loader.operation(STATUS)
    start=time.monotonic();time.sleep(1)
    result['sample_end']=loader.operation(STATUS);result['sample_seconds']=time.monotonic()-start
    result['frame_delta']=(result['sample_end']['scratch']-result['sample_start']['scratch'])&0xffffffff
    if result['sample_end']['scratch']&0xffff0000==0xdead0000 or not result['frame_delta'] or result['sample_end']['held']:
        raise RuntimeError('Gameplay firmware did not produce frames')
    result['candidate_pass']=True
finally:
    try:
        loader.transfer(package_segments(baseline));time.sleep(2)
        result['restored_start']=loader.operation(STATUS);time.sleep(1);result['restored_end']=loader.operation(STATUS)
        result['restore_pass']=not result['restored_end']['held'] and result['restored_end']['scratch']>result['restored_start']['scratch']
        if not result['restore_pass']:raise RuntimeError('Baseline restoration did not produce frames')
    finally:
        loader.close()
        (root/'build/castle-gameplay/physical-smoke.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
