import json,struct,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
root=Path('build/render-fixes');p=root/'replay-depth8'
raw=bytes(int(x,16) for x in (p/'input.hex').read_text().split());i=0;frames={};pal=np.zeros((256,3),dtype=np.uint8);current=0
while i<len(raw):
 if raw[i:i+3]!=b'GF\x02':raise RuntimeError('Bad packet framing')
 op,n=raw[i+3:i+5];data=raw[i+5:i+5+n];i+=n+7
 if op==4:pal[data[0]]=list(data[1:4])
 elif op==1:current=int.from_bytes(data,'big');frames[current]=[]
 elif op==2:frames[current].append(struct.unpack('>9hB',data))
rows=[]
for frame,tris in frames.items():
 color=np.zeros((240,320),dtype=np.uint8);depth=np.zeros((240,320),dtype=np.float64);covered=np.zeros((240,320),dtype=bool);submitted=0
 for tri in tris:
  xyz=np.asarray(tri[:9],dtype=np.int64).reshape((3,3));z=xyz[:,2]
  if np.any(z<257):raise RuntimeError('Oracle fixture requires CPU near clipping')
  reciprocal=16777216//z
  xy=np.column_stack((160+((xyz[:,0]*reciprocal*256)>>24),120-((xyz[:,1]*reciprocal*256)>>24)))
  # GPU screen clipping is not mirrored by this oracle. Select only triangles
  # whose projected vertices are inside, avoiding different clip triangulation.

  a,b,c=xy;area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
  if area<=0:continue # GPU fan_area is opposite of this standard area.
  submitted+=1;lo=np.maximum(xy.min(axis=0),[0,0]);hi=np.minimum(xy.max(axis=0),[319,239]);
  if np.any(lo>hi):continue
  xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1))
  def edge(u,v):return (v[0]-u[0])*(yy-u[1])-(v[1]-u[1])*(xx-u[0])
  e0,e1,e2=edge(b,c),edge(c,a),edge(a,b);inside=(e0>=0)&(e1>=0)&(e2>=0)
  candidate=(e0*(65536.0/z[0])+e1*(65536.0/z[1])+e2*(65536.0/z[2]))/area
  view=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1];dst=color[lo[1]:hi[1]+1,lo[0]:hi[0]+1];mask=inside&(candidate>view+1e-10)
  view[mask]=candidate[mask];dst[mask]=tri[9];covered[lo[1]:hi[1]+1,lo[0]:hi[0]+1]|=inside
 Image.fromarray(pal[color]).save(root/f'oracle-frame-{frame}.png')
 row={'frame':frame,'oracle_scope':'Floating-point reciprocal depth on integer projected coordinates, bounding boxes clamped to viewport; does not reproduce rounded hardware screen-plane intersections or actors','oracle_triangles':submitted,'oracle_covered_pixels':int(covered.sum()),'comparisons':{}}
 for mode in ('depth8','depth12','subpixel'):
  cap=root/('replay-'+mode)/'capture';f=cap/f'frame-{frame}.color.hex'
  if not f.exists():continue
  a=np.array([int(v,16) for v in f.read_text().split()],dtype=np.uint8).reshape(240,320)
  Image.fromarray(pal[a]).save(root/f'{mode}-frame-{frame}.png')
  row['comparisons'][mode]={'disagree_with_scoped_oracle':int(((a!=color)&covered).sum()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 rows.append(row)
(root/'depth-oracle-comparison.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
