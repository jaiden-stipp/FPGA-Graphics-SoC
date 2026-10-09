#!/usr/bin/env python3
"""Build a profile-driven world, static or animated actor, and collision data.

Source display lists remain untouched. The adapters normalize geometry to the
existing Q8.8 GPU interface. A different game can supply another world/actor
profile and reuse the integer controller and firmware-facing asset schema.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import scene_assets
import sm64_subset

ROOT = Path(__file__).resolve().parents[1]
CAMERA_FIELDS=("distance","min_distance","target_height","follow_shift","vertical_shift","air_shift",
    "lookahead_ticks","lookahead_limit","look_shift","clearance","recovery_step","max_vertical_lag",
    "snap_distance","focal","near_z")


def camera_settings(profile):
    values={"pitch_degrees":30,"distance":960,"min_distance":384,
            "target_height":profile["physics"]["height"]*5//8,
            "follow_shift":2,"vertical_shift":3,"air_shift":4,"lookahead_ticks":4,
            "lookahead_limit":48,"look_shift":2,"clearance":16,"recovery_step":8,
            "max_vertical_lag":128,"snap_distance":256,"focal":256,"near_z":128}
    specified=profile.get("camera",{})
    if set(specified)-set(values):
        raise ValueError("Unknown camera configuration field")
    values.update(specified)
    if any(not isinstance(v,int) or isinstance(v,bool) for v in values.values()):
        raise ValueError("Camera settings must be integers")
    limits={"pitch_degrees":(15,60),"distance":(256,2048),"min_distance":(128,values["distance"]),
            "target_height":(0,profile["physics"]["height"]),"follow_shift":(0,5),
            "vertical_shift":(0,5),"air_shift":(0,6),"lookahead_ticks":(0,8),
            "lookahead_limit":(0,128),"look_shift":(0,5),"clearance":(4,64),
            "recovery_step":(1,32),"max_vertical_lag":(0,256),"snap_distance":(128,1024),
            "focal":(128,512),"near_z":(16,min(128,values["min_distance"]//2))}
    if any(not low<=values[k]<=high for k,(low,high) in limits.items()):
        raise ValueError("Camera configuration exceeds the bounded fixed-point limits")
    # A vertical fallback keeps the actor beyond the near plane when its back
    # is against a tall wall. It fits the same four-preset runtime interface.
    angles=sorted({min(90,values["pitch_degrees"]+15*i) for i in range(3)}|{90})
    values["pitch_angles"]=angles
    values["pitches"]=[[round(math.cos(math.radians(a))*256),round(math.sin(math.radians(a))*256)] for a in angles]
    return values


def camera_surfaces(chunks):
    surfaces=[]
    for vertices,triangles in chunks:
        for a,b,c,_ in triangles:
            pts=[vertices[i] for i in (a,b,c)]
            u,v=[pts[1][i]-pts[0][i] for i in range(3)],[pts[2][i]-pts[0][i] for i in range(3)]
            n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            length=math.sqrt(sum(x*x for x in n))
            normal=[round(x*4096/length) for x in n]
            bounds=[x for i in range(3) for x in (min(p[i] for p in pts),max(p[i] for p in pts))]
            surfaces.append((pts,(*normal,*bounds,max(range(3),key=lambda i:abs(n[i])))))
    return surfaces


def write_obj(path, points, faces, colors):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("mtllib " + path.with_suffix(".mtl").name + "\n" +
                    "\n".join("v " + " ".join(map(str, p)) for p in points) + "\n" +
                    "\n".join("usemtl " + name + "\nf " + " ".join(map(str, f)) for f, name in faces) + "\n")
    path.with_suffix(".mtl").write_text("\n".join("newmtl " + name + "\nKd " +
        " ".join(map(str, rgb)) for name, rgb in colors.items()) + "\n")


def collision(chunks):
    floors, walls = [], []
    for vertices, triangles in chunks:
        for a, b, c, _ in triangles:
            p = [vertices[i] for i in (a, b, c)]
            u, v = [p[1][i]-p[0][i] for i in range(3)], [p[2][i]-p[0][i] for i in range(3)]
            n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(x*x for x in n))
            bounds = [(min(q[i] for q in p), max(q[i] for q in p)) for i in range(3)]
            if n[1] >= 0.5*length:  # Walkable outward faces, slopes at most 60 degrees.
                slopes = [round(-n[i]*4096/n[1]) for i in (0, 2)]
                floors.append((p, (*bounds[0], *bounds[2], *slopes)))
            else:
                normal = tuple(round(x*4096/length) for x in n)
                axis = max(range(3), key=lambda i: abs(n[i]))
                walls.append((p, (*normal, *bounds[0], *bounds[1], *bounds[2], axis)))
    if not floors:
        raise ValueError("World has no outward-wound walkable surfaces")
    return floors, walls


def floor_height(floors, x, z, ceiling):
    """Same bounded floor-plane convention as the integer runtime."""
    heights=[]
    for pts,rest in floors:
        min_x,max_x,min_z,max_z,sx,sz=rest
        if not (min_x<=x<=max_x and min_z<=z<=max_z):
            continue
        edges=[(b[0]-a[0])*(z-a[2])-(b[2]-a[2])*(x-a[0])
               for a,b in zip(pts,pts[1:]+pts[:1])]
        if not (min(edges)>=0 or max(edges)<=0):
            continue
        y=pts[0][1]+((sx*(x-pts[0][0])+sz*(z-pts[0][2]))>>12)
        if y<=ceiling:
            heights.append(y)
    return max(heights,default=-32768)


def generate(profile_path):
    profile = json.loads(profile_path.read_text())
    # SM64-specific import is confined to this asset adapter, not the runtime.
    world_obj = sm64_subset.convert(ROOT / profile["world_profile"],
                    out_dir=ROOT/"build/game/world",emit_scene_header=False)
    world_report=json.loads(world_obj.with_name("conversion.json").read_text())
    normalization=world_report["normalization"]
    palette, world = scene_assets.convert(world_obj,extent_q8_8=normalization["extent_q8_8"])
    source = sm64_subset.fetch()
    actor = profile["actor"]
    path = (source / actor["source"]).resolve()
    if not path.is_relative_to(source.resolve()):
        raise ValueError("Actor source must be inside the pinned checkout")
    text = path.read_text()
    points, faces, part_reports = [], [], []
    local_points,animation_parts=[],[]
    # Proper rigid transforms only: preserve each source vertex and triangle.
    for part in actor["parts"]:
        policy = {**actor, "display_list": part["display_list"], "initial_light": part["light"]}
        pts, fs, commands, discarded = sm64_subset.lower(text, policy)
        local_points.extend(pts);animation_parts.append((part,pts))
        matrix, translation = part["rotation"], part["translation"]
        if len(matrix) != 9 or len(translation) != 3:
            raise ValueError("Pose needs a 3x3 rotation and three translation values")
        rows = [matrix[i:i+3] for i in (0, 3, 6)]
        if any(sum(rows[i][k]*rows[j][k] for k in range(3)) != (1 if i==j else 0)
               for i in range(3) for j in range(3)):
            raise ValueError("Pose rotation must be orthonormal")
        det = (matrix[0]*(matrix[4]*matrix[8]-matrix[5]*matrix[7]) -
               matrix[1]*(matrix[3]*matrix[8]-matrix[5]*matrix[6]) +
               matrix[2]*(matrix[3]*matrix[7]-matrix[4]*matrix[6]))
        if det != 1:
            raise ValueError("Pose cannot mirror geometry or reverse its winding")
        offset = len(points)
        for p in pts:
            q = [sum(rows[i][k]*p[k] for k in range(3))+translation[i] for i in range(3)]
            points.append((q[2], q[0], q[1]))  # SM64 bone X-up -> world Y-up (proper rotation).
        faces += [([i+offset for i in f], material) for f, material in fs]
        part_reports.append({"display_list": part["display_list"], "triangles": len(fs),
                             "commands": commands, "appearance_state": discarded})
    colors = {**actor["light_colors"], **actor["texture_colors"]}
    obj = ROOT / "build/game/actor.obj"
    write_obj(obj, points, faces, colors)
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    height = profile["physics"]["height"]
    scale = height/(high[1]-low[1])
    center = [(high[i]+low[i])/2 for i in range(3)]
    def transform(p):
        return ((p[0]-center[0])*scale, (p[1]-low[1])*scale, (p[2]-center[2])*scale)
    palette, actor_chunks = scene_assets.convert(obj, transform=transform, palette=palette)
    animation_lines=[];animation_report=None
    if 'animation' in profile:
        from animation_assets import prepare
        actor_chunks,animation_lines,animation_report=prepare(source,{**profile['animation'],'height':height},
            animation_parts,local_points,faces,actor_chunks)
    if len(world)+len(actor_chunks)>16:
        raise ValueError("World and actor exceed the existing 16 mesh handles")
    floors, walls = collision(world)
    camera_cfg=camera_settings(profile)
    camera_faces=camera_surfaces(world)
    def source_point(point):
        if len(point)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in point):
            raise ValueError("Source-space points need three finite coordinates")
        return [round((v-normalization["center"][i])*normalization["extent_q8_8"]/
                      normalization["source_extent"]) for i,v in enumerate(point)]
    cfg = profile["physics"]
    if not (0 < cfg["speed"] <= cfg["radius"]//2 and 2 <= cfg["radius"] and
            2*cfg["radius"] <= cfg["height"] <= 1024 and
            0 < cfg["gravity"] <= cfg["jump_speed"] <= min(64,2*cfg["radius"]) and
            0 <= cfg["step_height"] <= cfg["radius"] and -30000 <= cfg["kill_y"] < -1024):
        raise ValueError("Controller needs speed <= radius/2, positive gravity and a bounded capsule")
    # Choose an interior point of the largest reasonably level floor by default.
    if "spawn_source" in profile:
        spawn=source_point(profile["spawn_source"])
    elif "spawn" in profile:
        spawn = profile["spawn"]
    else:
        candidates = [f for f in floors if max(abs(x) for x in f[1][-2:]) <= 2048]
        floor = max(candidates or floors, key=lambda f: abs(
            (f[0][1][0]-f[0][0][0])*(f[0][2][2]-f[0][0][2]) -
            (f[0][1][2]-f[0][0][2])*(f[0][2][0]-f[0][0][0])))
        spawn = [round(sum(p[i] for p in floor[0])/3) for i in range(3)]
        spawn[1] = floor[0][0][1] + ((floor[1][-2]*(spawn[0]-floor[0][0][0]) +
                    floor[1][-1]*(spawn[2]-floor[0][0][2])) >> 12)
    if len(spawn)!=3 or not all(isinstance(v,int) and -4096<v<4096 for v in spawn):
        raise ValueError("Spawn must fit the runtime world bounds")
    ground=floor_height(floors,spawn[0],spawn[2],spawn[1]+2)
    if abs(ground-spawn[1])>2:
        raise ValueError("Declared spawn is not on a displayed floor")
    spawn[1]=ground
    # A spawn must have floor support around the complete capsule footprint.
    r=cfg["radius"]
    if any(abs(floor_height(floors,spawn[0]+dx,spawn[2]+dz,ground+cfg["step_height"])-ground)>
           cfg["step_height"] for dx,dz in ((r,0),(-r,0),(0,r),(0,-r))):
        raise ValueError("Spawn is too close to a floor edge or steep step")
    views=[]
    for view in profile.get("validation_views",[]):
        point=source_point(view["source"])
        point[1]=floor_height(floors,point[0],point[2],point[1])
        if point[1]==-32768:
            raise ValueError("Validation view needs a displayed floor")
        views.append({"name":view["name"],"position_q8_8":point})
    all_chunks = world + actor_chunks
    lines = ["// Generated game asset ABI; source models remain unchanged.", "#ifndef GAME_DATA_H",
             "#define GAME_DATA_H", '#include "assets.h"', '#include "player.h"', '#include "camera.h"',
             f"#define GAME_WORLD_MESHES {len(world)}u", f"#define GAME_MESH_COUNT {len(all_chunks)}u",
             f"#define GAME_TRIANGLE_COUNT {sum(len(t) for _,t in all_chunks)}u",
             f"#define GAME_PALETTE_COUNT {len(palette)}u",
             "static const uint8_t game_palette[][3] = {" +
             ",".join("{"+",".join(map(str,rgb))+"}" for rgb in palette) + "};"]
    for name,chunks in (("world",world),("actor",actor_chunks)):
        for i, (vertices, triangles) in enumerate(chunks):
            for label, values, typ in (("vertices",vertices,"scene_vertex_t"),("triangles",triangles,"scene_triangle_t")):
                lines += [f"static const {typ} {name}_{label}_{i}[] = {{"]
                lines += ["{"+",".join(map(str,v))+"}," for v in values]
                lines += ["};"]
        lines += [f"static const scene_mesh_t {name}_meshes[] = {{"]
        lines += [f"{{{name}_vertices_{i},{name}_triangles_{i},{len(v)},{len(t)}}},"
                  for i,(v,t) in enumerate(chunks)]
        lines += ["};"]
    lines += animation_lines
    for label, data, typ in (("floors",floors,"collision_floor_t"),("walls",walls,"collision_wall_t"),
                             ("camera_surfaces",camera_faces,"collision_wall_t")):
        lines += [f"static const {typ} game_{label}[] = {{"]
        for pts, rest in data:
            lines += ["{"+",".join("{"+",".join(map(str,p))+"}" for p in pts)+","+",".join(map(str,rest))+"},"]
        if not data:
            lines += ["{0},"]
        lines += ["};"]
    settings = [*spawn] + [cfg[k] for k in ("speed","radius","height","step_height","gravity","jump_speed","kill_y")]
    lines += ["static const player_world_t game_world = {game_floors,game_walls," +
              f"{len(floors)},{len(walls)}," + ",".join(map(str,settings))+"};",
              "static const int16_t game_facing[][12] = {"]
    for i in range(32):
        c,s = math.cos(i*math.tau/32),math.sin(i*math.tau/32)
        lines += ["{"+",".join(str(round(v*256)) for v in (c,0,s,0,0,1,0,0,-s,0,c,0))+"},"]
    pitch_values=camera_cfg["pitches"]+[[0,0]]*(4-len(camera_cfg["pitches"]))
    lines += ["};", "static const camera_config_t game_camera_config={"+
        ",".join(map(str,[camera_cfg[k] for k in CAMERA_FIELDS]+[len(camera_cfg["pitches"])]))+",{"+
        ",".join("{"+",".join(map(str,p))+"}" for p in pitch_values)+"}};",
        f"static const camera_world_t game_camera_world={{game_camera_surfaces,{len(camera_faces)}}};"]
    lines += ["static const int16_t game_validation_positions[][3]={"+
              ",".join("{"+",".join(map(str,v["position_q8_8"]))+"}" for v in
                       (views or [{"position_q8_8":spawn}]))+"};"]
    lines += ["#endif", ""]
    storage = ['#ifdef GAME_USE_SDRAM',
               '#define GAME_STORAGE __attribute__((section(".game_assets")))',
               '#else', '#define GAME_STORAGE', '#endif']
    lines[3:3] = storage
    (ROOT / "firmware/generated/game_data.h").write_text("\n".join(lines).replace('static const ', 'static const GAME_STORAGE '))
    (ROOT / "sim/generated/game_stats.svh").write_text(
        f"`define MARIO_EXPECTED_TRIANGLES {sum(len(t) for _,t in all_chunks)}\n"
        f"`define MARIO_EXPECTED_MESHES {len(all_chunks)}\n"
        f"`define MARIO_WORLD_MESHES {len(world)}\n")
    with (ROOT/"sim/generated/game_stats.svh").open("a") as stats:
        stats.write(f"`define MARIO_CAMERA_FOCAL {camera_cfg['focal']}\n`define MARIO_CAMERA_NEAR {camera_cfg['near_z']}\n")
        if animation_report:
            stats.write('`define MARIO_ANIMATED 1\n'+f'`define MARIO_ACTOR_VERTICES {len(animation_report["vertex_sources"])}\n')
    report = {"profile":profile["name"], "source_commit":sm64_subset.git(source,"rev-parse","HEAD"),
              "actor_source":actor["source"], "actor_sha256":hashlib.sha256(text.encode()).hexdigest(),
              "pose":("original skeletal hierarchy and indexed clips" if animation_report else
                      "declared rigid standing pose; original animations not imported"),
              "parts":part_reports, "world_triangles":sum(len(t) for _,t in world),
              "actor_triangles":len(faces), "meshes":len(all_chunks), "palette_colors":len(palette),
              "collision_floors":len(floors), "collision_walls":len(walls), "spawn_q8_8":spawn,
              "world_import":world_report, "normalization":normalization, "validation_views":views,
              "physics":cfg, "camera":camera_cfg, "camera_surfaces":len(camera_faces), "original_gameplay_ported":False}
    if animation_report:report['animation']=animation_report
    (ROOT / "build/game/conversion.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Game: {len(all_chunks)} meshes, {len(faces)} actor triangles; {len(floors)} floors/{len(walls)} walls; spawn {spawn}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile",type=Path,default=ROOT/"profiles/sm64-mario.json")
    args=p.parse_args()
    try:
        generate(args.profile)
    except (ValueError,OSError) as e:
        p.exit(1,f"ERROR: {e}\n")
