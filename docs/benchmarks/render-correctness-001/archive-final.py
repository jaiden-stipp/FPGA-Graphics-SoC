from pathlib import Path
import hashlib,json,shutil,zipfile,re,subprocess
root=Path.cwd();src=root/'build/render-fixes';out=root/'docs/benchmarks/render-correctness-001'
for name in ['physical-comparison.log','deployment.log','rollback-running-check.json','selected-running-check.json','hardware-source-comparison.json','replay-final.log']+[f'physical-{m}-{c}.json' for m in ('baseline','fixed') for c in ('standing','moving')]:
    shutil.copyfile(src/name,out/name)
files=[]
for frame in (1,2):
    for channel,count in [('color',76800),('depth',76800),('palette',256)]:
        name=f'frame-{frame}.{channel}.hex';a=(src/'replay-fixed/capture'/name).read_bytes();b=(src/'replay-final/capture'/name).read_bytes()
        if len(b.split())!=count or a!=b:raise RuntimeError('Invalid or changed final capture '+name)
        files.append({'file':name,'experimental_default_sha256':hashlib.sha256(a).hexdigest(),'accepted_generator_sha256':hashlib.sha256(b).hexdigest(),'exact':True})
(out/'replay-generator-comparison.json').write_text(json.dumps({'scope':'Corrected software, experimental macros disabled vs fully regenerated accepted Stage 6 hardware','exact':True,'files':files},indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(out/'replay-final.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in (src/'replay-final').rglob('*'):
        if p.is_file():z.write(p,p.relative_to(src/'replay-final'))
world=json.loads((root/'build/castle-shaded/world.json').read_text())
(out/'source-appearance.json').write_text(json.dumps({'areas':[{'id':a['id'],'provenance':a['provenance']} for a in world['areas']]},indent=2)+'\n',encoding='utf-8')
sof=root/'build/quartus-render-depth12/RenderDepth12SoC.sof'
(out/'provenance.json').write_text(json.dumps({'baseline_commit':'15ce91c8080c965166296fae999d37387bba7f77','scope_commit':'d84c8a4','implementation_commit':'8f46e2c4f11df44e87adf09b086d460d7ca2da90','tools':{'quartus':'18.1.0 Build 625 SJ Lite Edition','clang':'21.1.6'},'selected_sof_sha256':'e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14','experimental_depth12_sof_sha256':hashlib.sha256(sof.read_bytes()).hexdigest(),'experimental_sof_programmed':False,'selected_hardware_sources_exact':True,'tests':{'world':34,'render_fixes':5,'clock':5,'physical_trials':12},'scope':'Combined software fixes on unchanged accepted 50 MHz hardware. Original asset packages and SOFs identified by hash; omitted from archive. Replay includes terrain/controller only. Timed movement is not cycle-identical; full-level performance/mission completeness unproven.'},indent=2)+'\n',encoding='utf-8')
(out/'README.md').write_text('''# RENDER-001 evidence

See ../../render-correctness-fixes.md for diagnosis, measurements and limitations.
The measurement runner snapshot must be copied to build/render-fixes/measure.py
in the repository checkout before executing: its parent-relative imports and
rollback paths deliberately refer to the repo and preserved local asset package.
Restore the exact local baseline package before repeating; CPU binaries alone
are insufficient because asset binaries are intentionally omitted here.

Physical trial JSON contains raw timestamps, input packets, atomic snapshots,
package hashes and automatic restore status. Measurements are summary statistics
computed from those files. selected-running-check.json establishes full-readback
release and frame progress on the selected package. No experimental hardware
was deployed. Source snapshots are reference copies, not independent projects.

Replay ZIPs contain full commands/framebuffer captures and test logs. The old
appearance replay uses the current canonical CPU clipper with old asset policy;
it is not a byte-exact replay of the old firmware. replay-final uses accepted,
regenerated RTL. Native integration tests cover actor pose/state separately.
The floating oracle is diagnostic only. The unsuccessful hardware experiments
and raw 12-bit fit reports are retained under experiments/.
''',encoding='utf-8')
shutil.copyfile(Path(__file__),out/'archive-final.py')
manifest={'algorithm':'sha256','files':{p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Archived',len(manifest['files']),'files')
