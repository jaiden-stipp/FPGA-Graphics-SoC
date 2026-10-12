"""Requery the unchanged accepted fitted netlist; archive constraints and timing."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
from soc import ROOT
from measure_pixel_lanes import timing_gate

OUT=ROOT/'build/arch-stage6/timing'
FIT=ROOT/'build/quartus-arch-stage5-worker'
NAME='ArchStage5SoC'
SHA='e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14'

def audit():
    OUT.mkdir(parents=True,exist_ok=True)
    if hashlib.sha256((FIT/(NAME+'.sof')).read_bytes()).hexdigest()!=SHA:raise RuntimeError('Accepted SOF changed')
    qsf=(ROOT/'build/arch-stage5/worker/project.qsf').read_text()
    # No map/fit/asm: this is the same routed design, not a new implementation.
    files=[ROOT/(NAME+'.qsf'),ROOT/(NAME+'.qpf')]
    if any(p.exists() for p in files):raise RuntimeError('Refusing to overwrite live project')
    for suffix in ('sta.rpt','sta.summary','fit.rpt','fit.summary'):
        shutil.copyfile(FIT/(NAME+'.'+suffix),OUT/('before.'+suffix))
    try:
        files[0].write_text(qsf);files[1].write_text('QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "'+NAME+'"\n')
        with (OUT/'sta.log').open('w') as log:
            subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_sta.exe',NAME],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        timing_gate(FIT,NAME)
    finally:
        for p in files:p.unlink(missing_ok=True)
    for suffix in ('sta.rpt','sta.summary'):
        shutil.copyfile(FIT/(NAME+'.'+suffix),OUT/('after.'+suffix))
    shutil.copyfile(ROOT/'fpga/soc.sdc',OUT/'soc.sdc')
    (OUT/'project.qsf').write_text(qsf)
    report=(FIT/(NAME+'.sta.rpt')).read_text()
    rows=[r.strip() for r in report.splitlines() if re.match(r';\s*Worst-case Slack\s*;',r)]
    if len(rows)!=1:raise RuntimeError('Missing multicorner summary')
    slacks=[float(v.strip()) for v in rows[0].split(';')[2:7]]
    coverage={label:[int(v) for v in re.search(r';\s*Unconstrained '+label+r'\s*;\s*(\d+)\s*;\s*(\d+)\s*;',report).groups()] for label in ('Clocks','Input Ports','Input Port Paths','Output Ports','Output Port Paths')}
    summary={'sof_sha256':SHA,'clock_hz':50000000,'netlist_changed':False,'new_exceptions':False,
        'multicorner_minimum_slack_ns':dict(zip(('setup','hold','recovery','removal','minimum_pulse_width'),slacks)),
        'unconstrained_setup_hold':coverage,'checks_pass':min(slacks)>=0,
        'scope':'Same accepted Stage 5 routed netlist; reanalysis, not a frequency sweep or new fit. External delays are inherited board/device assumptions, not newly measured signal margins.'}
    (OUT/'audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':audit()
