"""Export production C poses for review; these images are CPU references, not VGA captures.

Requires the native Clang test toolchain and Pillow. The existing geometry
reference renderer supplies projection/depth testing, independent of GPU RTL.
"""
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw
from diagnose_game import render
from test_animation import AnimationTests

ROOT=Path(__file__).resolve().parents[1]


def records(text,name):
    match=re.search(r'\b'+re.escape(name)+r'\[.*?\]\s*=\s*\{(.*?)\};',text,re.S)
    if not match:raise ValueError('Missing generated array: '+name)
    return [tuple(map(int,re.findall(r'-?\d+',v))) for v in re.findall(r'\{([^{}]+)\}',match[1])]


def main():
    AnimationTests.setUpClass()
    native=AnimationTests()
    header=(ROOT/'firmware/generated/game_data.h').read_text()
    palette=records(header,'game_palette')
    chunks=[]
    for i in range(16):
        if f'actor_vertices_{i}[]' not in header:break
        chunks.append((len(records(header,f'actor_vertices_{i}')),records(header,f'actor_triangles_{i}')))
    assert sum(n for n,_ in chunks)==native.count
    out=ROOT/'build/game/animation-diagnostics';out.mkdir(parents=True,exist_ok=True)
    cases=[('idle',0,0,1),('walk-start',1,0,1),('walk-stride',1,20,1),('walk-return',1,40,1),
           ('jump-start',2,0,0),('jump-air',2,8,0),('land-start',3,22,1),('land-recover',3,32,1)]
    sheet=Image.new('RGB',(1280,548),(24,30,40));draw=ImageDraw.Draw(sheet)
    draw.text((12,10),'Production fixed-point CPU poses / original source clips / independent reference renderer',fill='white')
    metadata=[]
    for cell,(name,clip,frame,grounded) in enumerate(cases):
        vertices,_=native.pose(clip,frame,grounded);index=0;meshes=[];faces=[]
        for count,triangles in chunks:
            meshes.append((vertices[index:index+count],triangles))
            faces += [tuple(index+v+1 for v in t[:3]) for t in triangles]
            index+=count
        pixels=render(meshes,palette,view=[222,0,128,0,-33,248,57,-64,-124,-66,215,450],focal=400)
        panel=Image.new('RGB',(320,240));panel.putdata(pixels)
        x=(cell%4)*320;y=32+(cell//4)*258
        sheet.paste(panel,(x,y));draw.text((x+8,y+243),f'{name}: source frame {frame}',fill='white')
        # This normalized pose export supersedes actor.obj's static adapter pose
        # for animation review. Vertices/indices remain production GPU uploads.
        (out/(name+'.obj')).write_text('\n'.join(['# Evaluated production C pose']+
            ['v '+' '.join(map(str,v)) for v in vertices]+['f '+' '.join(map(str,f)) for f in faces])+'\n')
        metadata.append({'pose':name,'clip':clip,'source_frame':frame,'grounded':grounded,
                         'bounds':[[min(v[k] for v in vertices) for k in range(3)],
                                   [max(v[k] for v in vertices) for k in range(3)]]})
    sheet.save(out/'poses.png')
    report={'scope':'Production native C poses; independent software render, not hardware output',
            'vertices':native.count,'triangles':len(faces),'poses':metadata}
    (out/'poses.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Animation pose sheet and OBJ exports:',out.relative_to(ROOT))


if __name__=='__main__':main()
