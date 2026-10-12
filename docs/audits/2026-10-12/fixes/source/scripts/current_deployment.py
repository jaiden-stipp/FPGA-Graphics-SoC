"""Verify the selected local artifacts and generate an owned programmer reference."""
import argparse,hashlib,json
from pathlib import Path
from load_game import package_segments,require_hardware
ROOT=Path(__file__).resolve().parents[1]
def selection(package_override=None):
    spec=json.loads((ROOT/'profiles/current-deployment.json').read_text(encoding='utf-8'))
    sof=(ROOT/spec['hardware']['file']).resolve();package=(package_override or ROOT/spec['package']).resolve()
    if not sof.is_relative_to(ROOT) or not package.is_relative_to(ROOT):raise ValueError('Deployment path escapes repository')
    if hashlib.sha256(sof.read_bytes()).hexdigest()!=spec['hardware']['sha256']:raise ValueError('Selected hardware hash changed; review the new fit before selection')
    package_segments(package)
    class RecordedHardware:
        retries=1
        def operation(self,*args,**kwargs):return spec['hardware']
    require_hardware(RecordedHardware(),json.loads(package.read_text(encoding='utf-8')))
    return spec,sof,package

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write-cdf',action='store_true');p.add_argument('--package',type=Path,help='Verify another local package against the selected hardware reference');a=p.parse_args()
    spec,sof,package=selection(a.package)
    record={'hardware':spec['hardware'],'package':str(package),'segments':json.loads(package.read_text(encoding='utf-8'))['segments'],'scope':'Verified local artifact selection; does not read or program the FPGA'}
    out=ROOT/'build/current-deployment.json';out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    if a.write_cdf:
        cdf=ROOT/'build/current-deployment.cdf'
        cdf.write_text('JedecChain;\n FileRevision(JESD32A);\n DefaultMfr(6E);\n P ActionCode(Cfg) Device PartName(EP4CE115F29) Path("'+sof.parent.as_posix()+'/") File("'+sof.name+'") MfrSpec(OpMask(1));\nChainEnd;\nAlteraBegin;\n ChainType(JTAG);\nAlteraEnd;\n',encoding='utf-8')
        print(cdf)
    print('Verified:',sof,'package:',package)
if __name__=='__main__':main()
