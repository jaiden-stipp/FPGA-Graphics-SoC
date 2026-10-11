"""Reject corrupted or incomplete evidence instead of reporting equivalence."""
import json,tempfile,unittest
from pathlib import Path
from compare_render_frames import compare

class ReplayEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.a=Path(self.tmp.name)/'before';self.b=Path(self.tmp.name)/'after'
  for folder in (self.a,self.b):
   (folder/'capture').mkdir(parents=True)
   (folder/'input.json').write_text(json.dumps({'scope':'test','frames':[{'frame':1,'label':'fixture','player':[0,0,0],'view':[1]}]}))
   for suffix,n in [('color.hex',76800),('depth.hex',76800),('palette.hex',256)]:
    (folder/'capture'/('frame-1.'+suffix)).write_text('00\n'*n)
   (folder/'capture/frame-triangles.log').write_text('1 012345\n')
 def test_equal_and_one_pixel_mismatch(self):
  self.assertTrue(compare(self.a,self.b)['exact'])
  p=self.b/'capture/frame-1.depth.hex';p.write_text('01\n'+'00\n'*76799)
  self.assertFalse(compare(self.a,self.b)['exact'])
 def test_identically_truncated_captures_are_not_full_frames(self):
  for folder in (self.a,self.b):(folder/'capture/frame-1.color.hex').write_text('00\n')
  with self.assertRaises(ValueError):compare(self.a,self.b)
 def test_unknown_pixel_and_malformed_trace_rejected(self):
  p=self.b/'capture/frame-1.color.hex';p.write_text('xx\n'+'00\n'*76799)
  with self.assertRaises(ValueError):compare(self.a,self.b)
  p.write_text('00\n'*76800);(self.b/'capture/frame-triangles.log').write_text('truncated\n')
  with self.assertRaises(ValueError):compare(self.a,self.b)

if __name__=='__main__':unittest.main()
