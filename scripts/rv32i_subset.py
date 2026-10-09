#!/usr/bin/env python3
"""Check a hand-ported C translation unit against the freestanding RV32I subset.

Clang provides the C parser. Floating-point/64-bit operations, indirect calls,
and unresolved runtime/OS/library helpers fail rather than being silently emulated.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
API = {"gfx_palette", "gfx_identity_view", "gfx_view_matrix", "gfx_projection",
       "gfx_begin_frame", "gfx_end_frame", "gfx_define_mesh", "gfx_vertex",
       "gfx_index", "gfx_draw_mesh", "gfx_draw_matrix", "gfx_command", "gfx_wait_frame",
       "fixed_mul", "player_reset", "player_step", "player_floor", "camera_reset", "camera_step",
       "animation_reset", "animation_step", "animation_pose", "sdram_self_test",
       "game_runtime_upload", "game_runtime_clock_reset", "game_runtime_wait_tick",
       "game_runtime_advance_tick", "game_runtime_input", "game_runtime_present",
       "beacon_reset", "beacon_step", "first_person_reset", "first_person_step",
       "game_port_init", "game_port_update", "game_port_render",
       "game_input_decode","game_movement_keys","game_view_update","game_object_overlap","game_door_step",
       "game_pickup_step","game_animation_frame","game_mesh_frame","game_hud_begin","game_hud_rect","game_hud_number"}


def children(node):
    yield node
    for child in node.get("inner", []):
        yield from children(child)


def check(source, cc="clang", additional_api=()):
    compiler = shutil.which(cc)
    nm = shutil.which("llvm-nm")
    if compiler is None or nm is None or "clang" not in Path(compiler).name:
        raise ValueError("C subset audit requires clang and llvm-nm on PATH")
    source = source.resolve()
    api = API | set(additional_api)
    flags = ["--target=riscv32-unknown-elf", "-march=rv32i", "-mabi=ilp32",
             "-msmall-data-limit=0", "-mno-relax", "-ffreestanding", "-fno-builtin",
             "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "firmware/include"),
             "-I" + str(ROOT / "firmware/generated")]
    result = subprocess.run([compiler, *flags, "-Xclang", "-ast-dump=json", "-fsyntax-only", str(source)],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr)
    ast = json.loads(result.stdout)
    functions = [node for node in children(ast) if node.get("kind") == "FunctionDecl" and
                 any(c.get("kind") == "CompoundStmt" for c in node.get("inner", []))]
    defined = {node["name"] for node in functions}
    errors = set()
    # Analyze function bodies, not unused typedefs/system declarations from stdint.h.
    for function in functions:
        for node in children(function):
            typ = node.get("type", {})
            spelling = typ.get("desugaredQualType", typ.get("qualType", ""))
            if re.search(r"\b(float|double|long long)\b", spelling) and "*" not in spelling:
                errors.add(f"{function['name']}: unsupported numeric type {spelling}")
            if node.get("kind") == "CallExpr":
                callee = node.get("inner", [{}])[0]
                references = [item.get("referencedDecl", {}) for item in children(callee)
                              if item.get("kind") == "DeclRefExpr"]
                names = [item.get("name") for item in references if item.get("kind") == "FunctionDecl"]
                if len(names) != 1:
                    errors.add(f"{function['name']}: indirect function call is outside the first subset")
                elif names[0] not in defined | api:
                    errors.add(f"{function['name']}: unsupported external call {names[0]}")
    # Check global initializers as well as bodies.
    for node in children(ast):
        if node.get("kind") == "FloatingLiteral":
            errors.add("Floating-point constant is outside the fixed-point subset")
    if errors:
        raise ValueError("\n".join(sorted(errors)))
    out = ROOT / "build/subset"
    out.mkdir(parents=True, exist_ok=True)
    obj = out / (source.stem + ".o")
    subprocess.run([compiler, *flags, "-c", str(source), "-o", str(obj)], check=True)
    symbols = subprocess.check_output([nm, "-u", str(obj)], text=True)
    unresolved = {line.split()[-1] for line in symbols.splitlines() if line.strip()}
    unsupported = unresolved - api
    if unsupported:
        raise ValueError("Unsupported compiler/runtime symbols: " + ", ".join(sorted(unsupported)))
    report = {"source": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "target": "rv32i/ilp32", "functions": sorted(defined), "external_api": sorted(unresolved),
              "numeric_policy": "integer/fixed-point, at most 32-bit operations",
              "runtime_policy": "static storage/stack, direct calls, no OS/heap or implicit compiler arithmetic helpers"}
    (out / (source.stem + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS RV32I C subset: {source.name}; report build/subset/{source.stem}.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    try:
        check(args.source, args.cc)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
