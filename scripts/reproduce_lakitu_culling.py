"""Render the same original grounds view with reflected and corrected cameras.

Uses production terrain clipping/commands and actual GPU RTL replay. Terrain,
eye/focus, palette and hardware are identical; only the camera X row changes.
No physical FPGA writes. Native engine fixtures must have been built first.
"""
import ctypes as c,json,os,shutil,subprocess,sys
from test_sm64_engine_slice import Result
from test_sm64_visual_camera import configure
import replay_render_route as replay
import sm64_engine_slice as engine

def main():
    dest=engine.ROOT/'build/camera-controls-fix/replay';dest.mkdir(parents=True,exist_ok=True)
    # Windows keeps loaded DLL files locked throughout simulation. Use a copy
    # so independent engine regression builds can refresh their own DLL.
    library=dest/'engine-reference.dll';shutil.copy2(engine.OUT/'engine.dll',library)
    lib=configure(c.CDLL(str(library)));lib.sm64_engine_probe.restype=c.c_uint32
    lib.sm64_engine_update.argtypes=[c.c_uint32,c.c_uint32,c.POINTER(Result)]
    view=(c.c_int16*12)()
    lib.sm64_engine_init_heading((c.c_int32*3)(-1328,260,4664),32768)
    for tick in range(60):
        r=Result();lib.sm64_engine_update(0,256,c.byref(r));lib.sm64_engine_camera_step(view,4)
        if r.fault:raise RuntimeError('Native camera fault')
    corrected=list(view);before=[-v if i<4 else v for i,v in enumerate(corrected)]
    route={'frames':[{'area':0,'view':before,'label':'reflected-camera','reset':True},
                     {'area':0,'view':corrected,'label':'proper-camera','reset':True}]}
    replay.prepare(engine.OUT/'assets/world.json',route,dest)
    env=os.environ.copy();env['PATH']=str(engine.LLVM)+os.pathsep+env['PATH']
    subprocess.run([sys.executable,str(engine.ROOT/'scripts/replay_render_route.py'),'--capture-only','--out',str(dest),'--simulate','--setup-overlap','--two-pixel-lanes'],cwd=engine.ROOT,env=env,check=True)
    from PIL import Image
    palette=[int(v,16) for v in (dest/'capture/frame-1.palette.hex').read_text().split()]
    results=[]
    for index,label in enumerate(('reflected-camera','proper-camera'),1):
        values=[int(v,16) for v in (dest/f'capture/frame-{index}.color.hex').read_text().split()]
        if len(values)!=76800:raise ValueError('Incomplete framebuffer capture')
        pixels=[tuple((palette[v]>>shift)&255 for shift in (16,8,0)) for v in values]
        picture=Image.new('RGB',(320,240));picture.putdata(pixels);picture.resize((960,720),Image.Resampling.NEAREST).save(dest/(label+'.png'))
        results.append({'label':label,'non_background_pixels':sum(v!=0 for v in values),'view':before if index==1 else corrected})
    (dest/'results.json').write_text(json.dumps({'scope':__doc__,'frames':results},indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
