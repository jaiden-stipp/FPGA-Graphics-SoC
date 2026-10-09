"""Exercise the production integer controller on collision fixtures and imported terrain."""
import ctypes as c
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
import game_assets
import scene_assets

ROOT=Path(__file__).resolve().parents[1]

class Point(c.Structure):
    _fields_=[(k,c.c_int16) for k in ("x","y","z")]
class Floor(c.Structure):
    _fields_=[(k,Point) for k in ("a","b","c")]+[(k,c.c_int16) for k in
                ("min_x","max_x","min_z","max_z","slope_x","slope_z")]
class Wall(c.Structure):
    _fields_=[(k,Point) for k in ("a","b","c")]+[(k,c.c_int16) for k in
        ("nx","ny","nz","min_x","max_x","min_y","max_y","min_z","max_z")]+[("axis",c.c_uint16)]
class World(c.Structure):
    _fields_=[("floors",c.POINTER(Floor)),("walls",c.POINTER(Wall)),
        ("floor_count",c.c_uint32),("wall_count",c.c_uint32)]+[(k,c.c_int32) for k in
        ("spawn_x","spawn_y","spawn_z","speed","radius","height","step_height","gravity","jump_speed","kill_y")]
class Player(c.Structure):
    _fields_=[(k,c.c_int32) for k in ("x","y","z","velocity_y")]+[(k,c.c_uint32) for k in
        ("grounded","facing","previous_keys","respawns")]


@lru_cache(maxsize=1)
def load_controller():
    out=ROOT/"build/player-tests"
    out.mkdir(parents=True,exist_ok=True)
    cc=shutil.which("clang")
    if not cc:
        raise RuntimeError("Production controller tests require Clang")
    dll=out/("player.dll" if os.name=="nt" else "player.so")
    flags=["-shared","-O1","-Wall","-Wextra","-Werror","-I"+str(ROOT/"firmware/include")]
    if os.name=="nt":
        flags += ["-fuse-ld=lld","-nostdlib","-Wl,/noentry"] + ["-Wl,/export:"+s for s in
                   ("player_step","player_reset","player_floor","fixed_mul")]
    else:
        flags += ["-fPIC"]
    subprocess.run([cc,*flags,str(ROOT/"firmware/src/player.c"),"-o",str(dll)],check=True)
    lib=c.CDLL(str(dll))
    lib.player_reset.argtypes=[c.POINTER(Player),c.POINTER(World)]
    lib.player_step.argtypes=[c.POINTER(Player),c.POINTER(World),c.c_uint32]
    lib.player_floor.argtypes=[c.POINTER(World),c.c_int32,c.c_int32,c.c_int32]
    lib.player_floor.restype=c.c_int32
    lib.fixed_mul.argtypes=[c.c_int32,c.c_int32]
    lib.fixed_mul.restype=c.c_int32
    return lib


def world_for(chunks,spawn=(0,0,0)):
    floors,walls=game_assets.collision(chunks)
    fa=(Floor*len(floors))(*(Floor(*(Point(*p) for p in pts),*rest) for pts,rest in floors))
    wa=(Wall*len(walls))(*(Wall(*(Point(*p) for p in pts),*rest) for pts,rest in walls))
    world=World(fa,wa,len(fa),len(wa),*spawn,8,18,128,12,3,30,-1536)
    world.references=(fa,wa)
    return world


def fixture(extra=None,slope=False):
    # Outward-wound floor; optional independently wound wall/ceiling fixtures.
    vertices=[(-1000,-250 if slope else 0,-1000),(-1000,-250 if slope else 0,1000),
              (1000,250 if slope else 0,1000),(1000,250 if slope else 0,-1000)]
    triangles=[(0,1,2,1),(0,2,3,1)]
    if extra=="wall":
        vertices += [(80,-100,-1000),(80,300,-1000),(80,300,1000),(80,-100,1000)]
        triangles += [(4,5,6,1),(4,6,7,1)]
    if extra=="ceiling":
        vertices += [(-1000,220,-1000),(1000,220,-1000),(1000,220,1000),(-1000,220,1000)]
        triangles += [(4,5,6,1),(4,6,7,1)]
    return world_for([(vertices,triangles)])


