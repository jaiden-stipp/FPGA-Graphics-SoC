from pathlib import Path
import os,subprocess,sys,json,time
root=Path.cwd();out=root/'build/repo-audit';env=os.environ.copy();env['PATH']=r'C:\Program Files\LLVM\bin'+os.pathsep+env['PATH']
rows=[]
for test in sorted((root/'scripts').glob('test_*.py')):
    start=time.monotonic()
    with (out/(test.stem+'.log')).open('w',encoding='utf-8') as log:
        p=subprocess.run([sys.executable,str(test)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    row={'file':test.name,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,3)};rows.append(row)
    (out/'native-tests.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(test.name,p.returncode,flush=True)
