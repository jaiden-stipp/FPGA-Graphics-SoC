"""Supplementary stationary Mario samples; never claim traversing-game FPS."""
import argparse,json,time
from pathlib import Path
from load_game import Loader,BEGIN,READ,COMMIT,STATUS
ROOT=Path(__file__).resolve().parents[1]
def sample(label,size):
 symbols=json.loads((ROOT/'build/mario-castle-sdram-direct.symbols.json').read_text())
 l=Loader();report={'label':label,'line_bytes':size,'scope':'Unscripted standing spawn view; only comparable if player coordinates remain identical. Not traversal FPS. Published frame counters and stage globals may refer to different frames.','windows':[]}
 held=False
 try:
  time.sleep(3)
  for trial in range(3):
   records=[]
   for i in range(12):
    s=l.operation(STATUS);assert s['initialized'] and not s['held'] and 0<s['scratch']<0x10000000
    records.append({'t':time.monotonic(),'frame':s['scratch']})
    if i<11:time.sleep(.25)
   l.operation(BEGIN);held=True
   position=list(l.operation(READ,symbols['game_player'],count=3)['words'])
   metrics={name:l.operation(READ,symbols[name],count=1)['words'][0] for name in ('game_cpu_cycles','game_update_cycles','game_present_cycles','game_frame_cycles','castle_prepare_cycles','castle_draw_cycles','castle_pose_upload_cycles')}
   elapsed=records[-1]['t']-records[0]['t'];frames=(records[-1]['frame']-records[0]['frame'])&0xffffffff
   report['windows'].append({'trial':trial+1,'records':records,'frames':frames,'elapsed_s':elapsed,'observed_fps':frames/elapsed,'position_u32':position,'metrics':metrics})
   l.operation(COMMIT);held=False;time.sleep(3)
  report['restored_status']=l.operation(STATUS)
 finally:
  if held:l.operation(COMMIT)
  l.close();(ROOT/'build/cache-lines'/f'{label}-game.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);p.add_argument('--size',type=int,choices=(8,16,32),required=True);a=p.parse_args();sample(a.label,a.size)