class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=load_controller()

    def start(self,world):
        p=Player()
        self.lib.player_reset(c.byref(p),c.byref(world))
        return p

    def step(self,p,w,keys=0,count=1):
        for _ in range(count):
            self.lib.player_step(c.byref(p),c.byref(w),keys)

    def test_move_turn_diagonal_and_opposite_keys(self):
        w=fixture(); p=self.start(w)
        self.step(p,w,2,10)
        self.assertEqual((p.x,p.y,p.z,p.facing,p.grounded),(80,0,0,8,1))
        self.step(p,w,3,5)
        self.assertEqual(p.x,80)
        self.step(p,w,6)
        self.assertEqual((p.x,p.z,p.facing),(85,5,4))

    def test_jump_lands_and_held_key_does_not_auto_repeat(self):
        w=fixture(); p=self.start(w)
        self.step(p,w,16)
        self.assertEqual((p.y,p.grounded),(30,0))
        high=0
        for _ in range(50):
            self.step(p,w,16); high=max(high,p.y)
        self.assertEqual(high,165)
        self.assertEqual((p.y,p.grounded,p.velocity_y),(0,1,0))
        self.step(p,w,0); self.step(p,w,16)
        self.assertEqual(p.y,30)

    def test_air_movement_and_landing_on_sloped_floor(self):
        w=fixture(slope=True); p=self.start(w)
        self.step(p,w,2,10)
        self.assertEqual((p.x,p.y,p.grounded),(80,20,1))
        self.step(p,w,18)
        self.step(p,w,2,30)
        self.assertEqual(p.grounded,1)
        self.assertEqual(p.y,p.x//4)

    def test_wall_blocks_and_slides_without_tunneling(self):
        w=fixture("wall"); p=self.start(w)
        self.step(p,w,2,100)
        self.assertTrue(56<=p.x<=63)
        x=p.x
        self.step(p,w,6,20)
        self.assertLess(p.x,64); self.assertGreaterEqual(p.x,x)
        self.assertEqual(p.z,100)
        self.step(p,w,18,10)
        self.assertLess(p.x,64)

    def test_ceiling_stops_upward_movement_then_lands(self):
        w=fixture("ceiling"); p=self.start(w)
        max_y=0
        for _ in range(50):
            self.step(p,w,16); max_y=max(max_y,p.y)
        self.assertLessEqual(max_y,92)
        self.assertGreater(max_y,0)
        self.assertEqual((p.y,p.grounded),(0,1))

    def test_walk_off_edge_fall_and_respawn(self):
        w=fixture(); p=self.start(w)
        self.step(p,w,2,126)
        self.assertEqual(p.grounded,0)
        self.step(p,w,0,50)
        self.assertEqual((p.x,p.y,p.z,p.grounded,p.respawns),(0,0,0,1,1))
        self.step(p,w,15,20)
        self.assertEqual(p.respawns,2)

    def test_real_world_spawn_movement_jump_and_reset(self):
        report=json.loads((ROOT/"build/game/conversion.json").read_text())
        _,chunks=scene_assets.convert(ROOT/"build/game/world/scene.obj",
            extent_q8_8=report["normalization"]["extent_q8_8"])
        w=world_for(chunks,report["spawn_q8_8"]); p=self.start(w)
        self.step(p,w,0,30)
        self.assertEqual((p.x,p.y,p.z),tuple(report["spawn_q8_8"]))
        x=p.x
        self.step(p,w,1,5)
        self.assertLess(p.x,x)
        y=p.y
        self.step(p,w,16)
        self.assertGreater(p.y,y); self.assertEqual(p.grounded,0)
        self.step(p,w,0,50)
        self.assertEqual(p.grounded,1)
        self.step(p,w,15)
        self.assertEqual((p.x,p.y,p.z),tuple(report["spawn_q8_8"]))

    def test_integer_products(self):
        for a,b in ((-2048,2048),(4096,-2000),(7,181),(0,-32),(-12,-320),(2147483647,1)):
            self.assertEqual(self.lib.fixed_mul(a,b),a*b)

    def test_imported_field_to_bridge_route_and_jump(self):
        report=json.loads((ROOT/"build/game/conversion.json").read_text())
        n=report["normalization"]
        _,chunks=scene_assets.convert(ROOT/"build/game/world/scene.obj",extent_q8_8=n["extent_q8_8"])
        w=world_for(chunks,report["spawn_q8_8"]); p=self.start(w)
        # Start field -> approach -> the original sloping wooden bridge -> exit.
        route=[(-6558,7000),(-2000,7000),(-2000,5632),(-1100,5632),(1200,5632)]
        for x,z in route:
            for axis,value,index,negative,positive in (("x",x,0,1,2),("z",z,2,8,4)):
                goal=round((value-n["center"][index])*n["extent_q8_8"]/n["source_extent"])
                for _ in range(500):
                    if abs(getattr(p,axis)-goal)<=w.speed:
                        break
                    self.step(p,w,positive if getattr(p,axis)<goal else negative)
                    self.assertEqual(p.respawns,0)
                    self.assertEqual(p.grounded,1)
                self.assertLessEqual(abs(getattr(p,axis)-goal),w.speed, (axis,value,p.x,p.y,p.z))
            y=p.y
            self.step(p,w,16)
            self.assertGreater(p.y,y)
            self.step(p,w,0,50)
            self.assertEqual((p.grounded,p.y,p.respawns),(1,y,0))
        self.assertGreater(p.y,report["spawn_q8_8"][1]+150)
        self.step(p,w,15)
        self.assertEqual((p.x,p.y,p.z),tuple(report["spawn_q8_8"]))

    def test_declared_spawn_and_capture_positions_have_stable_support(self):
        report=json.loads((ROOT/"build/game/conversion.json").read_text())
        _,chunks=scene_assets.convert(ROOT/"build/game/world/scene.obj",
                                     extent_q8_8=report["normalization"]["extent_q8_8"])
        for position in [report["spawn_q8_8"]]+[v["position_q8_8"] for v in report["validation_views"]]:
            w=world_for(chunks,position);p=self.start(w)
            self.step(p,w,0,60)
            self.assertEqual((p.x,p.y,p.z),tuple(position))
            self.assertEqual((p.grounded,p.respawns),(1,0))

    def test_game_asset_build_does_not_emit_viewer_assets(self):
        viewer=(ROOT/"firmware/generated/scene_data.h").read_bytes()
        # Exercise the profile that produced the current generated package.
        # This test also runs against the full SDRAM level.
        report=json.loads((ROOT/"build/game/conversion.json").read_text())
        profiles=list((ROOT/'profiles').glob('sm64-mario*.json'))
        profile=next(p for p in profiles if json.loads(p.read_text())['name']==report['profile'])
        game=(ROOT/"firmware/generated/game_data.h").read_bytes()
        with patch.object(scene_assets,"generate",side_effect=AssertionError("Viewer generator called")):
            game_assets.generate(profile)
        self.assertEqual((ROOT/"firmware/generated/scene_data.h").read_bytes(),viewer)
        self.assertEqual((ROOT/"firmware/generated/game_data.h").read_bytes(),game)


if __name__=="__main__":
    unittest.main(verbosity=2)
