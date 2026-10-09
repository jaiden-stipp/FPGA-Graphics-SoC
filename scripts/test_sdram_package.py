"""Host loader validation: reject mismatched/out-of-range packages before reset."""
import binascii
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import socket
import load_game as loader


class PackageTests(unittest.TestCase):
    def test_retry_changes_transport_id_but_keeps_memory_transaction(self):
        class DroppedReply:
            def __init__(self): self.sent=[]
            def sendto(self,data,target): self.sent.append(data); self.target=target
            def settimeout(self,value): pass
            def recvfrom(self,size):
                if len(self.sent)==1: raise socket.timeout()
                transaction=struct.unpack_from('>I',self.sent[-1],21)[0]
                values=(0x53440100,0,0,0,0,3,0,17,0,0,0,0,0)
                return struct.pack('>2sBBIHHI13I',b'GS',2,2,transaction,0,0,0,*values),self.target
        client=loader.Loader.__new__(loader.Loader)
        client.socket=DroppedReply();client.target=('192.168.7.2',4000)
        client.timeout=.01;client.retries=2;client.transaction=42;client.transport_frame=99
        self.assertTrue(client.operation(loader.WRITE,0x80000000,(7,))['held'])
        first,second=client.socket.sent
        self.assertNotEqual(first[4:8],second[4:8])
        self.assertEqual(first[12:],second[12:])

    def test_wire_and_completed_reply(self):
        message=loader.packet(42,loader.WRITE,0x80000000,(0x12345678,0x89abcdef))
        command=message[12:]
        self.assertEqual(message[:4],b'GP\x02\x03')
        self.assertEqual(command[5:9],b'SD\x01\x22')
        self.assertEqual(struct.unpack('>H',command[-2:])[0],binascii.crc_hqx(command[:-2],0xffff))
        values=(0x53440100,0,1,2,3,2,0x5dad600d,17,0,0,0,0,0)
        reply=struct.pack('>2sBBIHHI13I',b'GS',2,2,42,0,0,0,*values)
        self.assertEqual(loader.decode_reply(reply,42)['words'],(1,2,3))
        self.assertIsNone(loader.decode_reply(reply,43))
        self.assertIsNone(loader.decode_reply(b'GS\x02\x01'+b'\0'*16,42))

    def test_manifest_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); image=root/'code.bin';image.write_bytes(b'12345')
            segment={'file':'code.bin','address':0,'bytes':5,'sha256':hashlib.sha256(b'12345').hexdigest()}
            manifest=root/'package.json'
            def write(segments): manifest.write_text(json.dumps({'format':'soc-game-package','version':1,'segments':segments}))
            write([segment]); self.assertEqual(loader.package_segments(manifest)[0][1],b'12345\0\0\0')
            write([dict(segment,address=0xfffc)])
            with self.assertRaises(ValueError):loader.package_segments(manifest)
            write([dict(segment,sha256='bad')])
            with self.assertRaises(ValueError):loader.package_segments(manifest)
            write([segment,segment])
            with self.assertRaises(ValueError):loader.package_segments(manifest)
            write([segment,dict(segment,address=0x40000018)])
            with self.assertRaises(ValueError):loader.package_segments(manifest)
            write([dict(segment,file='../code.bin')])
            with self.assertRaises(ValueError):loader.package_segments(manifest)


if __name__=='__main__':unittest.main()
