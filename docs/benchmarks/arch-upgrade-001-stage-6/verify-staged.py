from pathlib import Path
import json,hashlib,subprocess
base=Path('docs/benchmarks/arch-upgrade-001-stage-6');manifest=json.loads((base/'manifest.json').read_text())['files'];paths=[(base/rel).as_posix() for rel in manifest]
result=subprocess.run(['git','cat-file','--batch'],input=''.join(':'+p+'\n' for p in paths).encode(),stdout=subprocess.PIPE,check=True);data=result.stdout;pos=0
for rel,p in zip(manifest,paths):
 end=data.index(b'\n',pos);header=data[pos:end].decode().split();pos=end+1
 if len(header)!=3 or header[1]!='blob':raise RuntimeError('Missing staged '+p)
 size=int(header[2]);blob=data[pos:pos+size];pos+=size+1
 if hashlib.sha256(blob).hexdigest()!=manifest[rel]:raise RuntimeError('Staged bytes differ '+p)
m=json.loads((base/'measurements.json').read_text())
for mode in ('tick-paced','uncapped','moving-tick-paced','moving-uncapped'):
 d=json.loads((base/('physical-'+mode+'.json')).read_text())
 if len(d['trials'])!=3 or d.get('failure') or any(not t['cadence']['atomic'] for t in d['trials']):raise RuntimeError('Bad trials '+mode)
r=json.loads((base/'accepted-running-check.json').read_text())
if r['segments']!=m['uncapped']['segments'] or r['last_status']['scratch']<=r['first_status']['scratch'] or r['last_status']['held']:raise RuntimeError('Deployment gate mismatch')
if not json.loads((base/'hardware-source-comparison.json').read_text())['exact']:raise RuntimeError('Hardware changed')
report=Path('docs/architecture-stage-6.md').read_bytes()
if any(x<32 and x not in (10,13,9) for x in report):raise RuntimeError('Report control bytes')
print('PASS staged SHA manifest:',len(manifest),'files; 12 atomic trials; unchanged hardware; selected package progression')
