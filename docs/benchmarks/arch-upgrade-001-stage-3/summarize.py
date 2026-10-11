from pathlib import Path
import json,re,statistics,hashlib
out=Path('build/arch-stage3')
report={'experiment':'ARCH-UPGRADE-001 Stage 3','baseline_commit':'6153efa','clock_hz':50000000,'hardware':{},'physical':{},'replays':{}}
for mode,name in [('serial','ArchStage3SerialSoC'),('overlap','ArchStage3SoC')]:
 fit=Path('build/quartus-arch-stage3-'+mode)
 summary=(fit/(name+'.fit.summary')).read_text();rpt=(fit/(name+'.fit.rpt')).read_text();sta=(fit/(name+'.sta.summary')).read_text();stareport=(fit/(name+'.sta.rpt')).read_text()
 def metric(label,text=summary):
  return int(re.search(re.escape(label)+r'\s*:\s*([\d,]+)',text)[1].replace(',',''))
 def resource(label):
  return int(re.search(r';\s*'+re.escape(label)+r'\s*;\s*([\d,]+)',rpt)[1].replace(',',''))
 timings=re.findall(r'Type\s*:\s*([^\r\n]+)\s+Slack\s*:\s*([-\d.]+)',sta)
 hw={'logic_elements':metric('Total logic elements'),'memory_bits':metric('Total memory bits'),'multipliers_9bit':metric('Embedded Multiplier 9-bit elements'),'plls':metric('Total PLLs'),'m9k':resource('M9Ks'),'physical_memory_bits':resource('Total block memory implementation bits'),'setup_min_ns':min(float(v) for t,v in timings if ' Setup ' in t),'hold_min_ns':min(float(v) for t,v in timings if ' Hold ' in t),'timings':[{ 'type':t,'slack_ns':float(v)} for t,v in timings],'sof_sha256':hashlib.sha256((fit/(name+'.sof')).read_bytes()).hexdigest()}
 for label in ('Clocks','Input Ports','Input Port Paths','Output Ports','Output Port Paths'):
  match=re.search(r';\s*Unconstrained '+label+r'\s*;\s*(\d+)\s*;\s*(\d+)\s*;',stareport)
  if not match:raise ValueError('Missing constraint coverage')
  hw['unconstrained_'+label.replace(' ','_').lower()]={'setup':int(match[1]),'hold':int(match[2])}
 report['hardware'][mode]=hw
 normal=json.loads((out/('physical-'+mode+'-normal.json')).read_text())
 detailed=json.loads((out/('physical-'+mode+'-detail.json')).read_text())
 probe=json.loads((out/('physical-'+mode+'-probe.json')).read_text())
 def values(entries,getter):
  v=[getter(t) for t in entries];return {'trials':v,'median':statistics.median(v),'minimum':min(v),'maximum':max(v)}
 normal_data={k:values(normal['trials'],lambda t:t['metrics'][k]) for k in normal['trials'][0]['metrics']}
 normal_data['observed_fps']=values(normal['trials'],lambda t:t['observed_fps'])
 detail_data={k:values(detailed['trials'],lambda t:t['gpu'][k]) for k in detailed['trials'][0]['gpu']}
 detail_data['render_cpu_cycles']=values(detailed['trials'],lambda t:t['phases']['render']['cycles'])
 detail_data['frame_ids']=[t['metrics']['frame'] for t in detailed['trials']]
 report['physical'][mode]={'normal':normal_data,'detail':detail_data,'probe':[ {k:values(probe['trials'],lambda t:t['meshes'][i][k]) for k in probe['trials'][0]['meshes'][i]} for i in range(3)]}
 report['replays'][mode]={}
 for kind in ('castle','quake','fixtures'):
  match=json.loads((out/(kind+'-'+mode+'-comparison.json')).read_text())
  timeline=(out/(kind+'-'+mode)/'capture/frame-timeline.log').read_text()
  frames={}
  for line in timeline.splitlines():
   parts=line.split();f=int(parts[0]);frames.setdefault(f,{})
   if parts[1]=='begin':frames[f]['begin']=int(parts[2])
   elif parts[1] in ('swap_request','setup_metrics'):
    if parts[1]=='swap_request':frames[f]['swap_request']=int(parts[2])
    for kv in parts[3:]:
     k,v=kv.split('=');frames[f][k]=int(v)
  for f in frames:frames[f]['begin_to_swap_request']=frames[f]['swap_request']-frames[f]['begin']
  report['replays'][mode][kind]={'exact':match['exact'],'triangles':match['after_triangles'],'frames':frames}
report['hardware_delta']={k:report['hardware']['overlap'][k]-report['hardware']['serial'][k] for k in ('logic_elements','memory_bits','multipliers_9bit','plls','m9k','physical_memory_bits')}
a=report['physical']['serial']['normal']['game_cpu_cycles']['median'];b=report['physical']['overlap']['normal']['game_cpu_cycles']['median']
report['ordinary_cpu_change']={'serial_cycles':a,'overlap_cycles':b,'delta_cycles':b-a,'change_percent':(b/a-1)*100}
report['scope']='Synthetic GPU probes and ordinary standing update+render, not complete-game FPS improvement. Aggregate raster_cycles semantics change from serial work to busy union. Replays exclude actors/physical framebuffer.'
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
print('Hardware delta',report['hardware_delta']);print('Ordinary CPU',report['ordinary_cpu_change'])
for i in range(3):
 a=report['physical']['serial']['probe'][i];b=report['physical']['overlap']['probe'][i]
 print('Probe',i,'raster',a['raster_cycles']['median'],b['raster_cycles']['median'],'total excluding swap',a['total_cycles']['median']-a['swap_wait_cycles']['median'],b['total_cycles']['median']-b['swap_wait_cycles']['median'])
for mode in report['hardware']:
 print(mode,'timing',report['hardware'][mode]['setup_min_ns'],report['hardware'][mode]['hold_min_ns'])
