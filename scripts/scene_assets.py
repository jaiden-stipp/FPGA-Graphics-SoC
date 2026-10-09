#!/usr/bin/env python3
"""Convert a small, outward-wound Wavefront OBJ scene into GPU mesh chunks."""
import argparse
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def convert(path, transform=None, palette=None, extent_q8_8=2048):
    if not isinstance(extent_q8_8,int) or not 256<=extent_q8_8<=8192:
        raise ValueError("Normalized extent must be an integer in [256,8192]")
    vertices, faces, materials = [], [], {}
    material = "default"
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        fields = raw.split("#", 1)[0].split()
        if not fields:
            continue
        if fields[0] == "mtllib":
            for name in fields[1:]:
                current = None
                for line in (path.parent / name).read_text().splitlines():
                    m = line.split("#", 1)[0].split()
                    if m and m[0] == "newmtl":
                        current = m[1]
                    elif m and m[0] == "Kd" and current:
                        color = tuple(float(v) for v in m[1:4])
                        if len(color) != 3 or not all(math.isfinite(v) and 0 <= v <= 1 for v in color):
                            raise ValueError("Material Kd must contain three values in [0,1]")
                        materials[current] = color
        elif fields[0] == "usemtl":
            material = fields[1]
        elif fields[0] == "v":
            point = tuple(float(v) for v in fields[1:4])
            if len(point) != 3 or not all(math.isfinite(v) for v in point):
                raise ValueError(f"Invalid vertex on line {number}")
            vertices.append(point)
        elif fields[0] == "f":
            polygon = []
            for item in fields[1:]:
                index = int(item.split("/", 1)[0])
                if index == 0:
                    raise ValueError("OBJ indices start at 1")
                index = index - 1 if index > 0 else len(vertices) + index
                if not 0 <= index < len(vertices):
                    raise ValueError(f"Vertex index out of range on line {number}")
                polygon.append(index)
            if len(polygon) < 3:
                raise ValueError("Faces need at least three vertices")
            if len(polygon) > 3:
                raise ValueError("Export triangulated OBJ faces (triangulate in the modeling tool)")
            faces.append((polygon, material))
    if not faces:
        raise ValueError("Scene has no triangles")
    # Only referenced vertices affect normalization, including arbitrary OBJ units.
    used = {i for face, _ in faces for i in face}
    low = [min(vertices[i][a] for i in used) for a in range(3)]
    high = [max(vertices[i][a] for i in used) for a in range(3)]
    extent = max(high[a] - low[a] for a in range(3))
    if extent == 0:
        raise ValueError("Scene has zero extent")
    points = [tuple(round(q) for q in transform(v)) if transform else
              tuple(round((v[a] - (low[a] + high[a]) / 2) * extent_q8_8 / extent)
                    for a in range(3)) for v in vertices]
    palette = list(palette) if palette is not None else [(100, 170, 230)]
    chunks, local, chunk_vertices, triangles = [], {}, [], []
    for face, name in faces:
        a, b, c = [vertices[i] for i in face]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(n*n for n in normal))
        if length == 0 or len({points[i] for i in face}) < 3:
            raise ValueError("Degenerate triangle, including collapse after Q8.8 conversion")
        qa, qb, qc = [points[i] for i in face]
        qu, qv = [qb[i]-qa[i] for i in range(3)], [qc[i]-qa[i] for i in range(3)]
        if all(n == 0 for n in (qu[1]*qv[2]-qu[2]*qv[1], qu[2]*qv[0]-qu[0]*qv[2], qu[0]*qv[1]-qu[1]*qv[0])):
            raise ValueError("Triangle becomes collinear after Q8.8 conversion")
        light = 0.65 + 0.35 * max(0, (normal[0]*0.3 + normal[1]*0.8 - normal[2]*0.5) / length)
        rgb = tuple(min(255, round(x * light * 255)) for x in materials.get(name, (0.8, 0.75, 0.6)))
        if rgb not in palette:
            palette.append(rgb)
        color = palette.index(rgb)
        if color > 255:
            raise ValueError("Scene exceeds 255 face colors; simplify its materials")
        if len(triangles) == 256 or len(local) + len(set(face) - local.keys()) > 128:
            chunks.append((chunk_vertices, triangles))
            local, chunk_vertices, triangles = {}, [], []
        for i in face:
            if i not in local:
                local[i] = len(chunk_vertices)
                chunk_vertices.append(points[i])
        triangles.append(tuple(local[i] for i in face) + (color,))
    chunks.append((chunk_vertices, triangles))
    if len(chunks) > 16:
        raise ValueError(f"Scene requires {len(chunks)} handles; hardware has 16. Export a smaller area.")
    return palette, chunks


def generate(source=None):
    source = source or ROOT / "build/sm64/scene.obj"
    palette, chunks = convert(source)
    lines = ["// Generated by scripts/scene_assets.py. Geometry is static; the FPGA transforms it.",
             "#ifndef SCENE_DATA_H", "#define SCENE_DATA_H", '#include "assets.h"',
             f"#define SCENE_MESH_COUNT {len(chunks)}u",
             f"#define SCENE_TRIANGLE_COUNT {sum(len(t) for _, t in chunks)}u",
             f"#define SCENE_PALETTE_COUNT {len(palette)}u",
             "static const uint8_t scene_palette[][3] = {" +
             ",".join("{" + ",".join(map(str, rgb)) + "}" for rgb in palette) + "};"]
    for i, (vertices, triangles) in enumerate(chunks):
        for label, values, typ in (("vertices", vertices, "scene_vertex_t"), ("triangles", triangles, "scene_triangle_t")):
            lines.append(f"static const {typ} scene_{label}_{i}[] = {{")
            lines += ["    {" + ",".join(map(str, v)) + "}," for v in values]
            lines.append("};")
    lines.append("static const scene_mesh_t scene_meshes[] = {")
    lines += [f"    {{scene_vertices_{i}, scene_triangles_{i}, {len(v)}, {len(t)}}},"
              for i, (v, t) in enumerate(chunks)]
    lines += ["};", "// Quantized camera rotations avoid runtime floating point on RV32I.",
              "static const int16_t scene_camera[][12] = {"]
    for i in range(32):
        angle = i * 2 * math.pi / 32
        c, s = math.cos(angle), math.sin(angle)
        pc, ps = math.cos(math.radians(25)), math.sin(math.radians(25))
        matrix = (c, 0, -s, 0, ps*s, pc, ps*c, 0, pc*s, -ps, pc*c, 0)
        lines.append("    {" + ",".join(str(round(v*256)) for v in matrix) + "},")
    lines += ["};", "#endif", ""]
    output = ROOT / "firmware/generated/scene_data.h"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    stats = ROOT / "sim/generated/scene_stats.svh"
    stats.parent.mkdir(parents=True, exist_ok=True)
    stats.write_text(f"`define SCENE_EXPECTED_TRIANGLES {sum(len(t) for _,t in chunks)}\n"
                     f"`define SCENE_EXPECTED_MESHES {len(chunks)}\n")
    print(f"Scene: {source.name}; {len(chunks)} meshes, {sum(len(v) for v,_ in chunks)} vertices, "
          f"{sum(len(t) for _,t in chunks)} triangles, {len(palette)} colors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obj", type=Path, help="Triangulated exported scene; default build/sm64/scene.obj")
    args = parser.parse_args()
    try:
        generate(args.obj)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
