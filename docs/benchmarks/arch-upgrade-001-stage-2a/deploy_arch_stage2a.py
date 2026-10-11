from pathlib import Path
import sys,json,time
sys.path.insert(0,'scripts')
from load_game import Loader,package_segments,require_hardware,STATUS
candidate=Path('build/mario-castle-sdram-direct-packed-mul.package.json');baseline=Path('build/arch-stage1/baseline/mario-castle-sdram-direct-mul.package.json')
a=package_segments(candidate);b=package_segments(baseline)
assert [(addr,data) for addr,data,_ in a if addr>=0x80000000]==[(addr,data) for addr,data,_ in b if addr>=0x80000000]
last=json.loads(Path('build/arch-stage2a/physical-packed-moving.json').read_text());assert len(last['trials'])==3 and 'failure' not in last and last['restored_status']['initialized'] and not last['restored_status']['held']
loader=Loader()
try:
 require_hardware(loader,json.loads(candidate.read_text()))
 loader.transfer([seg for seg in a if seg[0]<65536])
 time.sleep(2);first=loader.operation(STATUS);time.sleep(1);second=loader.operation(STATUS)
 for d in (first,second):
  assert d['initialized'] and not d['held'] and 0<d['scratch']<0x10000000 and d['gpu_features']==3 and d['cpu_features']==0x80000001,d
 assert second['scratch']>first['scratch']
 report={'package':str(candidate.resolve()),'scope':'CPU-image upload/readback; immutable SDRAM assets reused after full readback in preceding physical trials; normal unprofiled Mario, frame progress and read-only capabilities','first_status':first,'second_status':second,'reused_asset_sha256':json.loads(candidate.read_text())['segments'][1]['sha256']}
 Path('build/arch-stage2a/final-running-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:loader.close()
