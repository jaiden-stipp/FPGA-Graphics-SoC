"""Independent integer oracle for GW v1; wide Python math, explicit 32-bit wrap."""
import json,random
from pathlib import Path

def signed32(n):
    n &= 0xffffffff
    return n-(1<<32) if n&(1<<31) else n

def reference(vertex,origin,position,view):
    delta=[signed32((vertex[i]+origin[i]-position[i])*4) for i in range(3)]
    q=[signed32((signed32(sum(delta[j]*view[4*i+j] for j in range(3)))//256)+view[4*i+3]) for i in range(3)]
    x,y,z=q
    distances=[z-257,30000-z,x*256+z*160,-x*256+z*160,y*256+z*120,-y*256+z*120]
    return q+[sum((signed32(d)<0)<<i for i,d in enumerate(distances))]

def generate(out=Path('build/arch-stage5')):
    out.mkdir(parents=True,exist_ok=True);rng=random.Random(5012026)
    identity=[256,0,0,0,0,256,0,0,0,0,256,0]
    cases=[]
    for k,n in enumerate([1,127,128,128,128,128,128,128,128,128]):
        view=identity[:] if k<3 else [rng.randint(-32768,32767) for _ in range(12)]
        origin=[0]*3 if k<3 else [rng.randint(-32768,32767) for _ in range(3)]
        position=[0]*3 if k<3 else [rng.randint(-32768,32767) for _ in range(3)]
        vertices=[tuple(rng.randint(-32768,32767) for _ in range(3)) for _ in range(n)]
        if k==2:
            view[11]=1
            vertices[:8]=[(-80,0,128),(80,0,128),(0,-60,128),(0,60,128),(0,0,64),(0,0,7500),(-1,-1,-1),(32767,-32768,32767)]
        cases.append({'view':view,'origin':origin,'position':position,'vertices':vertices,
                      'expected':[reference(v,origin,position,view) for v in vertices]})
    def hexfile(name,words):
        (out/name).write_text(''.join(f'{v&0xffffffff:08x}\n' for v in words))
    hexfile('vector-config.hex',[v for c in cases for v in c['view']+c['position']+c['origin']+[len(c['vertices'])]])
    hexfile('vector-input.hex',[v for c in cases for x,y,z in c['vertices'] for v in [(x&65535)|((y&65535)<<16),z]])
    hexfile('vector-expected.hex',[v for c in cases for q in c['expected'] for v in q])
    (out/'vector.meta').write_text(f"{len(cases)} {sum(len(c['vertices']) for c in cases)}\n")
    (out/'vectors.json').write_text(json.dumps(cases,indent=2)+'\n')
    print('Generated independent geometry vectors:',sum(len(c['vertices']) for c in cases))

if __name__=='__main__':generate()
