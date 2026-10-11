from pathlib import Path
import subprocess,re
out=Path('build/arch-stage2a');out.mkdir(parents=True,exist_ok=True)
name='ArchStage2ASoC';fit='build/quartus-arch-stage2a'
q=Path('build/screen-edges/project.qsf').read_text().replace('build/quartus-screen-edges',fit)
for folder,file in [('command','graphics_command_stream_decoder.sv'),('command','graphics_command_processor.sv'),('pipeline','indexed_mesh_store.sv')]:
 q=q.replace('external/renderer/rtl/'+folder+'/'+file,'rtl/generated/'+file)
q='set_global_assignment -name SEARCH_PATH rtl/generated\n'+q
created=[]
try:
 for suffix,contents in [('qsf',q),('qpf','QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "'+name+'"\n')]:
  p=Path(name+'.'+suffix)
  if p.exists():raise RuntimeError('Refusing overwrite '+str(p))
  p.write_text(contents);created.append(p)
 (out/'project.qsf').write_text(q)
 qt=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
 for stage in ('map','fit','sta','asm'):
  with (out/('quartus-'+stage+'.log')).open('w') as log:
   result=subprocess.run([str(qt/('quartus_'+stage+'.exe')),name],stdout=log,stderr=subprocess.STDOUT)
  print(stage,result.returncode,flush=True)
  if result.returncode:raise SystemExit(result.returncode)
  if stage=='sta':
   slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',Path(fit+'/'+name+'.sta.summary').read_text())]
   if not slacks or min(slacks)<0:raise SystemExit('Timing failed; do not program')
   print('minimum slack',min(slacks),flush=True)
finally:
 for p in created:p.unlink()
