"""Prepare pinned native fixtures, then run every host regression in isolation."""
import argparse,json,os,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'build/tests');p.add_argument('--fixtures-dir',type=Path);a=p.parse_args()
    if a.fixtures_dir:os.environ['SOC_TEST_FIXTURES']=str(a.fixtures_dir.resolve())
    from game_assets import generate
    from test_support import ensure_castle_fixture,linked_test_packages
    from types import SimpleNamespace
    from soc import bootstrap
    from sm64_subset import convert
    bootstrap(SimpleNamespace())
    linked_test_packages()
    convert(ROOT/'profiles/sm64-bob-flat.json')
    generate(ROOT/'profiles/sm64-mario.json')
    ensure_castle_fixture(False);ensure_castle_fixture(True)
    a.out.mkdir(parents=True,exist_ok=True);rows=[]
    for test in sorted((ROOT/'scripts').glob('test_*.py')):
        if test.name in ('test_all.py','test_support.py'):continue
        start=time.monotonic()
        with (a.out/(test.stem+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,str(test)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        text=(a.out/(test.stem+'.log')).read_text(encoding='utf-8');count=re.search(r'Ran (\d+) tests?',text)
        rows.append({'file':test.name,'exit_code':result.returncode,'tests':int(count[1]) if count else None,'seconds':round(time.monotonic()-start,3)})
        (a.out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
        print(test.name,'PASS' if result.returncode==0 else 'FAIL',flush=True)
    return int(any(row['exit_code'] for row in rows))
if __name__=='__main__':sys.exit(main())
