#!/usr/bin/env python3
"""Reproducible dependency, firmware, simulation and Quartus scaffold tooling."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def run(args, **kwargs):
    display = list(args) if len(args) <= 12 else list(args[:8]) + [f"... ({len(args)-8} more arguments)"]
    print("+", " ".join(str(a) for a in display), flush=True)
    return subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kwargs)


def tool(name):
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Required tool not found on PATH: {name}")
    return found


def write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8", newline="\n")


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise RuntimeError(f"Upstream adaptation anchor changed: {before[:80]!r}")
    return text.replace(before, after, 1)


def bootstrap(args):
    lock = json.loads((ROOT / "upstream.lock.json").read_text())
    for name, spec in lock.items():
        dest = ROOT / "external" / name
        source = getattr(args, f"{name}_source", None)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            run([tool("git"), "clone", "--no-checkout", source or spec["url"], dest])
            run([tool("git"), "-C", dest, "checkout", "--detach", spec["commit"]])
        actual = subprocess.check_output(
            [tool("git"), "-c", f"safe.directory={dest.resolve().as_posix()}", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(
            [tool("git"), "-c", f"safe.directory={dest.resolve().as_posix()}", "-C", str(dest), "status", "--porcelain"], text=True).strip()
        if actual != spec["commit"] or dirty:
            raise RuntimeError(f"{dest} must be clean at {spec['commit']}; refusing to overwrite")
    generate()


def generate():
    cpu_path = ROOT / "external/rv32i/5-Stage-Pipeline"
    cpu = (cpu_path / "RV32I_Pipeline.sv").read_text()
    cpu = replace_once(cpu, "module RV32I_Pipeline(", "module RV32I_SoC(")
    cpu = replace_once(cpu, "    output logic commit_valid\n", """    output logic commit_valid,
    input logic [31:0] soc_instruction, soc_rdata,
    input logic soc_misaligned, soc_write_performed,
    input tri0 soc_stall,
    output logic [31:0] soc_pc, soc_addr, soc_wdata,
    output logic [2:0] soc_funct3,
    output logic soc_read_en, soc_write_en,
    output wire [159:0] cpu_statistics
""")
    start = cpu.index("    UnifiedMem UM (")
    end = cpu.index("    // MEM/WB register", start)
    cpu = cpu[:start] + """    // Generated SoC boundary: preserve the upstream zero-wait MEM timing.
    assign soc_pc = pc;
    assign soc_addr = ALU_result_MEM;
    assign soc_wdata = rs2_MEM;
    assign soc_funct3 = ctrl_MEM.funct3;
    assign soc_write_en = valid_MEM && ctrl_MEM.mem_write && !rst;
    assign soc_read_en = valid_MEM && ctrl_MEM.mem_read && !rst;
    assign Instruction = soc_instruction;
    assign mem_rdata = soc_rdata;
    assign misaligned = soc_misaligned;
    assign mem_write_performed = soc_write_performed;
