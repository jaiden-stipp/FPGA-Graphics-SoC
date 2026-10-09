#!/usr/bin/env python3
"""Write independent geometry coverage views and compare real GPU PPM captures.

The independent reference uses the declared camera and near plane, followed
by ordinary barycentric depth testing. A second coverage view applies integer
reciprocal projection and integer sample points to classify boundary rounding.
Neither is a bit-exact model of the FPGA's depth interpolation or RTL pipeline.
Only the Python standard library is required.
"""
import json
import math
from pathlib import Path
import scene_assets
import sm64_subset

ROOT=Path(__file__).resolve().parents[1]
WIDTH,HEIGHT=320,240
SKY=(100,170,230)


def clip_near(poly,quantized=False,near_z=128):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        inside_a,inside_b=a[2]>=near_z,b[2]>=near_z
        if inside_a:
            out.append(a)
        if inside_a!=inside_b:
            t=(near_z-a[2])/(b[2]-a[2])
            if quantized:
                tq=math.floor(t*65536)
                out.append(tuple(a[i]+((tq*(b[i]-a[i]))>>16) for i in (0,1))+(near_z,))
            else:
                out.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(3)))
    return out


def render(chunks,palette,position=None,quantized=False,view=None,focal=256,near_z=128):
    if view is None:
        x,y,z=position;target_y=y+64
        ty=-((232*target_y+108*z)>>8)
        tz=1024-((-108*target_y+232*z)>>8)
        view=[256,0,0,-x,0,232,108,ty,0,-108,232,tz]
    pixels=[SKY]*(WIDTH*HEIGHT);depth=[0.]*(WIDTH*HEIGHT)
    for vertices,triangles in chunks:
        camera=[tuple((sum(view[i*4+k]*v[k] for k in range(3))>>8)+view[i*4+3]
                      for i in range(3)) for v in vertices]
        for a,b,c,color in triangles:
            poly=clip_near([camera[i] for i in (a,b,c)],quantized,near_z)
            for j in range(1,len(poly)-1):
                tri=[poly[0],poly[j],poly[j+1]]
                p=[(160+focal*v[0]/v[2],120-focal*v[1]/v[2],1/v[2]) for v in tri]
                if quantized:
                    p=[(160+((v[0]*(65536//v[2])*focal)>>16),
                        120-((v[1]*(65536//v[2])*focal)>>16),1/v[2]) for v in tri]
                def edge(a,b,x,y):
                    return (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
                area=edge(p[0],p[1],p[2][0],p[2][1])
                if area<=0:
                    continue
                lx=max(0,math.floor(min(v[0] for v in p)))
                hx=min(WIDTH-1,math.ceil(max(v[0] for v in p)))
                ly=max(0,math.floor(min(v[1] for v in p)))
                hy=min(HEIGHT-1,math.ceil(max(v[1] for v in p)))
                for py in range(ly,hy+1):
                    for px in range(lx,hx+1):
                        offset=0 if quantized else .5
                        weights=[edge(p[1],p[2],px+offset,py+offset)/area,
                                 edge(p[2],p[0],px+offset,py+offset)/area,
                                 edge(p[0],p[1],px+offset,py+offset)/area]
                        if min(weights)<0:
                            continue
                        inv=sum(w*v[2] for w,v in zip(weights,p));i=py*WIDTH+px
                        if inv>depth[i]:
                            depth[i]=inv;pixels[i]=palette[color]
    return pixels


def ppm(path,pixels):
    path.write_text("P3\n320 240\n255\n"+"\n".join(" ".join(map(str,p)) for p in pixels)+"\n")


def compare(reference,path):
    data=path.read_text().split()
    if data[:4]!=["P3","320","240","255"]:
        raise ValueError("Expected a 320x240 GPU P3 capture")
    values=list(map(int,data[4:]));actual=list(zip(values[::3],values[1::3],values[2::3]))
    if len(actual)!=WIDTH*HEIGHT:
        raise ValueError("Incomplete GPU capture")
    # Ignore a three-pixel band near reference edges, where quantization differs.
    gaps=[]
    for y in range(3,HEIGHT-3):
        for x in range(3,WIDTH-3):
            i=y*WIDTH+x
            if actual[i]==SKY and all(reference[(y+dy)*WIDTH+x+dx]!=SKY
                for dy in range(-3,4) for dx in range(-3,4)):
                gaps.append((x,y))
    return {"capture":str(path.relative_to(ROOT)),"interior_sky_pixels":len(gaps),
            "gap_bounds":([min(x for x,y in gaps),min(y for x,y in gaps),
                           max(x for x,y in gaps),max(y for x,y in gaps)] if gaps else None),
            "reference_scope":"world coverage only; float projection differs from FPGA edge/depth quantization"}


def main():
    report=json.loads((ROOT/"build/game/conversion.json").read_text());n=report["normalization"]
    palette,chunks=scene_assets.convert(ROOT/"build/game/world/scene.obj",extent_q8_8=n["extent_q8_8"])
    out=ROOT/"build/game/diagnostics";out.mkdir(parents=True,exist_ok=True)
    views=[{"name":"spawn","position_q8_8":report["spawn_q8_8"]}]+report["validation_views"]
    comparisons=[]
    for view in views:
        for pose in ("standing","jumping"):
            stem="mario" if view["name"]=="spawn" else "mario-"+view["name"]
            capture=ROOT/"build"/(stem+"-"+pose+".ppm")
            metadata=capture.with_name(capture.name+".json")
            if not capture.exists() or not metadata.exists():continue
            stats=json.loads(metadata.read_text())
            if stats["triangles"]!=report["world_triangles"]+report["actor_triangles"]:continue
            if "camera" in report and "view" not in stats:continue
            kwargs={k:stats[k] for k in ("view","focal","near_z") if k in stats}
            pixels=render(chunks,palette,view["position_q8_8"],**kwargs)
            fixed=render(chunks,palette,view["position_q8_8"],quantized=True,**kwargs)
            name=view["name"]+"-"+pose
            ppm(out/(name+"-reference.ppm"),pixels)
            ppm(out/(name+"-quantized-reference.ppm"),fixed)
            comparisons.append({**compare(pixels,capture),"gpu_stats":stats,
                    "quantized_projection_comparison":{**compare(fixed,capture),
                        "reference_scope":"integer reciprocal projection and pixel sample points; depth remains floating point"}})
    profile=json.loads((ROOT/"profiles/sm64-mario.json").read_text())
    policy=json.loads((ROOT/profile["world_profile"]).read_text())
    vertices,faces,_,_,provenance=sm64_subset.geometry(ROOT/"external/sm64",policy)
    def xy(v):
        return ((v[0]+8192)/16.384,(8192-v[2])/16.384)
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1040">',
         '<rect width="1000" height="1040" fill="white"/>']
    for f,_ in faces:
        points=" ".join(f"{xy(vertices[i-1])[0]:.2f},{xy(vertices[i-1])[1]:.2f}" for i in f)
        svg.append(f'<polygon points="{points}" fill="#a8c777" stroke="#55713c" stroke-width=".5"/>')
    bounds=policy["selection_bounds"]
    x0,y0=xy((bounds["min"][0],0,bounds["max"][2]));x1,y1=xy((bounds["max"][0],0,bounds["min"][2]))
    svg.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="#c73b27" stroke-width="3"/>')
    for label,p in [("spawn",profile["spawn_source"])]+[(v["name"],v["source"]) for v in profile["validation_views"]]:
        x,y=xy(p);svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#c73b27"/><text x="{x+12}" y="{y}" font-size="18">{label}</text>')
    svg.append('<text x="10" y="1025" font-size="17">Source geometry: red bounds define the guaranteed area; whole touching triangles extend beyond it.</text></svg>')
    (out/"source-coverage.svg").write_text("\n".join(svg))
    result={"comparisons":comparisons,"selected_triangles":len(faces),"sources":provenance["sources"]}
    (out/"coverage.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["comparisons"],indent=2))


if __name__=="__main__":
    main()
