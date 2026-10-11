#!/usr/bin/env python3
"""Upload and read back CPU/SDRAM game packages using the existing UDP transport."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import secrets
import socket
import struct
import time

BEGIN, WRITE, READ, COMMIT, STATUS = range(1, 6)


def packet(transaction, operation, address=0, words=(), count=None):
    count = len(words) if count is None else count
    if operation not in range(1, 6) or not 0 <= count <= 3:
        raise ValueError('Invalid loader operation/count')
    payload = struct.pack('>2sBBII3I', b'SD', 1, (operation << 4) | count,
                          transaction, address, *(tuple(words)+(0,)*(3-len(words))))
    command = b'GF'+bytes((2, 11, len(payload)))+payload
    command += struct.pack('>H', binascii.crc_hqx(command, 0xffff))
    return struct.pack('>2sBBIHH', b'GP', 2, 3, transaction, 0, len(command))+command


def decode_reply(data, transaction):
    # Packet receipt is insufficient: wait for the operation-completed event.
    if len(data) != 68 or data[:4] != b'GS\x02\x02' or struct.unpack_from('>I',data,4)[0] != transaction:
        return None
    values=struct.unpack_from('>13I', data, 16)
    if values[0] != 0x53440100: return None
    if values[1]: raise RuntimeError(f'FPGA rejected loader operation, code {values[1]}')
    return {'initialized':bool(values[5]&2),'held':bool(values[5]&1),
            'words':values[2:5],'scratch':values[6],'refresh_count':values[7], 'input_abi':values[10], 'cpu_features':values[11], 'gpu_features':values[12]}


def package_segments(path):
    spec=json.loads(path.read_text())
    if spec.get('format')!='soc-game-package' or spec.get('version')!=1:
        raise ValueError('Unsupported game package')
    if 'target' in spec:
        from target_capabilities import validate
        validate(spec['target'])
    if 'content' in spec:
        from game_package import validate_content
        validate_content(spec['content'])
    segments=[]
    for segment in spec['segments']:
        source=(path.parent/segment['file']).resolve()
        if source.parent != path.parent.resolve(): raise ValueError('Package files must share the manifest directory')
        payload=source.read_bytes()
        if len(payload)!=segment['bytes'] or hashlib.sha256(payload).hexdigest()!=segment['sha256']:
            raise ValueError(f'Package hash/length mismatch: {source.name}')
        base=segment['address']; padded=payload.ljust((len(payload)+3)//4*4,b'\0')
        end=base+len(padded)
        if base%4 or not (0<=base<=end<=0x10000 or 0x80000000<=base<=end<=0x87fff000):
            raise ValueError('Package exceeds CPU RAM or SDRAM asset range')
        if padded: segments.append((base,padded,source.name))
    if not any(base==0 for base,_,_ in segments): raise ValueError('Missing CPU image')
    for i,(base,data,_) in enumerate(segments):
        for other,other_data,_ in segments[:i]:
            if max(base,other)<min(base+len(data),other+len(other_data)): raise ValueError('Overlapping package segments')
    if spec.get('required_gpu_features',{}).get('command-dma-v1'):
        if spec.get('command_buffers')!={'address':0x87fe0000,'bytes':2048,'buffer_bytes':1024,'count':2}:
            raise ValueError('Invalid command DMA buffer reservation')
        if any(max(base,0x87fe0000)<min(base+len(data),0x87fe0800) for base,data,_ in segments):
            raise ValueError('Package overlaps command DMA buffers')
    return segments


class Loader:
    def __init__(self, ip='192.168.7.2', port=4000, timeout=0.3, retries=8):
        self.target=(ip,port); self.timeout=timeout; self.retries=retries
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.bind(('',0)); self.transaction=secrets.randbits(31); self.transport_frame=secrets.randbits(32)

    def close(self): self.socket.close()

    def operation(self, op, address=0, words=(), count=None, retries=None):
        self.transaction=(self.transaction+1)&0xffffffff
        message=packet(self.transaction,op,address,words,count)
        for _ in range(self.retries if retries is None else retries):
            # A retry is a new transport frame containing the same idempotent
            # memory operation; GP transport duplicates are deliberately dropped.
            self.transport_frame=(self.transport_frame+1)&0xffffffff
            message=message[:4]+struct.pack('>I',self.transport_frame)+message[8:]
            self.socket.sendto(message,self.target)
            deadline=time.monotonic()+self.timeout
            while time.monotonic()<deadline:
                self.socket.settimeout(max(0.001,deadline-time.monotonic()))
                try: data,peer=self.socket.recvfrom(2048)
                except socket.timeout: break
                except ConnectionResetError: continue
                if peer!=self.target: continue
                result=decode_reply(data,self.transaction)
                if result is not None: return result
        raise TimeoutError(f'No completed-operation reply from {self.target} (op {op}, address {address:#x})')

    def transfer(self, segments):
        # PHY/switch link negotiation may take a few seconds after programming.
        result=self.operation(BEGIN,retries=max(self.retries,40))
        if not result['initialized']: raise RuntimeError('SDRAM has not initialized')
        for base,data,name in segments:
            words=struct.unpack('<'+'I'*(len(data)//4),data)
            for op in (WRITE,READ):
                verb='Uploading' if op==WRITE else 'Verifying'
                print(f'{verb} {name}: {len(data):,} bytes at {base:#010x}',flush=True)
                checkpoint=time.monotonic()
                for i in range(0,len(words),3):
                    expected=words[i:i+3]
                    result=self.operation(op,base+4*i,expected if op==WRITE else (),len(expected))
                    if op==READ and tuple(result['words'][:len(expected)])!=expected:
                        raise RuntimeError(f'Readback mismatch at {base+4*i:#x}')
                    if time.monotonic()-checkpoint>=10:
                        print(f'  {min(4*(i+3),len(data)):,}/{len(data):,} bytes',flush=True); checkpoint=time.monotonic()
        self.operation(COMMIT)
        print('Readback verified; CPU released.',flush=True)


def require_hardware(loader,spec):
    required=spec.get('required_gpu_features',{})
    if required.get('packed-enqueue-v1') or required.get('draw-mesh-fraction-v1') or required.get('command-dma-v1'):
        status=loader.operation(STATUS,retries=max(loader.retries,40))
        bits=(4 if required.get('command-dma-v1') else 0)|(2 if required.get('packed-enqueue-v1') else 0)|(1 if required.get('draw-mesh-fraction-v1') else 0)
        if not status.get('cpu_features',0)&0x80000000 or status.get('gpu_features',0)&bits!=bits:
            raise RuntimeError('Package requires GPU features '+str(required)+'; current status does not advertise them (CPU left running)')
    if 'mouse-look-v1' in spec.get('target',{}).get('required_features',[]):
        if loader.operation(STATUS,retries=max(loader.retries,40))['input_abi']!=0x494e0101:
            raise RuntimeError('Package needs the IN v1 FPGA image; current board is incompatible (CPU left running)')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path,nargs='?')
    parser.add_argument('--ip',default='192.168.7.2'); parser.add_argument('--port',type=int,default=4000)
    parser.add_argument('--status',action='store_true')
    parser.add_argument('--wait-self-test',action='store_true')
    args=parser.parse_args()
    if not args.status and args.package is None: parser.error('Provide a package or --status')
    # Validate the entire package before BEGIN holds the CPU.
    segments=package_segments(args.package) if args.package is not None else None
    loader=Loader(args.ip,args.port)
    try:
        if segments is not None:
            spec=json.loads(args.package.read_text())
            require_hardware(loader,spec)
            loader.transfer(segments)
        if args.wait_self_test:
            deadline=time.monotonic()+10
            while True:
                result=loader.operation(STATUS)
                if result['scratch']==0x5dad600d: print('PASS physical SDRAM self-test'); break
                if result['scratch']&0xffff0000==0xdead0000: raise RuntimeError(f'SDRAM self-test failed: {result["scratch"]:#x}')
                if time.monotonic()>=deadline: raise TimeoutError('SDRAM self-test did not complete')
                time.sleep(0.05)
        if args.status: print(json.dumps(loader.operation(STATUS,retries=max(loader.retries,40)),indent=2))
    finally: loader.close()


if __name__=='__main__': main()