""" + cpu[end:]
    # Own the wait-state adapters; the pinned CPU source remains unchanged.
    cpu = cpu.replace('    // Stage 1: IF', '    wire soc_advance = !soc_stall;\n    // Stage 1: IF', 1)
    for name in ('PC_IF','IF_ID','ID_EX','EX_MEM','MEM_WB','RegFile'):
        adapted = (cpu_path / (name+'.sv')).read_text()
        adapted = replace_once(adapted, 'module '+name+'(', 'module soc_'+name+'(\n    input logic enable,')
        adapted = replace_once(adapted, 'always_ff @(posedge clk) begin', 'always_ff @(posedge clk) begin\n        if (rst || enable) begin')
        end_at = adapted.rfind('    end')
        adapted = adapted[:end_at] + '        end\n' + adapted[end_at:]
        write(ROOT / ('rtl/generated/soc_'+name+'.sv'), adapted)
        cpu = re.sub(r'\b'+name+r' (\w+) \(\n', r'soc_'+name+r' \1 (\n        .enable(soc_advance),\n', cpu)
    for signal in ('trace_valid','trace_reg_write','trace_mem_read','trace_mem_write','trace_branch','trace_jump','trace_jalr','commit_valid','halt'):
        cpu = replace_once(cpu, 'assign '+signal+' = valid_WB', 'assign '+signal+' = soc_advance && valid_WB')
    assertions = (cpu_path/'verification/PipelineAssertions.sv').read_text()
    assertions = replace_once(assertions, 'module PipelineAssertions (', 'module soc_PipelineAssertions (\n    input logic enable,')
    assertions = replace_once(assertions, '    always @(posedge clk) begin\n        #1;', '    logic sampled_enable;\n    always @(posedge clk) begin\n        sampled_enable = enable;\n        #1;\n        if (rst || sampled_enable) begin')
    end_at = assertions.rfind('    end')
    assertions = assertions[:end_at]+'        end\n'+assertions[end_at:]
    cpu = replace_once(cpu, 'PipelineAssertions assertions (', 'soc_PipelineAssertions assertions (\n        .enable(soc_advance),')
    write(ROOT/'rtl/generated/soc_PipelineAssertions.sv', assertions)
    cpu = cpu.replace('    logic pc_src, stall;', '    logic pc_src, stall;\n    soc_cpu_counters performance (\n        .clk(clk), .reset(rst), .memory_freeze(soc_stall),\n        .retired(trace_valid), .dependency(stall), .redirect(pc_src),\n        .statistics(cpu_statistics)\n    );', 1)
    # Decode the complete M funct7: support MUL only, suppress all other M writes.
    control = (cpu_path / 'ControlUnit.sv').read_text()
    control = replace_once(control, 'module ControlUnit(', 'module soc_ControlUnit(')
    control = replace_once(control, '    input logic funct7b5,', '    input logic [6:0] funct7,')
    control = control.replace('funct7b5 ?', 'funct7[5] ?')
    control = replace_once(control, "                imm_sel = 3'b000;\n                case (funct3)", "                imm_sel = 3'b000;\n                if (funct7 == 7'b0000001) begin\n                    reg_write = (funct3 == 3'b000);\n                    ALU_Sel = 4'b1011;\n                end else case (funct3)")
    write(ROOT/'rtl/generated/soc_ControlUnit.sv',control)
    cpu = replace_once(cpu, '    ControlUnit CU (', '    soc_ControlUnit CU (')
    cpu = replace_once(cpu, '.funct7b5(funct7[5]),', '.funct7(funct7),')
    cpu = replace_once(cpu, '    ALU alu (', '    soc_ALU alu (')
    write(ROOT / "rtl/generated/RV32I_SoC.sv", cpu)
    ram = (cpu_path / "UnifiedMem.sv").read_text()
    ram = replace_once(ram, "module UnifiedMem #(", "module soc_ram #(")
    # Quartus defines ALTERA_RESERVED_QIS, but does not automatically define
    # SYNTHESIS. Select block RAM using its native synthesis macro so the
    # 16,384-word behavioral initialization never enters hardware synthesis.
    ram = replace_once(ram, "`ifdef SYNTHESIS", "`ifdef ALTERA_RESERVED_QIS")
    ram = replace_once(ram, '    parameter DEVICE_FAMILY = "Cyclone IV E"',
                       '    parameter HEX_FILE = "build/firmware.hex",\n'
                       '    parameter DEVICE_FAMILY = "Cyclone IV E"')
    ram = replace_once(ram, "    logic [31:0] mem [0:N-1];", """    logic [31:0] mem [0:N-1];
    initial begin
        for (integer i = 0; i < N; i = i + 1) mem[i] = 0;
        if (HEX_FILE != "") $readmemh(HEX_FILE, mem);
    end""")
    # The behavioral memory now has an initialization process, so use always
    # rather than always_ff for its simulation-only write process.
    ram = replace_once(ram, "    always_ff @(negedge clk) begin", "    always @(negedge clk) begin")
    write(ROOT / "rtl/generated/soc_ram.sv", ram)
    # Upstream palette IP embeds a path relative to its own repository root.
    palette = (ROOT / "external/renderer/rtl/memory/palette_ip.v").read_text()
    palette = replace_once(palette, '"rtl/memory/palette_default.mif"',
                           '"external/renderer/rtl/memory/palette_default.mif"')
    write(ROOT / "rtl/generated/palette_ip.v", palette)
    # Renderer logic uses CPU falling edges, but Intel PLL reference clocks
    # must come directly from the board oscillator, without that inversion.
    renderer_root = ROOT / "external/renderer/rtl"
    stream = (renderer_root / "system/graphics_stream_renderer.sv").read_text()
    stream = replace_once(stream, "    input logic clk,", "    input logic clk,\n    input logic reference_clk,")
    stream = replace_once(stream, "    graphics_renderer_core renderer (\n        .clk(clk),",
                          "    graphics_renderer_core renderer (\n        .clk(clk),\n        .reference_clk(reference_clk),")
    write(ROOT / "rtl/generated/graphics_stream_renderer.sv", stream)
    core = (renderer_root / "system/graphics_renderer_core.sv").read_text()
    core = replace_once(core, "    input logic clk,", "    input logic clk,\n    input logic reference_clk,")
    core = replace_once(core, "    graphics_pipeline pipeline (\n        .CLOCK_50(clk),",
                        "    graphics_pipeline pipeline (\n        .CLOCK_50(clk),\n        .reference_clk(reference_clk),")
    write(ROOT / "rtl/generated/graphics_renderer_core.sv", core)
    pipeline = (renderer_root / "pipeline/graphics_pipeline.sv").read_text()
    pipeline = replace_once(pipeline, "    input  logic        CLOCK_50,",
                            "    input  logic        CLOCK_50,\n    input  logic        reference_clk,")
    pipeline = replace_once(pipeline, ".inclk0(CLOCK_50)", ".inclk0(reference_clk)")
    write(ROOT / "rtl/generated/graphics_pipeline.sv", pipeline)
    # Keep eight extra reciprocal fraction bits for screen positions. The
    # pinned GPU rounds 65536/z before projection, causing visible vertex jumps
    # at distant reciprocal thresholds. Retain its external 8-bit depth ABI.
    transform = (renderer_root / "pipeline/transform_3d_pipeline.sv").read_text()
    for before, after in (
        ('input logic signed [15:0] reciprocal_q8_8', 'input logic signed [31:0] reciprocal_q16_16'),
        ('logic signed [31:0] product;\n        logic signed [47:0] scaled;\n        logic signed [48:0] screen_value;',
         'logic signed [47:0] product;\n        logic signed [63:0] scaled;\n        logic signed [64:0] screen_value;'),
        ('value_q8_8 * reciprocal_q8_8', 'value_q8_8 * reciprocal_q16_16'),
        ('(scaled >>> 16)', '(scaled >>> 24)'),
        ('divider_quotient[15:0]);', 'divider_quotient);'),
    ):
        if transform.count(before) != 2:
            raise RuntimeError(f'Projection adaptation anchor changed: {before!r}')
        transform = transform.replace(before, after)
    transform = replace_once(transform, "divider_numerator = 32'sd65536;", "divider_numerator = 32'sd16777216;")
    transform = replace_once(transform, 'polygon_z[project_index] <= divider_quotient[15:0];',
        'polygon_z[project_index] <= divider_quotient[23:8];')
    # The wider pair of multiplications failed 50 MHz timing as one path.
    # Register each product separately; retain the divider and output handshake.
    start = transform.index('    function automatic logic signed [15:0] project_x(')
    end = transform.index('    function automatic logic signed [15:0] interpolate_value(', start)
    transform = transform[:start] + '''    function automatic logic signed [15:0] project_x(
        input logic signed [63:0] scaled
    );
        logic signed [64:0] screen_value;
        begin
            screen_value = $signed(projection.center_x) + (scaled >>> 24);
            project_x = screen_value[15:0];
        end
    endfunction

    function automatic logic signed [15:0] project_y(
        input logic signed [63:0] scaled
    );
        logic signed [64:0] screen_value;
        begin
            screen_value = $signed(projection.center_y) - (scaled >>> 24);
            project_y = screen_value[15:0];
        end
    endfunction

''' + transform[end:]
    transform = replace_once(transform, '        PROJECT_WAIT,',
        '        PROJECT_WAIT,\n        PROJECT_SCALE,\n        PROJECT_STORE,')
    transform = replace_once(transform, '    logic signed [33:0] fan_area;', '''    logic signed [47:0] project_product_x, project_product_y;
    logic signed [63:0] project_scaled_x, project_scaled_y;
    logic [15:0] project_depth;
    logic signed [33:0] fan_area;''')
    transform = replace_once(transform, "            project_index <= '0;\n            fan_index <= '0;", '''            project_index <= '0;
            project_product_x <= '0; project_product_y <= '0;
            project_scaled_x <= '0; project_scaled_y <= '0;
            project_depth <= '0;
            fan_index <= '0;''')
    start = transform.index('                PROJECT_WAIT: begin')
    end = transform.index('                TRIANGLE_BUILD: begin', start)
    transform = transform[:start] + '''                PROJECT_WAIT: begin
                    if (divider_done) begin
                        project_product_x <= $signed(polygon_x[project_index]) * $signed(divider_quotient);
                        project_product_y <= $signed(polygon_y[project_index]) * $signed(divider_quotient);
                        project_depth <= divider_quotient[23:8];
                        state <= PROJECT_SCALE;
                    end
                end

                PROJECT_SCALE: begin
                    project_scaled_x <= project_product_x * $signed(projection.focal_x);
                    project_scaled_y <= project_product_y * $signed(projection.focal_y);
                    state <= PROJECT_STORE;
                end

                PROJECT_STORE: begin
                    polygon_x[project_index] <= project_x(project_scaled_x);
                    polygon_y[project_index] <= project_y(project_scaled_y);
                    polygon_z[project_index] <= project_depth;
                    project_index <= project_index + 1'b1;
                    state <= PROJECT_START;
                end

''' + transform[end:]
    write(ROOT / "rtl/generated/transform_3d_pipeline.sv", transform)
    # An affine depth inside a triangle lies within its vertex extrema.
    # Truncated gradient steps can violate that invariant at a distant edge,
    # including rounding a valid nonzero depth to zero (background).
    raster = (renderer_root / 'pipeline/renderer.sv').read_text()
    raster = replace_once(raster, '    logic [7:0] active_color;',
        '    logic [7:0] active_color;\n    logic [7:0] minimum_depth, maximum_depth;')
    raster = replace_once(raster, '        depth_f0 =', '''        minimum_depth = v0_depth < v1_depth ? v0_depth : v1_depth;
        minimum_depth = minimum_depth < v2_depth ? minimum_depth : v2_depth;
        maximum_depth = v0_depth > v1_depth ? v0_depth : v1_depth;
        maximum_depth = maximum_depth > v2_depth ? maximum_depth : v2_depth;
        depth_f0 =''')
    raster = replace_once(raster, '''        if (current_depth < 0)
            current_depth_byte = 8'h00;
        else if (current_depth > 36'sd65280)
            current_depth_byte = 8'hff;''', '''        if (current_depth < $signed({1'b0, minimum_depth, 8'b0}))
            current_depth_byte = minimum_depth;
        else if (current_depth > $signed({1'b0, maximum_depth, 8'b0}))
            current_depth_byte = maximum_depth;''')
    write(ROOT / 'rtl/generated/renderer.sv', raster)
    from gpu_fractional import generate as generate_fractional
    generate_fractional(replace_once,write)
    from gpu_setup import generate as generate_setup
    generate_setup(raster, replace_once, write)
    from gpu_pixel_lanes import generate as generate_pixel_lanes
    generate_pixel_lanes(replace_once, write)
    protocol = json.loads((ROOT / "external/renderer/protocol/protocol.json").read_text())
    header = ["// Generated from pinned renderer protocol/protocol.json.",
              "#ifndef GFX_PROTOCOL_H", "#define GFX_PROTOCOL_H",
              f"#define GFX_VERSION {protocol['commandVersion']}u"]
    for i, value in enumerate(protocol["magic"]["command"]):
        header.append(f"#define GFX_MAGIC_{i} {value}u")
    for name, value in protocol["opcodes"].items():
        macro = re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()
        header.append(f"#define GFX_OP_{macro} {value}u")
    header.append("#define GFX_OP_DRAW_MESH_Q8 13u")
    write(ROOT / "firmware/generated/gfx_protocol.h", "\n".join(header + ["#endif", ""]))
    print("Generated CPU boundary, RAM wrapper, palette path and firmware protocol header.")


def firmware(args):
    if not (ROOT / "firmware/generated/gfx_protocol.h").exists():
        raise RuntimeError("Run bootstrap first")
    BUILD.mkdir(exist_ok=True)
    cc = tool(args.cc)
    is_clang = "clang" in Path(cc).name
    prefix = args.cc.removesuffix("gcc") if not is_clang else "llvm-"
    objcopy = tool(args.objcopy or prefix + "objcopy")
    flags = ["-march=rv32i", "-mabi=ilp32", "-msmall-data-limit=0", "-mno-relax",
             "-O1", "-ffreestanding", "-fno-builtin", "-nostdlib", "-Wall", "-Wextra",
             "-Werror", "-Ifirmware/include", "-Ifirmware/generated",
             "-Wl,-T,firmware/link.ld", "-Wl,--no-relax"]
    if is_clang:
        flags = ["--target=riscv32-unknown-elf", "-fuse-ld=lld"] + flags
    apps = ["scene", "game", "triangle", "game-test", "scene-test", "mario", "mario-test", "mario-bridge-test"] if args.app == "all" else [args.app]
    if any(app.startswith("scene") for app in apps) and not (ROOT / "firmware/generated/scene_data.h").exists():
        from sm64_subset import convert
        convert(ROOT / "profiles/sm64-bob-flat.json")
    if any(app.startswith("mario") for app in apps) and not (ROOT / "firmware/generated/game_data.h").exists():
        from game_assets import generate as game_generate
        game_generate(ROOT / "profiles/sm64-mario.json")
    for app in apps:
        use_sdram = getattr(args, 'use_sdram', False)
        stem = getattr(args,'image_name',None) or app + ('-sdram' if use_sdram else '')
        app_flags = [f"-Wl,-Map,build/{stem}.map"]
        app_flags += getattr(args,'extra_flags',[])
        if use_sdram:
            app_flags += ['-DGAME_USE_SDRAM', '-Wl,-T,firmware/link-sdram.ld']
        compile_flags = [f for f in flags if not (use_sdram and f == '-Wl,-T,firmware/link.ld')]
        app_sources = ["firmware/start.S", "firmware/src/gfx.c"]
        if app == 'sdram-test':
            app_sources = ['firmware/start.S','firmware/src/sdram.c','firmware/src/sdram_test.c']
        elif app == "triangle":
            app_sources += ["firmware/src/main.c"]
        elif app.startswith("mario"):
            app_sources += ["firmware/src/gfx_scene.c", "firmware/src/player.c", "firmware/src/camera.c", "firmware/src/animation.c", "firmware/src/game_runtime.c", "firmware/src/mario.c"]
        elif app == 'beacon':
            app_sources += ['firmware/src/gfx_scene.c','firmware/src/player.c','firmware/src/camera.c',
                            'firmware/src/game_runtime.c','firmware/src/beacon.c','firmware/src/beacon_game.c']
        elif app == 'quake':
            app_sources += ['firmware/src/gfx_scene.c','firmware/src/player.c',
                            'firmware/src/game_runtime.c','firmware/src/first_person.c','firmware/src/quake_scene.c']
        elif app == 'portable':
            app_sources += ['firmware/src/gfx_scene.c','firmware/src/player.c','firmware/src/first_person.c',
                            'firmware/src/game_runtime.c','firmware/src/portable_assets.c','firmware/src/portable_main.c','firmware/src/cpu_profile.c']
            app_sources += [str(p) for p in args.port_sources]
        elif app.startswith("scene"):
            app_sources += ["firmware/src/gfx_scene.c", "firmware/src/scene.c"]
        else:
            app_sources += ["firmware/src/gfx_scene.c", "firmware/src/game.c"]
        if app == "game-test":
            app_flags += ["-DGAME_TICK_CYCLES=256u"]
        if app == "scene-test":
            app_flags += ["-DSCENE_TICK_CYCLES=256u"]
        if app == "mario-test":
            app_flags += ["-DPLAYER_TICK_CYCLES=100000u"]
        if app == "mario-bridge-test":
            app_flags += ["-DPLAYER_TICK_CYCLES=100000u", "-DPLAYER_VALIDATION_VIEW=0"]
        if use_sdram and app != 'sdram-test': app_sources += ['firmware/src/sdram.c']
        run([cc] + compile_flags + app_flags + app_sources + ["-o", f"build/{stem}.elf"])
        run([objcopy] + (['--remove-section=.game_assets'] if use_sdram else []) + ["-O", "binary", f"build/{stem}.elf", f"build/{stem}.bin"])
        if use_sdram:
            import hashlib
            run([objcopy,'--only-section=.game_assets','-O','binary',f'build/{stem}.elf',f'build/{stem}.assets.bin'])
            asset_data=(BUILD/f'{stem}.assets.bin').read_bytes()
            asset_data=asset_data.ljust((len(asset_data)+3)//4*4,b'\0')
            write(BUILD/f'{stem}.assets.hex',''.join(f'{int.from_bytes(asset_data[i:i+4],"little"):08x}\n' for i in range(0,len(asset_data),4)))
            segments=[]
            for label,address in [('bin',0),('assets.bin',0x80000000)]:
                path=BUILD/f'{stem}.{label}'; payload=path.read_bytes()
                segments.append({'file':path.name,'address':address,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
            package={'format':'soc-game-package','version':1,'app':app,'segments':segments}
            if '-DSOC_INTEGER_MUL' in app_flags:package['required_cpu_features']={'mul':True,'mmio_feature_bit':0}
            if '-DSOC_GEOMETRY_OFFLOAD' in app_flags:package.setdefault('required_cpu_features',{})['geometry-worker-v1']=True
            if getattr(args,'content',None): package['content']=args.content
            if getattr(args,'target',None): package['target']=args.target
            write(BUILD/f'{stem}.package.json',json.dumps(package,indent=2)+'\n')
        if '-DSOC_INTEGER_MUL' in app_flags:
            # Compiler stays RV32I. Validate every M-family opcode in executable text.
            disassembly=subprocess.check_output([tool('llvm-objdump'),'-d',BUILD/f'{stem}.elf'],text=True)
            encoded=[]
            for line in disassembly.splitlines():
                match=re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]{8})\s',line)
                if match:
                    instruction=int(match[2],16)
                    if instruction&127==0x33 and instruction>>25==1:
                        if (instruction>>12)&7:raise RuntimeError('Unsupported M instruction emitted at '+match[1])
                        encoded.append(int(match[1],16))
            if not encoded:raise RuntimeError('MUL-enabled firmware has no MUL instructions')
            write(BUILD/f'{stem}.isa.json',json.dumps({'compiler_isa':'rv32i','required_feature':'MUL only','mul_addresses':encoded},indent=2)+'\n')
        data = (BUILD / f"{stem}.bin").read_bytes()
        if len(data) > 65536:
            raise RuntimeError("Firmware exceeds RAM")
        data = data.ljust(65536, b"\0")
        words = [int.from_bytes(data[i:i+4], "little") for i in range(0, len(data), 4)]
        write(BUILD / f"{stem}.hex", "".join(f"{w:08x}\n" for w in words))
        write(BUILD / f"{stem}.mif", "WIDTH=32;\nDEPTH=16384;\nADDRESS_RADIX=HEX;\n"
              "DATA_RADIX=HEX;\nCONTENT BEGIN\n" +
              "".join(f"{i:04x} : {w:08x};\n" for i, w in enumerate(words)) + "END;\n")
        print(f"Built {app}: build/{stem}.hex and build/{stem}.mif")
        if app.startswith('mario') or app in ('beacon','quake','portable'):
            symbols=subprocess.check_output([tool(prefix+'nm'),'--defined-only',BUILD/f'{stem}.elf'],text=True)
            addresses={line.split()[-1]:int(line.split()[0],16) for line in symbols.splitlines() if len(line.split())==3}
            write(BUILD/f'{stem}.symbols.json',json.dumps(addresses,indent=2)+'\n')
            macros={'CPU_CYCLES':'game_cpu_cycles'}
            if 'game_frame_cycles' in addresses:macros['FRAME_CYCLES']='game_frame_cycles'
            if 'game_player' in addresses: macros['PLAYER']='game_player'
            if 'demo_state' in addresses: macros['DEMO_STATE']='demo_state'
            if app.startswith('mario'):
                macros.update({'CLIP':'game_animation_clip','ANIMATION_FRAME':'game_animation_frame',
                    'ANIMATION_CYCLES':'game_animation_cycles','UPLOAD_CYCLES':'game_upload_cycles'})
            elif app=='beacon': macros.update({'BEACONS':'game_beacons','FRAME':'game_frame'})
            else: macros.update({'FRAME':'game_frame'})
            label=stem.upper().replace('-','_')
            write(ROOT/f'sim/generated/{stem}_symbols.svh',''.join(
                f"`define {label}_{name}_ADDR 32'h{addresses[symbol]:08x}\n" for name,symbol in macros.items()))
        if app == args.boot:
            for extension in ("elf", "bin", "map", "hex", "mif"):
                shutil.copyfile(BUILD / f"{stem}.{extension}", BUILD / f"firmware.{extension}")
            print(f"Selected {app} as board boot image")
            write(BUILD/'boot.json',json.dumps({'app':stem,'sdram':use_sdram},indent=2)+'\n')


def sources(full=False):
    cpu = ROOT / "external/rv32i/5-Stage-Pipeline"
    files = [cpu / "pipeline_pkg.sv"]
    files += sorted(p for p in cpu.glob("*.sv") if p.name not in {
        "pipeline_pkg.sv", "UnifiedMem.sv", "RV32I_Pipeline.sv",
        "RV32I_Pipeline_tb.sv", "DE2_115_Top.sv"})
    files += [cpu / "verification/PipelineAssertions.sv"]
    files += [ROOT / "rtl/generated/RV32I_SoC.sv", ROOT / "rtl/generated/soc_ram.sv"]
    files += [ROOT / ('rtl/generated/soc_'+name+'.sv') for name in
              ('PC_IF','IF_ID','ID_EX','EX_MEM','MEM_WB','RegFile','PipelineAssertions')]
    files += [ROOT/'rtl/sdram_capture_clock.sv', ROOT/'rtl/sdram_controller.sv', ROOT/'rtl/sdram_bridge.sv', ROOT/'rtl/sdram_cache.sv', ROOT/'rtl/gfx_command_dma.sv',ROOT/'rtl/sdram_command_arbiter.sv', ROOT/'rtl/udp_memory_loader.sv']
    files += [ROOT / "rtl/geometry_worker.sv", ROOT / "rtl/soc_alu.sv", ROOT / "rtl/generated/soc_ControlUnit.sv", ROOT / "rtl/soc_cpu_counters.sv", ROOT / "rtl/soc_mmio.sv", ROOT / "rtl/soc_memory.sv"]
    renderer = ROOT / "external/renderer/rtl"
    files += [renderer / "command/graphics_command_stream_decoder.sv"]
    files += sorted((renderer / "network").glob("*.sv"))
    files += [ROOT / "rtl/udp_controls.sv"]
    if full:
        files += [ROOT / "rtl/generated/palette_ip.v"]
        replaced = {"graphics_stream_renderer.sv", "graphics_renderer_core.sv", "graphics_pipeline.sv", "transform_3d_pipeline.sv", "renderer.sv", "graphics_command_stream_decoder.sv", "graphics_command_processor.sv", "indexed_mesh_store.sv", "vga_controller.sv", "render_performance_counters.sv"}
        files += [ROOT / "rtl/generated" / name for name in sorted(replaced)]
        files += [ROOT / 'rtl/generated' / name for name in ('renderer_serial.sv','triangle_setup_engine.sv','renderer_overlap.sv','renderer_dual.sv','zbuffer_single.sv','framebuffer_single.sv','zbuffer_banked.sv','framebuffer_banked.sv','pixel_bank_ram.sv')]
        for directory in ("common", "command", "system", "pipeline", "memory", "video"):
            files += sorted(p for p in (renderer / directory).iterdir()
                            if p.suffix in {".sv", ".v"} and p.name not in {"palette_ip.v", "graphics_command_stream_decoder.sv"} and p.name not in replaced)
        files += [ROOT / "rtl/soc_top.sv", ROOT / "rtl/boards/de2_115_soc_top.sv"]
    return files


def simulate(args):
    if not getattr(args,'tests',None) and not all((BUILD / name).exists() for name in ("triangle.hex", "game-test.hex", "scene-test.hex", "mario-test.hex")):
        raise RuntimeError("Run build-fw --app all first")
    simulator = args.simulator
    if simulator == "auto":
        simulator = "modelsim" if shutil.which("vsim") else "iverilog"
    if args.full and simulator != "modelsim":
        raise RuntimeError("Full VGA test requires ModelSim with the altera_mf library")
    tests = ["soc_mmio_tb", "soc_memory_tb", "cpu_stream_tb", "game_stream_tb", "udp_controls_tb", "scene_stream_tb", "mario_stream_tb"]
    available = tests + ['geometry_worker_tb','cpu_geometry_tb','gfx_dma_tb','sdram_arbiter_tb','gfx_dma_memory_tb','packed_mmio_tb','sdram_cache_tb','sdram_memory_tb','sdram_cpu_tb','udp_loader_tb','udp_extended_input_tb','soc_cpu_counters_tb','cpu_counter_pipeline_tb','cpu_batch_stream_tb','cpu_mul_tb']
    if args.full:
        tests += ["soc_top_tb", "soc_game_top_tb", "soc_scene_top_tb", "soc_mario_top_tb", "soc_mario_bridge_top_tb"]
        available += ['setup_overlap_tb','pixel_lanes_tb','pixel_banks_tb']
        available += ['sdram_mario_top_tb','beacon_sdram_top_tb','quake_sdram_top_tb','portable_scene_top_tb','quake_interactive_top_tb','castle_world_top_tb','projection_precision_tb','screen_edge_coverage_tb','depth_edge_coverage_tb','render_frame_replay_tb','packed_render_replay_tb','dma_render_replay_tb','gpu_fractional_decoder_tb','gpu_fractional_mesh_tb']
    if getattr(args, "tests", None):
        requested = args.tests.split(",")
        if set(requested) - set(available + tests):
            raise ValueError("Unknown test or full renderer test without --full")
        tests = requested
    if "soc_mario_bridge_top_tb" in tests and not (BUILD/"mario-bridge-test.hex").exists():
        raise RuntimeError("Run sm64-mario or build-fw --app all to generate the bridge fixture")
    include = "+incdir+" + str(ROOT / "rtl/generated") + "+" + str(ROOT / "external/renderer/rtl/common") + "+" + str(ROOT / "sim/generated") + "+" + str(ROOT / "sim")
    src = sources(args.full) + ([ROOT/'sim/sdram_device_model.sv'] if args.full or any('sdram' in name or name in ('udp_loader_tb','gfx_dma_memory_tb') for name in tests) else []) + [ROOT / f"sim/{name}.sv" for name in tests]
    if ('packed_render_replay_tb' in tests or 'dma_render_replay_tb' in tests) and 'render_frame_replay_tb' not in tests:
        src.insert(-1,ROOT/'sim/render_frame_replay_tb.sv')
    if any(name in tests for name in ('portable_scene_top_tb','quake_interactive_top_tb','castle_world_top_tb')) and 'quake_sdram_top_tb' not in tests:
        src.insert(-1,ROOT/'sim/quake_sdram_top_tb.sv')
    BUILD.mkdir(exist_ok=True)
    if simulator == "modelsim":
        lib = getattr(args,'work_dir',None) or BUILD / "simlib"
        lib.parent.mkdir(parents=True,exist_ok=True)
        if not lib.exists():
            run([tool("vlib"), lib])
        run([tool("vlog"), "-work", lib, "-sv", "-mfcu", include] +
            (['+define+SOC_GEOMETRY_WORKER'] if getattr(args,'geometry_worker',False) else []) +
            (['+define+SOC_GPU_TWO_PIXEL_LANES'] if getattr(args,'two_pixel_lanes',False) else []) +
            (['+define+SOC_GPU_SETUP_OVERLAP'] if getattr(args,'setup_overlap',False) else []) +
            (['+define+SOC_DISABLE_COMMAND_DMA'] if getattr(args,'disable_command_dma',False) else []) + src)
        for name in tests:
            try:
                result = run([tool("vsim"), "-c", "-L", "altera_mf", "-lib", lib, name,
                              "-do", "onerror {quit -code 1}; run -all; quit -code 0"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            except subprocess.CalledProcessError as exc:
                write(BUILD / f"{name}.log", exc.stdout or "")
                print(exc.stdout or "")
                raise
            output = result.stdout
            write(BUILD / f"{name}.log", output)
            if "PASS " + name not in output or "** Error:" in output or "** Fatal:" in output:
                print(output)
                raise RuntimeError(f"Simulation failed: {name}")
            print("PASS", name)
    else:
        for name in tests:
            exe = BUILD / f"{name}.vvp"
            run([tool("iverilog"), "-g2012", "-s", name, "-I",
                 ROOT / "external/renderer/rtl/common", "-I", ROOT / "sim/generated", "-I", ROOT / "sim", "-o", exe] + src)
            result = run([tool("vvp"), exe], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
            write(BUILD / f"{name}.log", result.stdout)
            if "PASS " + name not in result.stdout:
                raise RuntimeError(f"Simulation ended without PASS: {result.stdout}")
            print("PASS", name)


def quartus(_args):
    # Generate an independent board project; never import either upstream top.
    lines = ['set_global_assignment -name FAMILY "Cyclone IV E"',
             'set_global_assignment -name DEVICE EP4CE115F29C7',
             'set_global_assignment -name TOP_LEVEL_ENTITY de2_115_soc_top',
             'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
             'set_global_assignment -name FITTER_EFFORT "STANDARD FIT"',
             'set_global_assignment -name SEARCH_PATH rtl/generated',
             'set_global_assignment -name SEARCH_PATH external/renderer/rtl/common',
             'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY build/quartus',
             'set_global_assignment -name SDC_FILE fpga/soc.sdc']
    boot=json.loads((BUILD/'boot.json').read_text()) if (BUILD/'boot.json').exists() else {'sdram':False}
    lines.append(f'set_parameter -name ENABLE_SDRAM {int(boot["sdram"])}')
    lines.append(f'set_parameter -name ENABLE_CACHE {int(not getattr(_args,"disable_cache",False))}')
    lines.append(f'set_parameter -name CACHE_LINE_BYTES {getattr(_args,"cache_line_bytes",32)}')
    lines.append(f'set_parameter -name ENABLE_BURST {int(not getattr(_args,"disable_burst",False))}')
    for path in sources(True):
        # Monitor/assertions are excluded from synthesis by upstream translate_off.
        kind = "VERILOG_FILE" if path.suffix == ".v" else "SYSTEMVERILOG_FILE"
        lines.append(f'set_global_assignment -name {kind} "{path.relative_to(ROOT).as_posix()}"')
    original = (ROOT / "external/renderer/Graphics.qsf").read_text().splitlines()
    # Use only pins for ports that exist in our board wrapper.
    ports = {"CLOCK_50", "KEY[0]", "KEY[1]"} | {f"LEDG[{i}]" for i in range(4)}
    for line in original:
        if line.startswith(("set_location_assignment", "set_instance_assignment")) and " -to " in line:
            target = line.split(" -to ", 1)[1].strip()
            if target in ports or target.startswith("VGA_") or (target.startswith("ENET0_") and target != "ENET0_LINK100"):
                lines.append(line)
    # Reuse the right-button pin verified in the CPU's DE2-115 project.
    cpu_pins = (ROOT / "external/rv32i/RV32I.qsf").read_text().splitlines()
    lines += [line for line in cpu_pins if line.startswith(
        ("set_location_assignment", "set_instance_assignment")) and line.endswith(" -to KEY3")]
    lines += (ROOT/'fpga/de2_115_sdram.qsf').read_text().splitlines()
    write(ROOT / "SoC.qsf", "\n".join(lines) + "\n")
    write(ROOT / "SoC.qpf", 'QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "SoC"\n')
    print("Generated SoC.qpf / SoC.qsf. Run scripts/soc.py build-fpga or compile in Quartus Lite.")


def sm64_scene(args):
    from sm64_subset import convert
    convert(args.profile)
    if "clang" in Path(args.cc).name:
        from rv32i_subset import check
        for name in ("scene.c", "gfx.c", "gfx_scene.c"):
            check(ROOT / "firmware/src" / name, args.cc)
    args.app, args.boot = "all", "scene"
    firmware(args)
    quartus(args)
    if args.sim:
        args.simulator, args.full = "modelsim", True
        simulate(args)
    if args.fpga:
        build_fpga(args)


def sm64_mario(args):
    from game_assets import generate as game_generate
    game_generate(args.profile)
    if "clang" in Path(args.cc).name:
        from rv32i_subset import check
        for name in ("mario.c", "player.c", "camera.c", "animation.c", "gfx.c", "gfx_scene.c", "game_runtime.c"):
            check(ROOT / "firmware/src" / name, args.cc)
    args.app, args.boot = "all", "mario"
    firmware(args)
    quartus(args)
    if args.sim:
        args.simulator, args.full = "modelsim", True
        args.tests = "mario_stream_tb,soc_mario_top_tb,soc_mario_bridge_top_tb"
        simulate(args)
    if args.fpga:
        build_fpga(args)


def sdram_game(args):
    from game_assets import generate as game_generate
    generate()
    game_generate(args.profile)
    from game_package import mario_content
    args.content=mario_content(args.profile,json.loads((BUILD/'game/conversion.json').read_text()))
    if 'clang' in Path(args.cc).name:
        from rv32i_subset import check
        for name in ('mario.c','player.c','camera.c','animation.c','gfx.c','gfx_scene.c','game_runtime.c','sdram.c','sdram_test.c'):
            check(ROOT/'firmware/src'/name,args.cc)
    args.use_sdram=True
    args.app='sdram-test'; args.boot=None
    saved_content=args.content; args.content=None
    firmware(args)
    args.content=saved_content
    args.app='mario'; args.boot='mario'
    firmware(args)
    # The standalone CPU/physical tests cover 100 ms retention. Shorten only
    # that boot delay in the GPU fixture; game tick timing stays at real 30 Hz.
    args.boot=None; args.image_name='mario-sdram-test'
    args.extra_flags=['-DSDRAM_RETENTION_CYCLES=1000u']
    firmware(args)
    args.image_name=None; args.extra_flags=[]
    shutil.copyfile(BUILD/'game/conversion.json',BUILD/'mario-sdram.conversion.json')
    quartus(args)
    if args.fpga: build_fpga(args)


def game_packages(args):
    # Software-only package build: preserve the already verified FPGA project.
    from game_package import generate as authored_generate
    from game_package import mario_content
    from game_assets import generate as mario_generate
    from rv32i_subset import check
    mario_profile=ROOT/'profiles/sm64-mario-sdram.json'
    mario_generate(mario_profile)
    args.content=mario_content(mario_profile,json.loads((BUILD/'game/conversion.json').read_text()))
    args.use_sdram=True; args.app='mario'; args.boot=None
    args.image_name=None; args.extra_flags=[]
    for name in ('mario.c','player.c','camera.c','animation.c','gfx.c','gfx_scene.c','game_runtime.c','sdram.c'):
        if 'clang' in Path(args.cc).name: check(ROOT/'firmware/src'/name,args.cc)
    firmware(args)
    args.image_name='mario-sdram-test'; args.extra_flags=['-DSDRAM_RETENTION_CYCLES=1000u']
    firmware(args)
    module=json.loads(args.profile.read_text()).get('module')
    if module=='quake':
        from quake_assets import generate as quake_generate, fetch_shareware
        pak=args.pak or (fetch_shareware() if args.fetch_quake else BUILD/'quake-shareware/pak0.pak')
        if not pak.exists():raise ValueError('Provide --pak PATH or use --fetch-quake for the original shareware data')
        args.content=quake_generate(args.profile,pak)
        game_sources=('first_person.c','quake_scene.c')
    elif module=='beacon':
        args.content=authored_generate(args.profile);game_sources=('beacon.c','beacon_game.c')
    else:raise ValueError('Unsupported gameplay module')
    for name in game_sources:
        if 'clang' in Path(args.cc).name: check(ROOT/'firmware/src'/name,args.cc)
    args.app=module; args.image_name=None; args.extra_flags=[]
    firmware(args)
    args.image_name=module+'-sdram-test'; args.extra_flags=['-DSDRAM_RETENTION_CYCLES=1000u']
    firmware(args)
    print('Built two interchangeable packages; FPGA boot image and project preserved.')


def portable_package(args):
    from portable_game import generate as generate_portable
    from rv32i_subset import check
    if getattr(args,'terrain_gpu_fractional',False):args.terrain_gpu_safe=True
    if sum(bool(getattr(args,key,False)) for key in ('packed_gfx','batch_gfx','dma_gfx'))>1:raise ValueError('Choose one of --packed-gfx, --batch-gfx, --dma-gfx')
    if not 0<=getattr(args,'terrain_min_chunk_faces',0)<=256:
        raise ValueError('--terrain-min-chunk-faces requires 0..256')
    if getattr(args,'terrain_min_chunk_faces',0) and not (getattr(args,'terrain_tight_chunks',False) or getattr(args,'terrain_gpu_fractional',False)):
        raise ValueError('--terrain-min-chunk-faces requires --terrain-tight-chunks or --terrain-gpu-fractional')
    if getattr(args,'profile_fine',False):args.profile_detail=True;args.cpu_profile=True
    if getattr(args,'terrain_gpu_safe',False) and getattr(args,'terrain_direct',False):
        raise ValueError('--terrain-gpu-safe and --terrain-direct are mutually exclusive')
    if 'clang' not in Path(args.cc).name:
        raise ValueError('Portable game builds require Clang for the mandatory specialized-C audit')
    try:
        spec,args.content,args.target,args.port_sources,api,report=generate_portable(args.project,tight_chunks=getattr(args,'terrain_tight_chunks',False) or getattr(args,'terrain_gpu_fractional',False),min_chunk_faces=getattr(args,'terrain_min_chunk_faces',0))
    except (KeyError,TypeError) as exc:
        raise ValueError('Invalid portable project/scene: '+str(exc)) from exc
    api=set(api)|{'portable_assets','portable_world','portable_camera','portable_meshes'}
    sources=['gfx.c','gfx_scene.c','player.c','first_person.c','game_runtime.c','sdram.c','portable_assets.c','portable_main.c','cpu_profile.c']
    for source in [ROOT/'firmware/src'/name for name in sources]+args.port_sources:
        check(source,args.cc,additional_api=api,extra_flags=(['-DSOC_PROFILE'] if getattr(args,'cpu_profile',False) or getattr(args,'profile_detail',False) else []) + (['-DSOC_PROFILE_DETAIL'] if getattr(args,'profile_detail',False) else []) + (['-DSOC_PROFILE_FINE'] if getattr(args,'profile_fine',False) else []) + (['-DGFX_BATCHED'] if getattr(args,'batch_gfx',False) else []) + (['-DGFX_PACKED'] if getattr(args,'packed_gfx',False) else []) + (['-DGFX_DMA'] if getattr(args,'dma_gfx',False) else []) + (['-DSOC_INTEGER_MUL'] if getattr(args,'integer_mul',False) else []) + (['-DSOC_GEOMETRY_OFFLOAD'] if getattr(args,'geometry_offload',False) else []) + (['-DWORLD_GPU_FRACTIONAL=1'] if getattr(args,'terrain_gpu_fractional',False) else []))
    direct=getattr(args,'terrain_direct',False)
    if direct and 'world_prepare' not in api:
        raise ValueError('--terrain-direct requires a port using the shared world renderer')
    if getattr(args,'terrain_gpu_safe',False) and 'world_prepare' not in api:
        raise ValueError('--terrain-gpu-safe requires the shared world renderer')
    args.app='portable';args.boot=None;args.use_sdram=True
    suffix=('-direct' if direct else '-gpu-q8' if getattr(args,'terrain_gpu_fractional',False) else '-gpu-safe' if getattr(args,'terrain_gpu_safe',False) else '')+('-profile' if getattr(args,'cpu_profile',False) or getattr(args,'profile_detail',False) else '')+('-detail' if getattr(args,'profile_detail',False) else '')+('-fine' if getattr(args,'profile_fine',False) else '')+('-batched' if getattr(args,'batch_gfx',False) else '')+('-packed' if getattr(args,'packed_gfx',False) else '')+('-dma' if getattr(args,'dma_gfx',False) else '')+('-mul' if getattr(args,'integer_mul',False) else '')+('-geometry' if getattr(args,'geometry_offload',False) else '')
    if getattr(args,'terrain_tight_chunks',False):suffix+='-tight'
    if getattr(args,'terrain_min_chunk_faces',0):suffix+='-min'+str(args.terrain_min_chunk_faces)
    args.image_name=spec['name']+'-sdram'+suffix
    diagnostic_flags=['-DWORLD_FORCE_DIRECT=1'] if direct else []
    diagnostic_flags += (['-DSOC_PROFILE'] if getattr(args,'cpu_profile',False) or getattr(args,'profile_detail',False) else []) + (['-DSOC_PROFILE_DETAIL'] if getattr(args,'profile_detail',False) else []) + (['-DGFX_BATCHED'] if getattr(args,'batch_gfx',False) else []) + (['-DGFX_PACKED'] if getattr(args,'packed_gfx',False) else []) + (['-DGFX_DMA'] if getattr(args,'dma_gfx',False) else []) + (['-DSOC_INTEGER_MUL'] if getattr(args,'integer_mul',False) else []) + (['-DSOC_GEOMETRY_OFFLOAD'] if getattr(args,'geometry_offload',False) else [])
    diagnostic_flags += ['-DSOC_PROFILE_FINE'] if getattr(args,'profile_fine',False) else []
    diagnostic_flags += ['-DWORLD_GPU_FRACTIONAL=1'] if getattr(args,'terrain_gpu_fractional',False) else []
    args.extra_flags=diagnostic_flags
    firmware(args)
    from load_game import package_segments
    package_segments(BUILD/(args.image_name+'.package.json'))
    args.image_name=spec['name']+'-sdram'+suffix+'-test'
    args.extra_flags=diagnostic_flags+['-DSDRAM_RETENTION_CYCLES=1000u']
    firmware(args)
    package_segments(BUILD/(args.image_name+'.package.json'))
    if getattr(args,'terrain_gpu_fractional',False):
        for stem in (spec['name']+'-sdram'+suffix,spec['name']+'-sdram'+suffix+'-test'):
            path=BUILD/(stem+'.package.json');package=json.loads(path.read_text())
            package['required_gpu_features']={'draw-mesh-fraction-v1':True,'mmio_address':0x400000a8,'bit':0}
            write(path,json.dumps(package,indent=2)+'\n')
    if getattr(args,'packed_gfx',False):
        for stem in (spec['name']+'-sdram'+suffix,spec['name']+'-sdram'+suffix+'-test'):
            path=BUILD/(stem+'.package.json');package=json.loads(path.read_text())
            package.setdefault('required_gpu_features',{})['packed-enqueue-v1']=True
            write(path,json.dumps(package,indent=2)+'\n')
    if getattr(args,'dma_gfx',False):
        for stem in (spec['name']+'-sdram'+suffix,spec['name']+'-sdram'+suffix+'-test'):
            path=BUILD/(stem+'.package.json');package=json.loads(path.read_text())
            package.setdefault('required_gpu_features',{})['command-dma-v1']=True
            package['command_buffers']={'address':0x87fe0000,'bytes':2048,'buffer_bytes':1024,'count':2}
            write(path,json.dumps(package,indent=2)+'\n')
            package_segments(path)
    if direct:
        for stem in (spec['name']+'-sdram'+suffix,spec['name']+'-sdram'+suffix+'-test'):
            path=BUILD/(stem+'.package.json')
            package=json.loads(path.read_text())
            package['diagnostic']={'terrain_submission':'CPU-clipped direct triangles; GPU resident terrain cache bypassed',
                'purpose':'isolate terrain mesh uploads and cached-versus-direct clipping; not a performance optimization'}
            write(path,json.dumps(package,indent=2)+'\n')
    print(f'Built {spec["name"]}: {report["source_triangles"]} triangles via shared scene IR and direct-call game port ABI. Use a compatible target FPGA image.')


def build_fpga(args):
    """Run native stages directly, avoiding Quartus shell Tcl path normalization."""
    if not (ROOT / "SoC.qpf").exists() or not (BUILD / "firmware.mif").exists():
        raise RuntimeError("Run bootstrap, build-fw and quartus-project first")
    quartus_bin = args.quartus_bin
    if quartus_bin is None and os.environ.get("QUARTUS_ROOTDIR"):
        candidate = Path(os.environ["QUARTUS_ROOTDIR"]) / ("bin64" if os.name == "nt" else "bin")
        if candidate.is_dir():
            quartus_bin = candidate
    for stage in ("map", "fit", "sta", "asm"):
        name = f"quartus_{stage}"
        executable = quartus_bin / (name + (".exe" if os.name == "nt" else "")) if quartus_bin else tool(name)
        log = BUILD / f"quartus-{stage}.log"
        with log.open("w", encoding="utf-8") as output:
            run([executable, "SoC"], stdout=output, stderr=subprocess.STDOUT)
        if stage == "sta":
            import re
            summary = (BUILD / "quartus/SoC.sta.summary").read_text()
            slacks = [float(value) for value in re.findall(r"Slack\s*:\s*([-+\d.]+)", summary)]
            if not slacks or min(slacks) < 0:
                raise RuntimeError("Timing constraints failed; inspect build/quartus/SoC.sta.summary")
        print(f"PASS Quartus {stage}; log: {log.relative_to(ROOT)}")
    print("Programming image: build/quartus/SoC.sof")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("bootstrap")
    p.add_argument("--rv32i-source", type=Path, help="Optional local Git clone")
    p.add_argument("--renderer-source", type=Path, help="Optional local Git clone")
    p.set_defaults(func=bootstrap)
    p = sub.add_parser("build-fw")
    p.add_argument("--app", choices=["all", "scene", "scene-test", "game", "triangle", "game-test", "mario", "mario-test", "mario-bridge-test"], default="all")
    p.add_argument("--boot", choices=["scene", "game", "triangle", "mario"], default="scene")
    p.add_argument("--cc", default="clang")
    p.add_argument("--objcopy")
    p.set_defaults(func=firmware)
    p = sub.add_parser("sim")
    p.add_argument("--simulator", choices=["auto", "modelsim", "iverilog"], default="auto")
    p.add_argument("--full", action="store_true")
    p.add_argument("--tests", help="Comma-separated tests; permits selecting the Mario milestone tests")
    p.add_argument('--work-dir',type=Path,help='Independent ModelSim library for concurrent verification')
    p.add_argument('--geometry-worker',action='store_true',help='Enable optional Stage 5 Q8 geometry worker')
    p.add_argument('--two-pixel-lanes',action='store_true',help='Experimental Stage 4 parity-banked two-pixel raster')
    p.add_argument('--setup-overlap',action='store_true',help='Experimental Stage 3 setup/raster overlap; default retains serial renderer')
    p.add_argument('--disable-command-dma',action='store_true',help='Use accepted direct cache/controller topology without experimental DMA')
    p.set_defaults(func=simulate)
    p = sub.add_parser("quartus-project")
    p.add_argument('--disable-cache',action='store_true',help='Generate an uncached SDRAM baseline project')
    p.add_argument('--cache-line-bytes',type=int,choices=(8,16,32),default=32,help='Cache line size; total capacity stays 4 KiB')
    p.add_argument('--disable-burst',action='store_true',help='Keep the cache but fill lines with independent BL1 reads')
    p.set_defaults(func=quartus)
    p = sub.add_parser("build-fpga")
    p.add_argument("--quartus-bin", type=Path, help="Edition-specific Quartus executable directory")
    p.set_defaults(func=build_fpga)
    p = sub.add_parser("sm64-scene", help="Convert pinned SM64 display-list C, build RV32I images and project")
    p.add_argument("--profile", type=Path, default=ROOT / "profiles/sm64-bob-flat.json")
    p.add_argument("--cc", default="clang")
    p.add_argument("--objcopy")
    p.add_argument("--sim", action="store_true")
    p.add_argument("--fpga", action="store_true")
    p.add_argument("--quartus-bin", type=Path)
    p.set_defaults(func=sm64_scene)
    p = sub.add_parser("sm64-mario", help="Build profile-driven Mario actor, collision, controller and GPU firmware")
    p.add_argument("--profile", type=Path, default=ROOT / "profiles/sm64-mario.json")
    p.add_argument("--cc", default="clang")
    p.add_argument("--objcopy")
    p.add_argument("--sim", action="store_true")
    p.add_argument("--fpga", action="store_true")
    p.add_argument("--quartus-bin", type=Path)
    p.set_defaults(func=sm64_mario)
    p = sub.add_parser('sdram-game', help='Build CPU plus SDRAM assets and a reusable UDP game package')
    p.add_argument('--profile',type=Path,default=ROOT/'profiles/sm64-mario-sdram.json')
    p.add_argument('--cc',default='clang'); p.add_argument('--objcopy')
    p.add_argument('--fpga',action='store_true'); p.add_argument('--quartus-bin',type=Path)
    p.set_defaults(func=sdram_game)
    p = sub.add_parser('game-packages', help='Build Mario and Quake scene packages for the same SDRAM FPGA image')
    p.add_argument('--profile',type=Path,default=ROOT/'profiles/quake-e1m1.json')
    p.add_argument('--pak',type=Path); p.add_argument('--fetch-quake',action='store_true')
    p.add_argument('--cc',default='clang'); p.add_argument('--objcopy')
    p.set_defaults(func=game_packages)
    p = sub.add_parser('portable-game', help='Build any compatible shared-scene project with a default or custom game port')
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--terrain-direct',action='store_true',help='Diagnostic: draw shared-world terrain without resident GPU mesh handles; preserve normal packages')
    p.add_argument('--terrain-gpu-safe',action='store_true',help='Conservative exact-rounding, full-frustum resident terrain with direct fallback')
    p.add_argument('--terrain-gpu-fractional',action='store_true',help='Use optional exact fractional terrain matrix command; needs matching GPU feature')
    p.add_argument('--terrain-tight-chunks',action='store_true',help='Opt in to spatial-cell terrain chunks for a measured packing comparison')
    p.add_argument('--terrain-min-chunk-faces',type=int,default=0,help='Experimental minimum faces before spatial splitting (0..256); requires tight or fractional terrain')
    p.add_argument('--cc',default='clang');p.add_argument('--objcopy')
    p.add_argument('--cpu-profile',action='store_true',help='Require CPU counter ABI and publish atomic completed-frame profiles')
    p.add_argument('--profile-detail',action='store_true',help='Optional per-function cycle/call profiles; implies --cpu-profile')
    p.add_argument('--profile-fine',action='store_true',help='Optional CRC/check/write and clipping fraction/intersection timers; implies --profile-detail')
    p.add_argument('--geometry-offload',action='store_true',help='Optional Stage 5 CPU-fallback transform/outcode worker')
    p.add_argument('--integer-mul',action='store_true',help='Use MUL-only fixed_mul; requires CPU feature bit 0')
    p.add_argument('--batch-gfx',action='store_true',help='Experimental FIFO-space reservation transport; retain byte stream ABI')
    p.add_argument('--dma-gfx',action='store_true',help='Experimental two-buffer SDRAM command DMA; requires command-dma-v1 hardware')
    p.add_argument('--packed-gfx',action='store_true',help='Optional atomic 1..4-byte MMIO transport; requires packed-enqueue-v1 hardware')
    p.set_defaults(func=portable_package)
    args = parser.parse_args()
    try:
        args.func(args)
    except (RuntimeError, ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
