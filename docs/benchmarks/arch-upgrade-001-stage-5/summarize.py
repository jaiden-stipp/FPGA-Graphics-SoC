from pathlib import Path
import json,re,statistics,hashlib,subprocess,sys
sys.path.insert(0,'scripts')
from profile_cpu import GPU
out=Path('build/arch-stage5')
report={'experiment':'ARCH-UPGRADE-001 Stage 5','baseline_commit':'40219cec','accepted_stage4_commit':'e0d776c','implementation_commit':'df0649df','clock_hz':50000000,'hardware':{},'physical':{}}
for mode,name in [('control','ArchStage5ControlSoC'),('worker','ArchStage5SoC')]:
 fit=Path('build/quartus-arch-stage5-'+mode)
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
 normal=json.loads((out/('physical-'+mode+'-normal.json')).read_text());detailed=json.loads((out/('physical-'+mode+'-detail.json')).read_text());probe=None
 def values(entries,getter):
  v=[getter(t) for t in entries];return {'trials':v,'median':statistics.median(v),'minimum':min(v),'maximum':max(v)}
 normal_data={k:values(normal['trials'],lambda t:t['metrics'][k]) for k in normal['trials'][0]['metrics']}
 normal_data['observed_fps']=values(normal['trials'],lambda t:t['observed_fps'])
 detail_data={k:values(detailed['trials'],lambda t:t['gpu'][k]) for k in detailed['trials'][0]['gpu']}
 detail_data['render_cpu_cycles']=values(detailed['trials'],lambda t:t['phases']['render']['cycles']);detail_data['frame_ids']=[t['metrics']['frame'] for t in detailed['trials']]
 scopes={name:{'cycles':values(detailed['trials'],lambda t:t['detail'][name]['cycles']),'calls':values(detailed['trials'],lambda t:t['detail'][name]['calls'])} for name in detailed['trials'][0]['detail']}
 report['physical'][mode]={'normal':normal_data,'detail':detail_data,'detail_scopes':scopes}
report['hardware_delta']={k:report['hardware']['worker'][k]-report['hardware']['control'][k] for k in ('logic_elements','memory_bits','multipliers_9bit','plls','m9k','physical_memory_bits')}
a=report['physical']['control']['normal']['game_cpu_cycles']['median'];b=report['physical']['worker']['normal']['game_cpu_cycles']['median']
report['ordinary_cpu_change']={'control_cycles':a,'worker_cycles':b,'delta_cycles':b-a,'change_percent':(b/a-1)*100}
probe=json.loads((out/'physical-worker-probe.json').read_text())
report['paired_probe']=[{k:values(probe['trials'],lambda t:t['cases'][i][k]) for k in probe['trials'][0]['cases'][i]} for i in range(10)]
report['scope']='Paired original-kernel/adapter synthetic probe plus three ordinary and detailed standing resets on each hardware. Includes setup/input/output/poll overhead. GPU render/clocks/transport/game assets unchanged. Provisional until exact complete-game stream/GPU replay gates pass.'
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
print('Hardware delta',report['hardware_delta']);print('Ordinary CPU',report['ordinary_cpu_change'])
for mode in report['hardware']:print(mode,'timing',report['hardware'][mode]['setup_min_ns'],report['hardware'][mode]['hold_min_ns'],'transforms',report['physical'][mode]['detail_scopes']['vertex_transform_outcodes']['cycles'])
