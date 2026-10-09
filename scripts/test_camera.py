"""Execute the production fixed-point camera on independent collision fixtures."""
import ctypes as c
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import game_assets
import scene_assets
from test_player import Player,Point,Wall,world_for,fixture,load_controller

ROOT=Path(__file__).resolve().parents[1]

class Config(c.Structure):
    _fields_=[(k,c.c_int32) for k in game_assets.CAMERA_FIELDS]+[
        ("pitch_count",c.c_uint32),("pitches",(c.c_int16*2)*4)]
class CameraWorld(c.Structure):
    _fields_=[("surfaces",c.POINTER(Wall)),("count",c.c_uint32)]
class Camera(c.Structure):
    _fields_=[(k,c.c_int32) for k in ("target_x","target_y","target_z","look_x","look_z",
        "previous_x","previous_y","previous_z","fraction","pitch","eye_x","eye_y","eye_z")]+[
        ("respawns",c.c_uint32),("obstructed",c.c_uint32),("view",c.c_int16*12)]
class Orbit(c.Structure):
    _fields_=[(k,c.c_int32) for k in ('focus_x','focus_y','focus_z','previous_x','previous_y','previous_z','fraction')]+[('initialized',c.c_uint32),('respawns',c.c_uint32)]
class OrbitConfig(c.Structure):
    _fields_=[(k,c.c_int32) for k in ('distance','target_height','clearance','snap_distance')]+[(k,c.c_uint32) for k in ('follow_shift','vertical_shift','recovery_step')]

def config(values=None):
    profile=json.loads((ROOT/"profiles/sm64-mario.json").read_text())
    profile["camera"].update(values or {})
    d=game_assets.camera_settings(profile)
    pitches=((c.c_int16*2)*4)(*((c.c_int16*2)(*v) for v in
                              d["pitches"]+[[0,0]]*(4-len(d["pitches"]))))
    return Config(*(d[k] for k in game_assets.CAMERA_FIELDS),len(d["pitches"]),pitches)

def surfaces(chunks):
    data=game_assets.camera_surfaces(chunks)
    array=(Wall*len(data))(*(Wall(*(Point(*p) for p in pts),*rest) for pts,rest in data))
    world=CameraWorld(array,len(array));world.references=array
    return world

def geometry(wall_z=None,wall_height=1000,ceiling=None,slope=False):
    v=[(-2000,-500 if slope else 0,-2000),(-2000,-500 if slope else 0,2000),
       (2000,500 if slope else 0,2000),(2000,500 if slope else 0,-2000)]
    t=[(0,1,2,1),(0,2,3,1)]
    if wall_z is not None:
        v += [(-2000,0,wall_z),(2000,0,wall_z),(2000,wall_height,wall_z),(-2000,wall_height,wall_z)]
        t += [(4,5,6,1),(4,6,7,1)]
    if ceiling is not None:
        offset=len(v)
        v += [(-2000,ceiling,-2000),(2000,ceiling,-2000),(2000,ceiling,2000),(-2000,ceiling,2000)]
        t += [(offset,offset+1,offset+2,1),(offset,offset+2,offset+3,1)]
    return [(v,t)]

def project(cam,cfg,point):
    values=[sum(cam.view[i*4+k]*point[k] for k in range(3))/256+cam.view[i*4+3] for i in range(3)]
    return (160+cfg.focal*values[0]/values[2],120-cfg.focal*values[1]/values[2],values[2])

def segment_hits(a,b,triangle):
    # Independent floating-point segment/triangle intersection, with no plane
    # expansion or fixed-point camera helpers copied from the implementation.
    def sub(x,y):return tuple(v-w for v,w in zip(x,y))
    def dot(x,y):return sum(v*w for v,w in zip(x,y))
    def cross(x,y):return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    p,q,r=triangle;d=sub(b,a);u=sub(q,p);v=sub(r,p);h=cross(d,v);det=dot(u,h)
    if abs(det)<1e-8:return False
    s=sub(a,p);first=dot(s,h)/det
    if not 0<=first<=1:return False
    k=cross(s,u);second=dot(d,k)/det
    if second<0 or first+second>1:return False
    distance=dot(v,k)/det
    return 1e-5<distance<1-1e-5

class CameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.player_lib=load_controller()
        out=ROOT/"build/camera-tests";out.mkdir(parents=True,exist_ok=True)
        dll=out/("camera.dll" if os.name=="nt" else "camera.so")
        flags=["-shared","-O1","-Wall","-Wextra","-Werror","-I"+str(ROOT/"firmware/include")]
        if os.name=="nt":flags += ["-fuse-ld=lld","-nostdlib","-Wl,/noentry","-Wl,/export:camera_reset","-Wl,/export:camera_step","-Wl,/export:camera_orbit_step"]
        else:flags += ["-fPIC"]
        subprocess.run([shutil.which("clang"),*flags,str(ROOT/"firmware/src/player.c"),
                        str(ROOT/"firmware/src/camera.c"),"-o",str(dll)],check=True)
        cls.lib=c.CDLL(str(dll))
        for name in ("camera_reset","camera_step"):
            getattr(cls.lib,name).argtypes=[c.POINTER(Camera),c.POINTER(Player),c.POINTER(Config),c.POINTER(CameraWorld)]
        cls.lib.camera_orbit_step.argtypes=[c.POINTER(Orbit),c.POINTER(Player),c.POINTER(OrbitConfig),c.POINTER(CameraWorld),c.POINTER(c.c_int16),c.c_int32]

    def orbit(self,state,world):
        cam,p,cfg=state
        co=round(math.cos(math.pi/8)*256);si=-round(math.sin(math.pi/8)*256)
        view=(c.c_int16*12)(256,0,0,0,0,co,-si,0,0,si,co,0)
        self.lib.camera_orbit_step(c.byref(cam),c.byref(p),c.byref(cfg),c.byref(world),view,4)
        return view

    def test_orbit_framing_follow_and_teleport(self):
        state=(Orbit(),Player(),OrbitConfig(1000,125,20,1000,2,3,16));cam,p,cfg=state
        world=surfaces(geometry());view=self.orbit(state,world)
        screen=[]
        for height in (0,180):
            y=height*4*view[5]/256+view[7];z=height*4*view[9]/256+view[11]
            self.assertGreater(z,257);screen.append(120-256*y/z)
        self.assertTrue(80<screen[1]<screen[0]<190,screen)
        self.assertTrue(30<screen[0]-screen[1]<70,screen)
        p.x=24;self.orbit(state,world);self.assertTrue(0<cam.focus_x<p.x)
        p.x=4000;self.orbit(state,world);self.assertEqual(cam.focus_x,p.x)

    def test_orbit_collision_retracts_then_recovers_gradually(self):
        state=(Orbit(),Player(),OrbitConfig(1000,125,20,1000,2,3,16));cam,_,_=state
        self.orbit(state,surfaces(geometry(wall_z=-300)))
        fraction=cam.fraction;self.assertTrue(0<fraction<256)
        self.orbit(state,surfaces(geometry()))
        self.assertTrue(fraction<cam.fraction<256)

    def start(self,chunks=None,spawn=(0,0,0),values=None):
        chunks=chunks or geometry();w=world_for(chunks,spawn);cw=surfaces(chunks);cfg=config(values);p=Player();cam=Camera()
        self.player_lib.player_reset(c.byref(p),c.byref(w))
        self.lib.camera_reset(c.byref(cam),c.byref(p),c.byref(cfg),c.byref(cw))
        return p,cam,w,cw,cfg,chunks

    def tick(self,state,keys=0):
        p,cam,w,cw,cfg,_=state
        self.player_lib.player_step(c.byref(p),c.byref(w),keys)
        self.lib.camera_step(c.byref(cam),c.byref(p),c.byref(cfg),c.byref(cw))

    def visible(self,state):
        p,cam,_,_,cfg,_=state
        for point in ((p.x,p.y,p.z),(p.x,p.y+128,p.z)):
            x,y,z=project(cam,cfg,point)
            self.assertGreater(z,cfg.near_z)
            self.assertTrue(0<x<320 and 0<y<240,(x,y,z,cam.pitch,cam.fraction))

    def unobstructed(self,state):
        p,cam,_,_,cfg,chunks=state
        anchor=(p.x,p.y+cfg.target_height,p.z);eye=(cam.eye_x,cam.eye_y,cam.eye_z)
        for vertices,triangles in chunks:
            for a,b,c,_ in triangles:
                self.assertFalse(segment_hits(anchor,eye,[vertices[i] for i in (a,b,c)]),(anchor,eye,(a,b,c)))

    def test_configured_projection_and_initial_framing(self):
        for values in ({},{"pitch_degrees":45,"distance":1200,"target_height":96,"focal":300}):
            s=self.start(values=values);self.visible(s);self.unobstructed(s)
            p,cam,_,_,cfg,_=s
            self.assertEqual((cam.target_x,cam.target_y,cam.target_z),(0,cfg.target_height,0))
            self.assertEqual(cam.fraction,256)

    def test_horizontal_follow_and_lookahead_settle_after_stopping(self):
        s=self.start();p,cam,_,_,cfg,_=s
        for _ in range(50):
            self.tick(s,2);self.visible(s);self.unobstructed(s)
            self.assertLessEqual(abs(cam.target_x-p.x),cfg.lookahead_limit)
        self.assertGreater(cam.look_x,0)
        self.assertGreater(cam.target_x,p.x)
        for _ in range(60):self.tick(s)
        self.assertEqual((cam.look_x,cam.target_x),(0,p.x))

    def test_jump_moves_up_the_screen_and_landing_settles(self):
        s=self.start();p,cam,_,_,cfg,_=s
        initial=project(cam,cfg,(p.x,p.y,p.z))[1];base=cam.target_y
        self.tick(s,16)
        self.assertLess(cam.target_y-base,p.y)
        high=0
        for _ in range(45):
            high=max(high,initial-project(cam,cfg,(p.x,p.y,p.z))[1]);self.visible(s);self.tick(s,16)
        self.assertGreater(high,15)
        self.assertEqual(p.grounded,1)
        for _ in range(60):self.tick(s)
        self.assertEqual(cam.target_y,p.y+cfg.target_height)

    def test_high_wall_forces_safe_steeper_pitch(self):
        s=self.start(geometry(wall_z=-200));p,cam,_,_,cfg,_=s
        self.assertGreater(cam.pitch,0);self.assertEqual(cam.obstructed,1)
        self.assertGreater(cam.eye_z,-200)
        self.visible(s);self.unobstructed(s)
        for _ in range(100):
            self.tick(s,4);self.visible(s);self.unobstructed(s)
        self.assertEqual(cam.pitch,0)
        self.assertEqual(cam.fraction,256)

    def test_low_ceiling_shortens_without_forcing_minimum_distance(self):
        s=self.start(geometry(ceiling=220));_,cam,_,_,cfg,_=s
        self.assertLess(cam.fraction,256)
        self.assertLessEqual(cam.eye_y,220-cfg.clearance+2)
        self.visible(s);self.unobstructed(s)

    def test_close_back_wall_keeps_character_visible(self):
        s=self.start(geometry(wall_z=-20))
        self.visible(s);self.unobstructed(s)
        for _ in range(40):
            self.tick(s,8);self.visible(s);self.unobstructed(s)

    def test_boom_recovers_gradually_after_obstacle_removed(self):
        s=self.start(geometry(ceiling=220));_,cam,_,cw,cfg,_=s
        shortened=cam.fraction;cw.count=0
        self.tick(s)
        self.assertEqual(cam.fraction,shortened+cfg.recovery_step)
        for _ in range(60):self.tick(s)
        self.assertEqual(cam.fraction,256)

    def test_respawn_and_teleport_clear_follow_history(self):
        s=self.start();p,cam,w,cw,cfg,_=s
        for _ in range(15):self.tick(s,2)
        self.tick(s,16);self.tick(s,15)
        self.assertEqual((cam.target_x,cam.target_y,cam.target_z),(p.x,p.y+cfg.target_height,p.z))
        self.assertEqual((cam.look_x,cam.look_z),(0,0))
        p.x=700;p.z=400
        self.lib.camera_step(c.byref(cam),c.byref(p),c.byref(cfg),c.byref(cw))
        self.assertEqual((cam.target_x,cam.target_z),(700,400));self.visible(s)

    def test_slope_follow_and_bounded_air_lag(self):
        s=self.start(geometry(slope=True));p,cam,_,_,cfg,_=s
        for _ in range(70):self.tick(s,2);self.visible(s);self.unobstructed(s)
        p.grounded=0;p.y-=200
        self.lib.camera_step(c.byref(cam),c.byref(p),c.byref(cfg),c.byref(s[3]))
        self.assertLessEqual(abs(cam.target_y-(p.y+cfg.target_height)),cfg.max_vertical_lag)

    def test_map_edge_fall_and_respawn_keep_character_framed(self):
        s=self.start(spawn=(1900,0,0));p,cam,_,_,_,_=s
        fell=False
        for _ in range(100):
            self.tick(s,2)
            fell |= not p.grounded
            self.visible(s);self.unobstructed(s)
            if p.respawns:break
        self.assertTrue(fell)
        self.assertEqual(p.respawns,1)
        self.assertEqual((cam.look_x,cam.look_z),(0,0))

    def test_real_field_bridge_route_keeps_camera_outside_surfaces(self):
        r=json.loads((ROOT/"build/game/conversion.json").read_text());n=r["normalization"]
        _,chunks=scene_assets.convert(ROOT/"build/game/world/scene.obj",extent_q8_8=n["extent_q8_8"])
        s=self.start(chunks,r["spawn_q8_8"]);p,cam,w,_,_,_=s
        for x,z in [(-6558,7000),(-2000,7000),(-2000,5632),(-1100,5632),(1200,5632)]:
            for axis,v,i,negative,positive in (("x",x,0,1,2),("z",z,2,8,4)):
                goal=round((v-n["center"][i])*n["extent_q8_8"]/n["source_extent"])
                for _ in range(500):
                    if abs(getattr(p,axis)-goal)<=w.speed:break
                    self.tick(s,positive if getattr(p,axis)<goal else negative)
                    self.visible(s);self.unobstructed(s)
                self.assertLessEqual(abs(getattr(p,axis)-goal),w.speed)
            self.tick(s,16)
            for _ in range(45):self.tick(s);self.visible(s);self.unobstructed(s)
        self.assertEqual(p.respawns,0)

    def test_invalid_camera_profiles_rejected(self):
        for values in ({"yaw":30},{"pitch_degrees":0},{"distance":40000},{"near_z":0},
                       {"follow_shift":-1},{"recovery_step":0},{"focal":1.5}):
            with self.subTest(values=values),self.assertRaises(ValueError):config(values)

if __name__=="__main__":unittest.main(verbosity=2)
