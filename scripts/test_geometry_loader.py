import unittest
from load_game import require_hardware,STATUS

class GeometryCapabilityTests(unittest.TestCase):
    class Loader:
        retries=1
        def __init__(self,features):self.features=features;self.operations=[]
        def operation(self,op,**kwargs):self.operations.append(op);return {'cpu_features':self.features,'gpu_features':3}
    def test_reject_before_loading(self):
        l=self.Loader(0x80000001)
        with self.assertRaises(RuntimeError):require_hardware(l,{'required_cpu_features':{'mul':True,'geometry-worker-v1':True}})
        self.assertEqual(l.operations,[STATUS])
    def test_new_and_old_packages(self):
        for features in (0x80000001,0x80000003):
            require_hardware(self.Loader(features),{'required_cpu_features':{'mul':True},'required_gpu_features':{'packed-enqueue-v1':True}})
        require_hardware(self.Loader(0x80000003),{'required_cpu_features':{'geometry-worker-v1':True}})

if __name__=='__main__':unittest.main()
