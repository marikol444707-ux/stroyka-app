from pathlib import Path
import zipfile,hashlib,json
p=Path(__file__).parent
logs=['realism-browser-check.log','rooms-browser-check.log','materials-check.log','family-plan-browser-check.log','realism-capture.log']
reports=['garden-model-check.json','walk-look-check.json','soft-furnishings-check.json','realism-model-integrity.json','realism-film-validation.json','family-plan-check.json','project-discussion-check.json','material-context-check.json','assembly-motion-check.json','bedroom-model-check.json','room-navigation-check.json','lighting-model-check.json','furniture-model-check.json','project-context-check.json','interior-model-check.json','wall-section-model-check.json','facade-model-check.json','house-roof-model-check.json','material-data-check.json','roof-model-check.json','study-model-check.json','navigation-check.json','journey-timeline-check.json','node-checks.json']
for n in logs:
 text=(p/n).read_text();assert 'PASS' in text and '\nError:' not in text,n
for n in reports:assert json.loads((p/n).read_text())['passed'],n
run=(p/'regressions.log').read_text()
for test in ['check-realism-browser.cjs','check-rooms-browser.cjs','check-materials.cjs','check-family-plan-browser.cjs']:assert 'PASS '+test in run,test
assert 'Traceback' not in run and len(json.loads((p/'node-checks.json').read_text())['checks'])==21
nav=json.loads((p/'navigation.json').read_text());assert nav['modelSha256']==hashlib.sha256((p/'stroyka-polished.glb').read_bytes()).hexdigest()
for row in json.loads((p/'realism-model-integrity.json').read_text())['files']:assert hashlib.sha256((p/row['file']).read_bytes()).hexdigest()==row['sha256']
names=['README.txt','THREE-LICENSE.txt','package.json','build_viewer.py','viewer-template.html','index.html','stroyka-materials.html','stroyka-polished.glb','previous-house.glb','base-interior.blend','unbatched-polished.blend','previous-interior.blend','refine-furniture.py','rearrange-bedrooms.py','optimize_model.py','export_navigation.py','export-family-plan.py','furniture-layout.json','furniture-changes.json','bedroom-changes.json','model-optimization.json','navigation.json','previous-navigation.json','public-site.css','poster-house.webp','verify-browser-v26.py','package_release.py','build-realism-film.py','capture-realism.cjs','realism-film-storyboard.json','realism.mp4','realism.gif','realism-preview.png','regressions.log','build.log']
names += [f.name for f in p.glob('realism-*.png') if not f.name.endswith('-initial.png')]+[f.name for f in p.glob('*.js')]+[f.name for f in p.glob('check-*.mjs')]+[f.name for f in p.glob('check-*.cjs')]+logs+reports
names=sorted(set(names));assert all((p/n).is_file() for n in names)
(p/'SHA256SUMS').write_text(''.join(hashlib.sha256((p/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
archive=p/'stroyka-one-house-v26.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for n in names+['SHA256SUMS']:z.write(p/n,n)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for n in names:assert hashlib.sha256(z.read(n)).hexdigest()==hashlib.sha256((p/n).read_bytes()).hexdigest()
result={'passed':True,'archive':archive.name,'files':len(names)+1,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'production_ready':False};(p/'package-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
