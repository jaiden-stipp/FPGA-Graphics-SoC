from pathlib import Path
import json,re,statistics,hashlib,subprocess,sys
sys.path.insert(0,'scripts')
from profile_cpu import GPU
out=Path('build/arch-stage4')
report={'experiment':'ARCH-UPGRADE-001 Stage 4','baseline_commit':'8082afd','accepted_stage3_commit':'0a6434b','implementation_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'clock_hz':50000000,'hardware':{},'physical':{},'replays':json.loads((out/'replay-measurements.json').read_text())['replays']}
for mode,name in [('control','ArchStage4ControlSoC'),('dual','ArchStage4SoC')]:
 fit=Path('build/quartus-arch-stage4-'+mode)
 summary=(fit/(name+'.fit.summary')).read_text();rpt=(fit/(name+'.fit.rpt')).read_text();sta=(fit/(name+'.sta.summary')).read_text();stareport=(fit/(name+'.sta.rpt')).read_text()
 def metric(label,text=summary):return int(re.search(re.escape(label)+r'\s*:\s*([\d,]+)',text)[1].replace(',',''))
 def resource(label):return int(re.search(r';\s*'+re.escape(label)+r'\s*;\s*([\d,]+)',rpt)[1].replace(',',''))
 timings=re.findall(r'Type\s*:\s*([^\r\n]+)\s+Slack\s*:\s*([-\d.]+)',sta)
 hw={'logic_elements':metric('Total logic elements'),'memory_bits':metric('Total memory bits'),'multipliers_9bit':metric('Embedded Multiplier 9-bit elements'),'plls':metric('Total PLLs'),'m9k':resource('M9Ks'),'physical_memory_bits':resource('Total block memory implementation bits'),'setup_min_ns':min(float(v) for t,v in timings if ' Setup ' in t),'hold_min_ns':min(float(v) for t,v in timings if ' Hold ' in t),'timings':[{'type':t,'slack_ns':float(v)} for t,v in timings],'sof_sha256':hashlib.sha256((fit/(name+'.sof')).read_bytes()).hexdigest()}
 for label in ('Clocks','Input Ports','Input Port Paths','Output Ports','Output Port Paths'):
  m=re.search(r';\s*Unconstrained '+label+r'\s*;\s*(\d+)\s*;\s*(\d+)\s*;',stareport)
  if not m:raise ValueError('Missing constraint coverage')
  hw['unconstrained_'+label.replace(' ','_').lower()]={'setup':int(m[1]),'hold':int(m[2])}
 report['hardware'][mode]=hw
 normal=json.loads((out/('physical-'+mode+'-normal.json')).read_text());detailed=json.loads((out/('physical-'+mode+'-detail.json')).read_text());probe=json.loads((out/('physical-'+mode+'-probe.json')).read_text())
 def values(entries,getter):
  v=[getter(t) for t in entries];return {'trials':v,'median':statistics.median(v),'minimum':min(v),'maximum':max(v)}
 normal_data={k:values(normal['trials'],lambda t:t['metrics'][k]) for k in normal['trials'][0]['metrics']}
 normal_data['observed_fps']=values(normal['trials'],lambda t:t['observed_fps'])
 detail_data={k:values(detailed['trials'],lambda t:t['gpu'][k]) for k in detailed['trials'][0]['gpu']}
 detail_data['render_cpu_cycles']=values(detailed['trials'],lambda t:t['phases']['render']['cycles']);detail_data['frame_ids']=[t['metrics']['frame'] for t in detailed['trials']]
 probes=[]
 for i in range(3):
  pr={k:values(probe['trials'],lambda t:t['meshes'][i][k]) for k in probe['trials'][0]['meshes'][i]}
  pr['before_swap_wait']=values(probe['trials'],lambda t:t['meshes'][i]['total_cycles']-t['meshes'][i]['swap_wait_cycles'])
  probes.append(pr)
 report['physical'][mode]={'normal':normal_data,'detail':detail_data,'probe':probes}
report['hardware_delta']={k:report['hardware']['dual'][k]-report['hardware']['control'][k] for k in ('logic_elements','memory_bits','multipliers_9bit','plls','m9k','physical_memory_bits')}
a=report['physical']['control']['normal']['game_cpu_cycles']['median'];b=report['physical']['dual']['normal']['game_cpu_cycles']['median']
report['ordinary_cpu_change']={'control_cycles':a,'dual_cycles':b,'delta_cycles':b-a,'change_percent':(b/a-1)*100}
for i in range(3):
 a=report['physical']['control']['probe'][i];b=report['physical']['dual']['probe'][i]
 for k in GPU[:7]:
  if a[k]['trials']!=b[k]['trials']:raise RuntimeError('Probe event mismatch '+k)
report['scope']='Two-lane raster plus parity banking/parallel clear as one architecture change. Clocks, command ABI, firmware and game assets unchanged. Three physical resets per image for each synthetic probe, ordinary standing game and instrumented standing game. Exact replay geometry excludes actors; physical game progress is not physical framebuffer readback. No power or Fmax claim.'
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
print('Hardware delta',report['hardware_delta']);print('Ordinary CPU',report['ordinary_cpu_change'])
for i in range(3):
 a=report['physical']['control']['probe'][i];b=report['physical']['dual']['probe'][i]
 print('Probe',i,'raster',a['raster_cycles']['median'],b['raster_cycles']['median'],'before_swap',a['before_swap_wait']['median'],b['before_swap_wait']['median'],'clear',a['clear_cycles']['median'],b['clear_cycles']['median'])
for mode in report['hardware']:print(mode,'timing',report['hardware'][mode]['setup_min_ns'],report['hardware'][mode]['hold_min_ns'])
