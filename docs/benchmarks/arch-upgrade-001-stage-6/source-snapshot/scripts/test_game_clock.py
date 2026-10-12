"""Native execution of production fixed-tick scheduling, independent of render rate."""
import ctypes as c
import os,shutil,subprocess,unittest
from pathlib import Path
from soc import ROOT
from portable_game import validate_render_cadence

PERIOD=1666667
class Clock(c.Structure):
    _fields_=[('previous',c.c_uint32),('period',c.c_uint32),('ticks',c.c_uint32)]

class ClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'build/arch-stage6/clock-test';out.mkdir(parents=True,exist_ok=True)
        src=out/'clock.c';src.write_text('#include "game_clock.h"\nint due(game_runtime_clock_t*c,uint32_t n){return game_runtime_tick_due(c,n);}\nint advance(game_runtime_clock_t*c,uint32_t n){return game_clock_advance(c,n);}\n')
        dll=out/('clock.dll' if os.name=='nt' else 'clock.so')
        flags=['-shared','-O2','-Ifirmware/include']
        flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/export:due','-Wl,/export:advance'] if os.name=='nt' else ['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,str(src),'-o',str(dll)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(dll))
        for name in ('due','advance'):
            fn=getattr(cls.lib,name);fn.argtypes=[c.POINTER(Clock),c.c_uint32];fn.restype=c.c_int
    def frame(self,clock,now):
        count=0
        if self.lib.due(c.byref(clock),now):
            while True:
                count+=1
                if not self.lib.advance(c.byref(clock),now):break
        return count
    def test_deadline_and_repeat_render(self):
        clock=Clock(0,PERIOD,0)
        for now in (0,1,PERIOD-1):self.assertEqual(self.frame(clock,now),0)
        self.assertEqual(self.frame(clock,PERIOD),1)
        self.assertEqual(self.frame(clock,PERIOD),0)
        self.assertEqual(clock.previous,PERIOD)
    def test_different_render_rates_same_ticks(self):
        for interval in (100000,400000,800000,PERIOD):
            clock=Clock(0,PERIOD,0);ticks=0
            for now in range(0,50_000_000,interval):ticks+=self.frame(clock,now)
            ticks+=self.frame(clock,50_000_000)
            self.assertEqual(ticks,29) # 30*1666667 is 50,000,010, not 50,000,000.
            self.assertEqual(clock.previous,29*PERIOD)
    def test_wraparound(self):
        start=0xfffffff0;clock=Clock(start,PERIOD,0)
        self.assertEqual(self.frame(clock,(start+PERIOD-1)&0xffffffff),0)
        self.assertEqual(self.frame(clock,(start+PERIOD)&0xffffffff),1)
        self.assertEqual(clock.previous,(start+PERIOD)&0xffffffff)
    def test_catchup_cap_preserved(self):
        clock=Clock(0,PERIOD,0)
        self.assertEqual(self.frame(clock,3*PERIOD),3)
        self.assertEqual(self.frame(clock,10*PERIOD),4)
        self.assertEqual(clock.previous,10*PERIOD)
        self.assertEqual(self.frame(clock,10*PERIOD),0)
    def test_uncapped_requires_explicit_repeat_safe_contract(self):
        for port in ({},{'render_repeat_safe':False},{'render_repeat_safe':1},{'render_repeat_safe':'true'}):
            validate_render_cadence({'port':port},False)
            with self.assertRaises(ValueError):validate_render_cadence({'port':port},True)
        validate_render_cadence({'port':{'render_repeat_safe':True}},True)

if __name__=='__main__':unittest.main()
