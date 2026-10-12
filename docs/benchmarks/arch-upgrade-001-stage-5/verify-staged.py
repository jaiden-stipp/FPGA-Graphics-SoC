from pathlib import Path
import json,hashlib,subprocess
folder=Path('docs/benchmarks/arch-upgrade-001-stage-5');manifest=json.loads((folder/'manifest.json').read_text())
listed=subprocess.check_output(['git','ls-files','--stage','--',str(folder)],text=True)
blobs={}
for line in listed.splitlines():
 info,path=line.split('\t',1);blobs[path]=info.split()[1]
paths=[str(folder/f).replace('\\','/') for f in manifest['files']]
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(blobs[p] for p in paths)+'\n').encode())
pos=0
for path in paths:
 end=raw.index(b'\n',pos);header=raw[pos:end].decode().split();size=int(header[2]);pos=end+1
 data=raw[pos:pos+size];pos+=size+1
 expected=manifest['files'][str(Path(path).relative_to(folder)).replace('\\','/')]
 if size!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:raise RuntimeError('Staged byte/hash mismatch '+path)
 if Path(path).read_bytes()!=data:raise RuntimeError('Working/staged bytes differ '+path)
if pos!=len(raw):raise RuntimeError('Unexpected batch remainder')
print('Verified exact staged raw bytes:',len(paths),'files')
r=json.loads((folder/'accepted-running-check.json').read_text());print('Selected image',r['sof_sha256'],'frame progress',r['first_status']['scratch'],r['last_status']['scratch'])
measure=json.loads((folder/'measurements.json').read_text())
assert measure['ordinary_cpu_change']['delta_cycles']<0
assert measure['game_equivalence']['exact'] and measure['gpu_equivalence']['exact']
assert len(measure['gpu_equivalence']['frames'])==3
for mode in ('control','worker'):
 for label in ('normal','detail'):
  assert len(json.loads((folder/('physical-'+mode+'-'+label+'.json')).read_text())['trials'])==3
assert len(json.loads((folder/'physical-worker-probe.json').read_text())['trials'])==3
print('Validated 15 complete physical trials and exact three-frame complete-game command/GPU equivalence')
