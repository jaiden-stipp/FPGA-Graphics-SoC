from pathlib import Path
import json,hashlib,subprocess,re,ast
root=Path.cwd();out=root/'build/repo-audit';tracked=subprocess.check_output(['git','ls-files','-z']).decode().split('\0');r={'tracked_files':len([x for x in tracked if x]),'parse_errors':[],'manifest_checks':[],'broken_local_doc_links':[],'mojibake_docs':[]}
for name in tracked:
    if not name:continue
    p=root/name
    if p.suffix in ('.json','.py'):
        try:
            text=p.read_text(encoding='utf-8-sig')
            if p.suffix=='.json':json.loads(text)
            else:ast.parse(text,filename=name)
        except Exception as e:r['parse_errors'].append({'file':name,'error':str(e)})
    if p.suffix=='.md' and 'benchmarks/' not in name:
        try:text=p.read_text(encoding='utf-8')
        except UnicodeDecodeError as e:
            r['parse_errors'].append({'file':name,'error':str(e)});text=p.read_text(encoding='utf-8',errors='replace')
        if any(x in text for x in ('â€','Ã—','â€“','â€”')):r['mojibake_docs'].append(name)
        for link in re.findall(r'\]\(([^)]+)\)',text):
            link=link.strip('<>');target=link.split('#')[0]
            if not target or '://' in target or target.startswith(('http:','https:','mailto:')):continue
            target=re.sub(r':\d+$','',target)
            path=Path(target) if Path(target).is_absolute() else p.parent/target
            if not path.exists():r['broken_local_doc_links'].append({'file':name,'target':link})
    if p.name=='manifest.json' and 'benchmarks/' in name:
        m=json.loads(p.read_text(encoding='utf-8'));entries=m.get('files')
        if isinstance(entries,dict) and all(isinstance(v,str) for v in entries.values()):
            bad=[]
            for f,h in entries.items():
                q=p.parent/f
                if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest()!=h:bad.append(f)
            r['manifest_checks'].append({'file':name,'entries':len(entries),'bad':bad})
# Formal additionalProperties mismatch reproduced without introducing a validator dependency.
schema=json.loads((root/'schemas/game-package-v1.schema.json').read_text())
spec=json.loads((root/'build/mario-castle-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json').read_text())
r['package_schema_unknown_keys']=sorted(set(spec)-set(schema['properties']))
r['native_suites']=json.loads((out/'native-tests.json').read_text());tests=skips=failures=errors=0
for row in r['native_suites']:
    text=(out/(Path(row['file']).stem+'.log')).read_text(encoding='utf-8');m=re.search(r'Ran (\d+) tests?',text);row['tests']=int(m[1]) if m else None
    if m:tests+=int(m[1])
    for key in ('skipped','failures','errors'):
        m=re.search(key+r'=(\d+)',text)
        if m:
            if key=='skipped':skips+=int(m[1])
            elif key=='failures':failures+=int(m[1])
            else:errors+=int(m[1])
r['native_totals']={'tests':tests,'skipped':skips,'failures':failures,'errors':errors}
(out/'inventory-audit.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ('native_suites','manifest_checks')},indent=2));print('Manifests:',len(r['manifest_checks']),'bad entries:',sum(len(x['bad']) for x in r['manifest_checks']))
