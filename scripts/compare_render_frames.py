"""Exact color/depth and controller comparison for deterministic render replays."""
import argparse,hashlib,json
from pathlib import Path

def compare(before,after):
 a=json.loads((before/'input.json').read_text());b=json.loads((after/'input.json').read_text())
 if len(a['frames'])!=len(b['frames']):raise ValueError('Frame counts differ')
 rows=[]
 for x,y in zip(a['frames'],b['frames']):
  if x['frame']!=y['frame'] or x.get('player')!=y.get('player') or x.get('view')!=y.get('view'):raise ValueError('Mismatched replay/controller state')
  row={'frame':x['frame'],'label':x['label']}
  for suffix in ('color.hex','depth.hex','palette.hex'):
   name=f"frame-{x['frame']}.{suffix}";ap=before/'capture'/name;bp=after/'capture'/name
   av=ap.read_text().split();bv=bp.read_text().split()
   expected=256 if suffix=='palette.hex' else 76800
   if len(av)!=expected or len(bv)!=expected or any('x' in v.lower() or 'z' in v.lower() for v in av+bv):raise ValueError('Incomplete/unknown capture '+name)
   row[suffix]={'samples':len(av),'differences':sum(int(i,16)!=int(j,16) for i,j in zip(av,bv)),
    'before_sha256':hashlib.sha256(ap.read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(bp.read_bytes()).hexdigest()}
  rows.append(row)
 def triangle_records(folder):
  rows=[]
  for line in (folder/'capture/frame-triangles.log').read_text().splitlines():
   values=line.split()
   if len(values)!=2:raise ValueError('Malformed triangle trace')
   rows.append((int(values[0]),int(values[1],16)))
  return rows
 ta,tb=triangle_records(before),triangle_records(after)
 return {'submitted_triangles_equal':ta==tb,'before_triangles':len(ta),'after_triangles':len(tb),'scope':a['scope'],'before':str(before),'after':str(after),'frames':rows,'exact':ta==tb and all(v['differences']==0 for r in rows for k,v in r.items() if isinstance(v,dict))}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('before',type=Path);p.add_argument('after',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=compare(a.before,a.after);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n');print('Exact full-frame match:',r['exact']);raise SystemExit(0 if r['exact'] else 1)
if __name__=='__main__':main()
