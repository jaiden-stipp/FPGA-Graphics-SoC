from pathlib import Path
import subprocess
import hashlib

root = Path.cwd()
out = root / 'docs/benchmarks/static-timing-001'
out.mkdir(parents=True, exist_ok=True)
sof = root / 'build/quartus-integer-mul/IntegerMulSoC.sof'
sof_before = hashlib.sha256(sof.read_bytes()).hexdigest()

tcl = '''package require ::quartus::project
package require ::quartus::sta
project_open IntegerMulSoC
create_timing_netlist -model slow -temperature 85 -voltage 1200
read_sdc
update_timing_netlist
report_timing -setup -npaths 10 -detail full_path -file docs/benchmarks/static-timing-001/setup-full.rpt
foreach {label pattern} {cpu {*|cpu|*} graphics {*|graphics|*} cache {*cached.cache*} loader {*|loader|*}} {
    set regs [get_registers $pattern]
    puts "REGISTER_GROUP $label [get_collection_size $regs]"
    if {[get_collection_size $regs] > 0} {
        report_timing -setup -to $regs -npaths 5 -detail full_path -file docs/benchmarks/static-timing-001/$label-setup.rpt
    }
}
delete_timing_netlist
create_timing_netlist -model fast -temperature 0 -voltage 1200
read_sdc
update_timing_netlist
report_timing -hold -npaths 5 -detail full_path -file docs/benchmarks/static-timing-001/hold-full.rpt
delete_timing_netlist
project_close
'''
(out/'analyze.tcl').write_text(tcl)
temporary = []
try:
    for suffix, content in [('qsf', Path('docs/benchmarks/integer-mul-001/project.qsf').read_bytes()),
                            ('qpf', b'QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "IntegerMulSoC"\n')]:
        dest = root / ('IntegerMulSoC.' + suffix)
        if dest.exists():
            raise RuntimeError(f'Refusing to overwrite {dest}')
        dest.write_bytes(content)
        temporary.append(dest)
    with (out/'timequest.log').open('w') as log:
        result = subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_sta.exe', '-t', str(out/'analyze.tcl')], stdout=log, stderr=subprocess.STDOUT)
    print('TimeQuest exit:', result.returncode)
    sof_after = hashlib.sha256(sof.read_bytes()).hexdigest()
    assert sof_after == sof_before, 'Programmed image artifact changed during analysis'
    (out/'sof-identity.txt').write_text(f'before_sha256={sof_before}\nafter_sha256={sof_after}\n')
    print('SOF unchanged:', sof_after)
    raise SystemExit(result.returncode)
finally:
    for dest in temporary:
        dest.unlink()


