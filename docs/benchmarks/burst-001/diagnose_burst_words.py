from pathlib import Path
import subprocess,sys,json
sys.path.insert(0,'scripts');from load_game import Loader,STATUS,BEGIN,WRITE,READ,package_segments
pgm='C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe'
def program(path):subprocess.run([pgm,'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+path+'@1'],check=True,stdout=subprocess.DEVNULL)
program('build/quartus-burst/BurstSoC.sof');l=Loader();report={}
try:
 l.operation(BEGIN,retries=40)
 for i in range(0,32,3):l.operation(WRITE,0x80000000+4*i,words=[0xa1230000+j for j in range(i,min(i+3,32))])
 report['reads']=[]
 for i in range(24):
  r=l.operation(READ,0x80000000+4*i,count=1)['words'][0];report['reads'].append({'word':i,'expected':hex(0xa1230000+i),'observed':hex(r)})
 print(json.dumps(report,indent=2),flush=True);Path('build/burst-rejected-stream/word-readback.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
 l.close();program('build/quartus-projection/ProjectionSoC.sof');l=Loader()
 try:l.transfer(package_segments(Path('build/mario-castle-sdram-direct.package.json')))
 finally:l.close()

