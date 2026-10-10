package require ::quartus::project
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
