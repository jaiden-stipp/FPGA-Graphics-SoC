from pathlib import Path
import subprocess,sys,json
root=Path.cwd();out=root/'build/arch-stage2a';py=sys.executable
pgm=Path('C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe')
with (out/'programming.log').open('w') as log:
 subprocess.run([str(pgm),'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;build/quartus-arch-stage2a/ArchStage2ASoC.sof@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
print('Programmed final timing-checked Stage 2A image',flush=True)
restore='build/arch-stage1/baseline/mario-castle-sdram-direct-mul.package.json'
cases=[('legacy-detail','profile-detail'),('batched-detail','profile-detail-batched'),('packed-detail','profile-detail-packed'),('legacy-fine','profile-detail-fine'),('batched-fine','profile-detail-fine-batched'),('packed-fine','profile-detail-fine-packed'),('legacy-normal',None),('packed-normal','packed')]
for name,part in cases:
 stem='build/mario-castle-sdram-direct-'+part+'-mul' if part else 'build/arch-stage1/baseline/mario-castle-sdram-direct-mul'
 args=[py,'scripts/profile_cpu.py',stem+'.package.json','--symbols',stem+'.symbols.json','--restore',restore,'--out',str(out/('physical-'+name+'.json')),'--trials','3','--reuse-immutable-assets']
 if name.endswith('normal'):args+=['--uninstrumented']
 with (out/('physical-'+name+'.log')).open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('Measured '+name,flush=True)
