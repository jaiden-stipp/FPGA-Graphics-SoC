"""Compare clipping of unchanged castle faces at reproducible camera poses."""
import json
import math
import random
from pathlib import Path
from test_screen_edges import ROOT,build_probe,emitted,reference,covers

def main():
    baseline=build_probe(ROOT/'docs/benchmarks/screen-edges-001/before-world.c')
    candidate=build_probe()
    scene=json.loads((ROOT/'build/castle/world.json').read_text())
    probes=[(x,y) for x in (3,8,16,303,311,316) for y in (16,64,120,176,224)]
    probes += [(x,y) for y in (3,8,16,223,231,236) for x in (16,64,128,192,256,304)]
    results=[];count=0
    for area in scene['areas']:
        spawn=area['spawn']
        if isinstance(spawn,dict):spawn=spawn['position']
        positions=[spawn]
        rng=random.Random(183)
        collision=area['collision']
        floors=[t for t in collision['triangles'] if str(t[3]).startswith('floor')]
        if not floors:floors=collision['triangles']
        for t in rng.sample(floors,min(16,len(floors))):
            positions.append([sum(collision['vertices'][t[k]][j] for k in range(3))//3 for j in range(3)])
        for pose in range(len(positions)*8):
            spawn=positions[pose//8];yaw=(pose%8)*45
            co=round(math.cos(math.radians(yaw))*256);si=round(math.sin(math.radians(yaw))*256)
            view=[co,0,si,0,(-98*si)//256,237,(98*co)//256,-463,(237*si)//256,-98,(-237*co)//256,4207]
            points=[tuple((sum((v[j]-spawn[j])*4*view[4*r+j] for j in range(3))//256)+view[4*r+3] for r in range(3)) for v in area['vertices']]
            missing_before=missing_after=0;affected_before=affected_after=0;worst=[]
            for index,face in enumerate(area['triangles']):
                tri=[points[i] for i in face[:3]];expected=reference(tri);count+=1
                if not expected:continue
                wanted=[p for p in probes if covers(expected,*p) and all(covers(expected,p[0]+dx,p[1]+dy) for dx,dy in ((-2,0),(2,0),(0,-2),(0,2)))]
                if not wanted:continue
                before=emitted(baseline,tri);after=emitted(candidate,tri)
                mb=[p for p in wanted if not covers(before,*p)];ma=[p for p in wanted if not covers(after,*p)]
                missing_before+=len(mb);missing_after+=len(ma);affected_before+=bool(mb);affected_after+=bool(ma)
                if mb and len(worst)<3:worst.append({'source_face':index,'camera_triangle':tri,'before_missing':mb,'after_missing':ma})
            row={'area':area['id'],'position':spawn,'view':view,'yaw':yaw,'before_missing_probes':missing_before,'after_missing_probes':missing_after,'before_affected_faces':affected_before,'after_affected_faces':affected_after,'examples':worst}
            results.append(row)
            print(area['id'],yaw,missing_before,missing_after,flush=True)
    report={'source_world':str(Path('build/castle/world.json')),'triangle_pose_tests':count,'poses':len(results),'probe_definition':probes,'reference_margin_pixels':2,'results':results}
    dest=ROOT/'docs/benchmarks/screen-edges-001/castle-coverage.json';dest.write_text(json.dumps(report,indent=2)+'\n')
    print('Totals:',sum(r['before_missing_probes'] for r in results),sum(r['after_missing_probes'] for r in results),flush=True)
    if any(r['after_missing_probes'] for r in results):raise SystemExit('Candidate still loses sampled edge coverage')

if __name__=='__main__':main()
