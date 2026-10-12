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
from target_capabilities import feature_bits, GPU_REGS_PRESENT
from game_package import integer

BEGIN, WRITE, READ, COMMIT, STATUS = range(1, 6)


def packet(transaction, operation, address=0, words=(), count=None):
    count = len(words) if count is None else count
    integer(transaction,0,0xffffffff);integer(address,0,0xffffffff)
    for word in words:integer(word,0,0xffffffff)
    if type(operation) is not int or type(count) is not int or operation not in range(1, 6) or not 0 <= count <= 3:
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
    if not isinstance(spec,dict) or spec.get('format')!='soc-game-package' or type(spec.get('version')) is not int or spec.get('version')!=1:
        raise ValueError('Unsupported game package')
    allowed={'format','version','app','segments','target','content','required_cpu_features','required_gpu_features','cadence','diagnostic','command_buffers'}
    if set(spec)-allowed:raise ValueError('Unknown package fields')
    feature_bits(spec,'cpu');feature_bits(spec,'gpu')
    if 'app' in spec and not isinstance(spec['app'],str):raise ValueError('Invalid app')
    if 'diagnostic' in spec and (not isinstance(spec['diagnostic'],dict) or set(spec['diagnostic'])-{'terrain_submission','purpose'} or any(not isinstance(v,str) for v in spec['diagnostic'].values())):raise ValueError('Invalid diagnostic')
    if 'cadence' in spec:
        c=spec['cadence'];required={'simulation_tick_cycles','clock_hz','render','render_repeat_safe'}
        if not isinstance(c,dict) or not required<=set(c) or set(c)-required-{'interpolation'}:raise ValueError('Invalid cadence')
        integer(c['simulation_tick_cycles'],1,0xffffffff);integer(c['clock_hz'],1,0xffffffff)
        if c['render'] not in ('tick-paced','uncapped') or type(c['render_repeat_safe']) is not bool or ('interpolation' in c and type(c['interpolation']) is not bool):raise ValueError('Invalid render cadence')
        if c.get('interpolation') and (c['render']!='uncapped' or not c['render_repeat_safe']):raise ValueError('Interpolation requires uncapped repeat-safe rendering')
    if 'target' in spec:
        from target_capabilities import validate
        validate(spec['target'])
    if 'content' in spec:
        from game_package import validate_content
        validate_content(spec['content'])
    if not isinstance(spec.get('segments'),list) or not spec['segments']:raise ValueError('Missing package segments')
    segments=[]
    for segment in spec['segments']:
        if not isinstance(segment,dict) or set(segment)!={'file','address','bytes','sha256'}:raise ValueError('Invalid segment fields')
        name=segment['file']
        if not isinstance(name,str) or not name or '/' in name or '\\' in name:raise ValueError('Invalid segment filename')
        integer(segment['address'],0,0xffffffff);integer(segment['bytes'],0,134213632)
        h=segment['sha256']
        if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('Invalid segment hash')
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
    if 'command_buffers' in spec and not spec.get('required_gpu_features',{}).get('command-dma-v1'):raise ValueError('Command buffers require DMA')
    if spec.get('required_gpu_features',{}).get('command-dma-v1'):
        b=spec.get('command_buffers')
        if not isinstance(b,dict) or any(type(v) is not int for v in b.values()) or b!={'address':0x87fe0000,'bytes':2048,'buffer_bytes':1024,'count':2}:
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
        # Validate direct callers too, before BEGIN. Never release partially verified code.
        segments=list(segments)
        if not segments:raise ValueError('Empty transfer')
        for index,(base,data,name) in enumerate(segments):
            integer(base,0,0xffffffff)
            if not isinstance(data,bytes) or not data or len(data)%4 or not isinstance(name,str):raise ValueError('Invalid transfer segment')
            end=base+len(data)
            if base%4 or not (0<=base<end<=0x10000 or 0x80000000<=base<end<=0x87fff000):raise ValueError('Transfer outside memory')
            for other,previous,_ in segments[:index]:
                integer(other,0,0xffffffff)
                if max(base,other)<min(end,other+len(previous)):raise ValueError('Overlapping transfer segments')
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
    cpu=spec.get('required_cpu_features',{})
    bits=feature_bits(spec,'cpu')
    gpu_bits=feature_bits(spec,'gpu')
    if bits:
        status=loader.operation(STATUS,retries=max(loader.retries,40))
        if status.get('cpu_features',0)&bits!=bits:
            raise RuntimeError('Package requires CPU features '+str(cpu)+'; current status does not advertise them (CPU left running)')
    required=spec.get('required_gpu_features',{})
    if gpu_bits:
        status=loader.operation(STATUS,retries=max(loader.retries,40))
        bits=gpu_bits
        if not status.get('cpu_features',0)&GPU_REGS_PRESENT or status.get('gpu_features',0)&bits!=bits:
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
