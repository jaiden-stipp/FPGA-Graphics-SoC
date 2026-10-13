#!/usr/bin/env python3
"""Lower a declared subset of SM64 display-list C to static fixed-point GPU data.

This is a strict display-list interpreter, not a general C/gameplay transpiler.
Unknown commands, unresolved symbols and cyclic lists fail closed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import scene_assets

ROOT = Path(__file__).resolve().parents[1]
DISCARDABLE_STATE = {
    "gsDPPipeSync", "gsDPSetCycleType", "gsDPSetRenderMode", "gsDPSetDepthSource",
    "gsDPSetFogColor", "gsSPFogPosition", "gsSPSetGeometryMode", "gsSPClearGeometryMode",
    "gsDPSetCombineMode", "gsDPSetTile", "gsSPTexture", "gsDPTileSync", "gsDPSetTileSize",
    "gsDPLoadSync", "gsDPLoadBlock", "gsSPLight", "gsDPSetTextureLOD",
    "gsDPSetTextureFilter", "gsDPSetTexturePersp"
}


def git(source, *args):
    return subprocess.check_output([shutil.which("git") or "git",
        "-c", f"safe.directory={source.resolve().as_posix()}", "-C", str(source), *args], text=True).strip()


def fetch():
    spec = json.loads((ROOT / "sm64.lock.json").read_text())
    dest = ROOT / "external/sm64"
    if not dest.exists():
        subprocess.run(["git", "clone", "--no-checkout", spec["url"], str(dest)], check=True)
        subprocess.run(["git", "-c", f"safe.directory={dest.resolve().as_posix()}",
                        "-C", str(dest), "checkout", "--detach", spec["commit"]], check=True)
    if git(dest, "rev-parse", "HEAD") != spec["commit"] or git(dest, "status", "--porcelain"):
        raise ValueError("SM64 checkout must be clean at sm64.lock.json; refusing to overwrite it")
    return dest


def calls(body, macro_pattern=r'gs\w+'):
    """Split macro calls including nested argument expressions, without eval()."""
    pos = 0
    while pos < len(body):
        whitespace = re.match(r"[\s,]*", body[pos:]).end()
        pos += whitespace
        if pos == len(body):
            return
        match = re.match('('+macro_pattern+r')\s*\(', body[pos:])
        if not match:
            raise ValueError(f"Unsupported C display-list syntax: {body[pos:pos+60]}")
        name = match[1]
        pos += match.end()
        depth, start, args = 1, pos, []
        while pos < len(body) and depth:
            char = body[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if char == "," and depth == 1 or depth == 0:
                value = body[start:pos].strip()
                if value:
                    args.append(value)
                start = pos + 1
            pos += 1
        if depth:
            raise ValueError("Unclosed display-list macro")
        yield name, args


def lower(text, profile, *, face_attributes=None):
    if set(profile["discard_state"]) - DISCARDABLE_STATE:
        raise ValueError("Profile tries to discard a command outside the supported appearance-state subset")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    arrays = {}
    for typ, name, body in re.findall(r"(?:static\s+)?const\s+(Vtx|Gfx)\s+(\w+)\s*\[\]\s*=\s*\{(.*?)\};", text, re.S):
        if name in arrays:
            raise ValueError(f"Duplicate symbol: {name}")
        arrays[name] = (typ, body)
    cache, points, faces, stack, counts, discarded = {}, [], [], [], Counter(), Counter()
    indices, material = {}, ["default"]
    # Actor profiles can lower N64 solid lighting to palette materials without
    # modifying the source model. Terrain profiles retain their existing policy.
    light = [profile.get("initial_light", "default")]
    textured = [False]
    lighting = [True]
    vertex_attributes = {}
    light_colors = profile.get("light_colors", {})

    def number(value):
        if not re.fullmatch(r"-?(?:0[xX][0-9a-fA-F]+|[0-9]+)", value):
            raise ValueError(f"Expected integer literal: {value}")
        return int(value, 16 if "x" in value.lower() else 10)

    def emit(slots):
        face = []
        for slot in slots:
            if slot not in cache:
                raise ValueError(f"Triangle references unloaded vertex slot {slot}")
            point = cache[slot]
            if point not in indices:
                indices[point] = len(points) + 1
                points.append(point)
            face.append(indices[point])
        faces.append((face, material[0] if textured[0] or not light_colors else light[0]))
        if face_attributes is not None:
            face_attributes.append({'rgba':[vertex_attributes[s] for s in slots],
                                    'lighting':lighting[0],'textured':textured[0]})

    def visit(name):
        if name in stack:
            raise ValueError(f"Cyclic display list: {name}")
        if name not in arrays or arrays[name][0] != "Gfx":
            raise ValueError(f"Unresolved display list: {name}")
        stack.append(name)
        ended = False
        for command, args in calls(arrays[name][1]):
            counts[command] += 1
            if command == "gsSPEndDisplayList":
                ended = True
                break
            if command == "gsSPDisplayList":
                visit(args[0])
            elif command == "gsSPBranchList":
                if len(args)!=1:raise ValueError("Display-list branch requires one target")
                # N64 tail call: execute the target and never return to the
                # parent list. Retain the vertex cache and material state.
                visit(args[0]);ended=True;break
            elif command == "gsSPVertex":
                pointer = re.fullmatch(r"(\w+)(?:\s*\+\s*(\d+))?", args[0])
                if not pointer or pointer[1] not in arrays or arrays[pointer[1]][0] != "Vtx":
                    raise ValueError(f"Unsupported/unresolved vertex pointer: {args[0]}")
                coordinates = re.findall(r"\{\{\{\s*([^{}]+)\}", arrays[pointer[1]][1])
                vertices = [tuple(number(v.strip()) for v in coordinate.split(",")) for coordinate in coordinates]
                attributes=[]
                if face_attributes is not None:
                    records=re.findall(r'\{\{\{\s*[^{}]+\}\s*,\s*[^{}]+,\s*\{[^{}]+\}\s*,\s*\{([^{}]+)\}\s*\}\}',arrays[pointer[1]][1])
                    attributes=[[number(v.strip()) for v in record.split(',')] for record in records]
                    if len(attributes)!=len(vertices) or any(len(v)!=4 or any(x< -128 or x>255 for x in v) for v in attributes):
                        raise ValueError('Vertex attribute records must cover every source vertex')
                count, slot = number(args[1]), number(args[2])
                offset = int(pointer[2] or 0)
                if count <= 0 or slot < 0 or slot + count > 32 or offset + count > len(vertices):
                    raise ValueError("Invalid N64 vertex-cache load")
                for i in range(count):
                    if len(vertices[offset+i]) != 3:
                        raise ValueError("Vertex must have XYZ coordinates")
                    cache[slot+i] = vertices[offset+i]
                    if face_attributes is not None:vertex_attributes[slot+i]=[v&255 for v in attributes[offset+i]]
            elif command in {"gsSP1Triangle", "gsSP2Triangles"}:
                expected = 4 if command == "gsSP1Triangle" else 8
                if len(args) != expected:
                    raise ValueError("Invalid triangle macro")
                values = [number(arg) for arg in args]
                for start in range(0, expected, 4):
                    if values[start+3] != 0:
                        raise ValueError("Nonzero triangle flag needs an explicit lowering rule")
                    emit(values[start:start+3])
            elif command == "gsDPSetTextureImage":
                material[0] = args[-1]
                if material[0] not in profile["texture_colors"]:
                    raise ValueError(f"Declare a flat color for texture {material[0]} in the profile")
                discarded[command] += 1
            elif command == "gsDPSetEnvColor" and profile.get("opaque_environment"):
                values = [number(v) for v in args]
                if len(values) != 4 or any(v < 0 or v > 255 for v in values) or (values[3] != 255 and not profile.get('alpha_as_solid')):
                    raise ValueError("Actor environment must be fully opaque")
                discarded[command] += 1
            elif command == 'gsDPLoadTextureBlock' and profile.get('flat_texture_block'):
                material[0]=args[0]
                if material[0] not in profile['texture_colors']:
                    raise ValueError('Declare a flat color for texture '+material[0])
                discarded[command]+=1
            elif command == "gsDPSetAlphaCompare" and profile.get("opaque_environment"):
                if args != ["G_AC_NONE"]:
                    raise ValueError("Alpha testing has no lowering rule in the opaque actor profile")
                discarded[command] += 1
            elif command == "gsSPLight" and light_colors:
                match = re.fullmatch(r"&(\w+)\.(l|a)", args[0])
                if not match or match[1] not in light_colors:
                    raise ValueError(f"Declare a light color for {args[0]}")
                if match[2] == "l":
                    light[0] = match[1]
                discarded[command] += 1
            elif command == "gsSPTexture":
                if args[-1] not in {"G_ON", "G_OFF"}:
                    raise ValueError("Actor texture enable must be G_ON/G_OFF")
                textured[0] = args[-1] == "G_ON"
                discarded[command] += 1
            elif command in ('gsSPSetGeometryMode','gsSPClearGeometryMode'):
                if 'G_LIGHTING' in args[0].split('|') or 'G_LIGHTING' in [v.strip() for v in args[0].split('|')]:
                    lighting[0]=command=='gsSPSetGeometryMode'
                if command not in profile['discard_state']:raise ValueError('Geometry mode needs explicit appearance policy')
                discarded[command]+=1
            elif command in profile["discard_state"]:
                discarded[command] += 1
            else:
                raise ValueError(f"Unsupported command {command}; add a real lowering rule or explicit profile policy")
        if not ended:
            raise ValueError(f"Display list {name} has no end marker")
        stack.pop()

    visit(profile["display_list"])
    if not faces:
        raise ValueError("Display list contains no triangles")
    return points, faces, dict(counts), dict(discarded)


def geometry(source, profile):
    """Resolve declared source files and independent roots into one coordinate space."""
    files = profile.get("sources", [profile.get("source")])
    if not isinstance(files,list) or not files or any(not isinstance(name,str) or not name for name in files) or len(set(files)) != len(files):
        raise ValueError("Declare unique source files")
    texts, hashes = [], {}
    for name in files:
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError("Profile source must be inside the pinned checkout")
        texts.append(path.read_text())
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    text = "\n".join(texts)
    roots = profile.get("roots", [{"name": profile.get("display_list"), "layer": "opaque"}])
    if not isinstance(roots,list) or not roots or any(not isinstance(r,dict) or
            not isinstance(r.get("name"),str) or not r["name"] for r in roots) or len({r.get("name") for r in roots}) != len(roots):
        raise ValueError("Declare unique display-list roots")
    points, faces, indices, reports = [], [], {}, []
    counts, discarded = Counter(), Counter()
    for root in roots:
        if root.get("layer") != "opaque":
            raise ValueError("This world adapter supports opaque roots only; declare other layers as omitted")
        pts, fs, commands, state = lower(text, {**profile, "display_list": root["name"]})
        remap = {}
        for i, p in enumerate(pts, 1):
            if p not in indices:
                indices[p] = len(points)+1
                points.append(p)
            remap[i] = indices[p]
        start = len(faces)
        faces += [([remap[i] for i in face], material) for face, material in fs]
        reports.append({**root, "first_triangle": start, "triangles": len(fs),
                        "commands": commands, "discarded_state": state})
        counts.update(commands); discarded.update(state)
    selection = profile.get("selection_bounds")
    if selection:
        low, high = selection["min"], selection["max"]
        if len(low)!=3 or len(high)!=3 or any(not isinstance(v,(int,float)) for v in low+high) or any(a>=b for a,b in zip(low,high)):
            raise ValueError("Selection needs ordered three-dimensional bounds")
        selected = []
        for root in reports:
            subset = faces[root["first_triangle"]:root["first_triangle"]+root["triangles"]]
            kept = [(f,m) for f,m in subset if all(
                max(points[i-1][a] for i in f)>=low[a] and
                min(points[i-1][a] for i in f)<=high[a] for a in range(3))]
            root["selected_triangles"] = len(kept)
            root["selected_first_triangle"] = len(selected)
            selected.extend(kept)
        faces = selected
        if not faces:
            raise ValueError("Selection contains no original triangles")
    # Compact unused vertices after selection; never clip, retessellate or fill.
    used = sorted({i for face,_ in faces for i in face})
    remap = {old:new for new,old in enumerate(used,1)}
    points = [points[i-1] for i in used]
    faces = [([remap[i] for i in f],m) for f,m in faces]
    return points, faces, dict(counts), dict(discarded), {
        "sources": hashes, "roots": reports, "selection_bounds": selection,
        "selection_policy": "whole triangles whose bounds intersect the declared area" if selection else "all triangles"}


def convert(profile_path, out_dir=None, emit_scene_header=True):
    source = fetch()
    profile = json.loads(profile_path.read_text())
    points, faces, counts, discarded, provenance = geometry(source, profile)
    out = out_dir or ROOT / "build/sm64"
    out.mkdir(parents=True, exist_ok=True)
    obj = out / "scene.obj"
    lines = ["# Extracted static SM64 display-list subset; see conversion.json", "mtllib scene.mtl"]
    lines += ["v " + " ".join(map(str, p)) for p in points]
    for face, material in faces:
        lines += ["usemtl " + material, "f " + " ".join(map(str, face))]
    obj.write_text("\n".join(lines) + "\n")
    (out / "scene.mtl").write_text("\n".join(
        f"newmtl {name}\nKd " + " ".join(map(str, rgb))
        for name, rgb in profile["texture_colors"].items()) + "\n")
    if emit_scene_header:
        if profile.get("extent_q8_8",2048)!=2048:
            raise ValueError("Custom world scale is supported by game assets; use sm64-mario")
        scene_assets.generate(obj)
    target = profile.get("extent_q8_8",2048)
    palette, chunks = scene_assets.convert(obj,extent_q8_8=target)
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    normalization = {"center": [(a+b)/2 for a,b in zip(low,high)],
                     "source_extent": max(b-a for a,b in zip(low,high)), "extent_q8_8": target}
    report = {"profile": profile["name"], "source_commit": git(source, "rev-parse", "HEAD"),
              "source": profile.get("source"), "source_sha256": next(iter(provenance["sources"].values())) if len(provenance["sources"])==1 else None,
              "display_list": profile.get("display_list"), "source_vertices": len(points),
              "triangles": len(faces), "hardware_meshes": len(chunks), "palette_colors": len(palette),
              "commands": counts, "discarded_state": discarded,
              "description": profile["description"], "gameplay_ported": False,
              **provenance, "normalization": normalization,
              "omitted_layers": profile.get("omitted_layers", [])}
    (out / "conversion.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Conversion report: {out.relative_to(ROOT)}/conversion.json (static scene; gameplay not ported)")
    return obj


def inspect(source_path):
    source = fetch()
    path = (source / source_path).resolve()
    if not path.is_relative_to(source.resolve()):
        raise ValueError("Source must be inside the pinned checkout")
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(), flags=re.S)
    for name, body in re.findall(r"(?:static\s+)?const\s+Gfx\s+(\w+)\s*\[\]\s*=\s*\{(.*?)\};", text, re.S):
        commands = Counter(command for command, _ in calls(body))
        unknown = set(commands) - DISCARDABLE_STATE - {"gsDPSetTextureImage", "gsSPEndDisplayList",
                    "gsSPDisplayList", "gsSPVertex", "gsSP1Triangle", "gsSP2Triangles"}
        print(f"{name}: {sum(commands.values())} commands; unsupported: {', '.join(sorted(unknown)) or 'none'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "inspect", "convert"])
    parser.add_argument("--profile", type=Path, default=ROOT / "profiles/sm64-bob-flat.json")
    parser.add_argument("--source", default="levels/bob/areas/1/1/model.inc.c")
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            fetch()
        elif args.command == "inspect":
            inspect(args.source)
        else:
            convert(args.profile)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
