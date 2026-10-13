"""Build and validate the local-boot/immutable-SDRAM executable contract."""
import hashlib,json,subprocess
from pathlib import Path
from game_package import integer

FIELDS={'abi','entry','code_address','code_bytes','bss_address','bss_bytes'}

def validate_execution(spec,segments):
    enabled=spec.get('required_cpu_features',{}).get('sdram-exec-v1') is True
    e=spec.get('execution')
    if not enabled and 'execution' not in spec:return
    if not enabled or not isinstance(e,dict) or set(e)!=FIELDS or e.get('abi')!='local-boot-sdram-v1':
        raise ValueError('SDRAM execution needs typed execution metadata and sdram-exec-v1')
    integer(e['code_address'],0x80000000,0x80000000);integer(e['code_bytes'],4,0x1000000)
    integer(e['entry'],e['code_address'],e['code_address']+e['code_bytes']-4)
    integer(e['bss_address'],0x81000000,0x87fff000);integer(e['bss_bytes'],0,0x87fff000-e['bss_address'])
    if any(e[k]%4 for k in FIELDS-{'abi'}):raise ValueError('Unaligned execution metadata')
    if not any(base==e['code_address'] and len(data)==e['code_bytes'] for base,data,_ in segments):
        raise ValueError('Executable segment does not match metadata')
    for base,data,_ in segments:
        if 0x80000000<=base<0x81000000 and (base!=e['code_address'] or len(data)!=e['code_bytes']):
            raise ValueError('Unexpected segment in immutable executable window')
        if e['bss_bytes'] and max(base,e['bss_address'])<min(base+len(data),e['bss_address']+e['bss_bytes']):
            raise ValueError('Loaded segment overlaps zero-initialized BSS')

def extract(root,stem,objcopy,nm):
    elf=root/'build'/f'{stem}.elf'
    output=subprocess.check_output([nm,'--defined-only',str(elf)],text=True)
    symbols={x.split()[-1]:int(x.split()[0],16) for x in output.splitlines() if len(x.split())==3}
    definitions=[('bin',0,['.boot','.local_data']),('code.bin',symbols['_code_start'],['.text','.rodata']),
                 ('state.bin',symbols['_data_start'],['.data']),('assets.bin',symbols['_assets_start'],['.game_assets'])]
    segments=[]
    for label,address,sections in definitions:
        path=root/'build'/f'{stem}.{label}'
        subprocess.run([objcopy,*['--only-section='+s for s in sections],'-O','binary',str(elf),str(path)],check=True)
        payload=path.read_bytes();payload=payload.ljust((len(payload)+3)//4*4,b'\0');path.write_bytes(payload)
        if label=='assets.bin' and len(payload)!=symbols['_assets_end']-symbols['_assets_start']:
            raise ValueError('Asset extraction includes unexpected section padding')
        if label=='state.bin' and len(payload)!=symbols['_data_end']-symbols['_data_start']:
            raise ValueError('State extraction length mismatch')
        if payload:segments.append({'file':path.name,'address':address,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
    code=next(x for x in segments if x['address']==0x80000000)
    if code['bytes']!=symbols['_code_end']-symbols['_code_start']:raise ValueError('Code extraction length mismatch')
    metadata={'abi':'local-boot-sdram-v1','entry':symbols['main'],'code_address':code['address'],'code_bytes':code['bytes'],
              'bss_address':symbols['_bss_start'],'bss_bytes':symbols['_bss_end']-symbols['_bss_start']}
    package={'format':'soc-game-package','version':1,'segments':segments,'execution':metadata,'required_cpu_features':{'sdram-exec-v1':True}}
    validate_execution(package,[(x['address'],(root/'build'/x['file']).read_bytes(),x['file']) for x in segments])
    # Sparse word fixture for the physical controller model; never a 2 GiB flat image.
    words=[]
    for s in segments:
        if s['address']<0x80000000:continue
        data=(root/'build'/s['file']).read_bytes()
        words += [f'{(s["address"]-0x80000000+i)//4:07x} {int.from_bytes(data[i:i+4],"little"):08x}\n' for i in range(0,len(data),4)]
    (root/'build'/f'{stem}.external.txt').write_text(''.join(words),encoding='utf-8')
    return segments,metadata
