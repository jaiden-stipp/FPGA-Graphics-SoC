"""Deploy guarded audit firmware with verified prior-package rollback."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'build/render-fixes'))
from current_deployment import selection
from measure import restore
from measure_pixel_lanes import timing_gate
from load_game import package_segments
OUT=ROOT/'build/audit-fixes/deployment'
OUT.mkdir(parents=True,exist_ok=True)
NEW=ROOT/'build/mario-castle-audit-fixed-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json'
OLD=ROOT/'build/mario-castle-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json'
spec,sof,package=selection(NEW)
package_segments(OLD)
timing_gate(sof.parent,'ArchStage5SoC')
record={'started_utc':datetime.now(timezone.utc).isoformat(),'hardware':spec['hardware'],'rollback_package':str(OLD),'scope':'Physical deployment and frame-progress verification; not an FPS benchmark'}
try:
    print('Programming accepted Stage 5 image',flush=True)
    with (OUT/'programming.log').open('w',encoding='utf-8') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    print('Uploading guarded Mario package with full readback',flush=True)
    record['running']=restore(package)
    record['result']='success'
except Exception as exc:
    record['error']=repr(exc)
    print('Deployment failed; restoring previous verified package',flush=True)
    try:
        record['rollback_running']=restore(OLD)
        record['result']='failed_previous_package_restored'
    except Exception as rollback_exc:
        record['rollback_error']=repr(rollback_exc)
        record['result']='failed_rollback_failed'
    raise
finally:
    record['finished_utc']=datetime.now(timezone.utc).isoformat()
    (OUT/'boot-check.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,indent=2),flush=True)
