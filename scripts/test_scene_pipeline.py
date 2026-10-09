import binascii
from pathlib import Path
import struct
import shutil
import socket
import subprocess
import sys
import threading
import tempfile
import unittest
import keyboard_udp
import scene_assets
import sm64_subset
import rv32i_subset
import diagnose_game

VERTICES = """static const Vtx verts[] = {
    {{{0,0,0},0,{0,0},{0,0,127,255}}},
    {{{1,0,0},0,{0,0},{0,0,127,255}}},
    {{{0,1,0},0,{0,0},{0,0,127,255}}},
};"""
PROFILE = {"display_list": "root", "discard_state": [], "texture_colors": {}}


class ScenePipelineTests(unittest.TestCase):
    def test_independent_coverage_reference_sees_outward_floor(self):
        vertices=[(-1000,0,-1000),(-1000,0,1000),(1000,0,1000),(1000,0,-1000)]
        pixels=diagnose_game.render([(vertices,[(0,1,2,1),(0,2,3,1)])],
                                   [diagnose_game.SKY,(0,200,0)],(0,0,0))
        self.assertEqual(pixels[200*320+160],(0,200,0))
        self.assertEqual(pixels[10*320+160],diagnose_game.SKY)
    def source(self, body):
        return VERTICES + "const Gfx root[] = {" + body + "gsSPEndDisplayList(),};"

    def test_nested_lists_preserve_cache_and_winding(self):
        text = self.source("gsSPVertex(verts,3,5),gsSPDisplayList(child),")
        text += "const Gfx child[]={gsSP1Triangle(5,7,6,0),gsSPEndDisplayList(),};"
        points, faces, _, _ = sm64_subset.lower(text, PROFILE)
        self.assertEqual(points, [(0,0,0),(0,1,0),(1,0,0)])
        self.assertEqual(faces, [([1,2,3],"default")])

    def test_multi_file_roots_and_whole_triangle_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            (base/"vertices.c").write_text(VERTICES)
            (base/"lists.c").write_text(
                "const Gfx first[]={gsSPVertex(verts,3,0),gsSP1Triangle(0,1,2,0),gsSPEndDisplayList(),};"
                "const Gfx second[]={gsSPVertex(verts,3,0),gsSP1Triangle(0,2,1,0),gsSPEndDisplayList(),};")
            profile=PROFILE | {"sources":["vertices.c","lists.c"],
                "roots":[{"name":"first","layer":"opaque"},{"name":"second","layer":"opaque"}],
                "selection_bounds":{"min":[.2,-1,-1],"max":[.3,2,1]}}
            points,faces,_,_,report=sm64_subset.geometry(base,profile)
            self.assertEqual(points,[(0,0,0),(1,0,0),(0,1,0)])
            # Bounds cross a small part of the triangle: all source vertices stay.
            self.assertEqual(faces,[([1,2,3],"default"),([1,3,2],"default")])
            self.assertEqual([r["selected_triangles"] for r in report["roots"]],[1,1])
            for update in ({"sources":["../outside.c"]}, {"sources":["lists.c","lists.c"]},
                           {"roots":[{"name":"first","layer":"alpha"}]},
                           {"selection_bounds":{"min":[2,2,2],"max":[3,3,3]}}):
                with self.subTest(update=update),self.assertRaises(ValueError):
                    sm64_subset.geometry(base,profile | update)

    def test_unknown_geometry_and_recursive_lists_rejected(self):
        for body in ("gsSPMatrix(matrix,0),", "gsSPDisplayList(root),", "gsSP1Triangle(0,1,2,0),"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                sm64_subset.lower(self.source(body), PROFILE)
        with self.assertRaises(ValueError):
            sm64_subset.lower(self.source(""), PROFILE | {"discard_state": ["gsSPMatrix"]})

    def test_texture_loss_requires_declared_mapping(self):
        text = self.source("gsDPSetTextureImage(0,0,1,grass),gsSPVertex(verts,3,0),gsSP1Triangle(0,1,2,0),")
        with self.assertRaises(ValueError):
            sm64_subset.lower(text, PROFILE)
        _, faces, _, discarded = sm64_subset.lower(text, PROFILE | {"texture_colors": {"grass": [0,1,0]}})
        self.assertEqual(faces[0][1], "grass")
        self.assertEqual(discarded, {"gsDPSetTextureImage": 1})

    def test_actor_lights_and_texture_enable_preserve_geometry(self):
        policy = PROFILE | {"light_colors": {"red": [1,0,0], "blue": [0,0,1]},
                            "initial_light": "blue", "texture_colors": {"logo": [1,1,1]}}
        text = self.source("gsSPVertex(verts,3,0),gsSPLight(&red.l,1),gsSP1Triangle(0,1,2,0),"
                           "gsDPSetTextureImage(0,0,1,logo),gsSPTexture(0,0,0,0,G_ON),"
                           "gsSP1Triangle(0,1,2,0),gsSPTexture(0,0,0,0,G_OFF),gsSP1Triangle(0,1,2,0),")
        points, faces, _, _ = sm64_subset.lower(text,policy)
        self.assertEqual(points,[(0,0,0),(1,0,0),(0,1,0)])
        self.assertEqual(faces,[([1,2,3],"red"),([1,2,3],"logo"),([1,2,3],"red")])

    def test_actor_opacity_policy_rejects_transparency(self):
        policy = PROFILE | {"opaque_environment": True}
        for macro in ("gsDPSetEnvColor(255,255,255,128),", "gsDPSetAlphaCompare(G_AC_THRESHOLD),"):
            with self.assertRaises(ValueError):
                sm64_subset.lower(self.source(macro),policy)

    def test_mesh_capacity_and_vertex_remapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"scene.obj"
            lines = []
            for i in range(50):
                lines += [f"v {i} 0 0", f"v {i} 1 0", f"v {i} 0 1"]
            lines += [f"f {3*i+1} {3*i+2} {3*i+3}" for i in range(50)]
            path.write_text("\n".join(lines))
            _, chunks = scene_assets.convert(path)
            self.assertEqual(len(chunks),2)
            self.assertEqual(sum(len(t) for _,t in chunks),50)
            for vertices, triangles in chunks:
                self.assertLessEqual(len(vertices),128)
                for a,b,c,_ in triangles:
                    self.assertLess(max(a,b,c),len(vertices))
                self.assertTrue(all(-1024<=x<=1024 for point in vertices for x in point))

    def test_invalid_and_degenerate_obj_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"scene.obj"
            for contents in ("v nan 0 0\nf 1 1 1", "v 0 0 0\nf 0 1 1",
                             "v 0 0 0\nv 1 0 0\nv 2 0 0\nf 1 2 3"):
                path.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    scene_assets.convert(path)

    def test_control_packet_transport_and_crc(self):
        payload=keyboard_udp.packet(0x12345678,255,6)
        self.assertEqual(struct.unpack(">2sBBIHH",payload[:12]),(b"GP",2,3,0x12345678,0,11))
        self.assertEqual(payload[12:21],b"GF\x02\x04\x04\xff\x4b\xff\x06")
        self.assertEqual(struct.unpack(">H",payload[-2:])[0],binascii.crc_hqx(payload[12:-2],0xffff))
        with self.assertRaises(ValueError):
            keyboard_udp.packet(0,0,32)

    def test_sender_udp_loopback_and_neutral_exit(self):
        received = []
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server:
            server.bind(("127.0.0.1",0))
            server.settimeout(1)
            def receive():
                while True:
                    try:
                        data, peer = server.recvfrom(1024)
                    except socket.timeout:
                        return
                    received.append(data)
                    ack = b"GS\x02\x01" + data[4:8] + b"\x00\x00\x08\x00" + struct.pack(">II",1,0)
                    server.sendto(ack,peer)
            worker=threading.Thread(target=receive)
            worker.start()
            result=subprocess.run([sys.executable,str(Path(keyboard_udp.__file__)),"--ip","127.0.0.1",
                                   "--port",str(server.getsockname()[1]),"--buttons","2","--seconds","0.05"],
                                  capture_output=True,text=True,timeout=5)
            worker.join(timeout=2)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertGreaterEqual(len(received),5)
        self.assertTrue(all(p[20]==2 for p in received[:-3]))
        self.assertTrue(all(p[20]==0 for p in received[-3:]))
        self.assertIn("packet replies",result.stdout)
        for p in received:
            self.assertEqual(struct.unpack(">H",p[-2:])[0],binascii.crc_hqx(p[12:-2],0xffff))

    @unittest.skipUnless(shutil.which("clang") and shutil.which("llvm-nm"), "Clang C subset audit not installed")
    def test_c_subset_rejects_float_heap_and_runtime_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"unsupported.c"
            for contents in ("float step(float x) { return x+1.0f; }",
                             "extern void *malloc(unsigned); void *step(void) { return malloc(4); }",
                             "int step(int x, int y) { return x/y; }"):
                path.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    rv32i_subset.check(path)


if __name__=="__main__":
    unittest.main()
