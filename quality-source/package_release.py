from pathlib import Path
import hashlib,json,zipfile
p=Path(__file__).parent
for n in ['quality-check.json','media-check.json','source-preservation.json']:
 assert json.loads((p/n).read_text())['passed'],n
log=(p/'browser-check.log').read_text()
assert 'PASS: explicit real touch' in log and '\nError:' not in log
rebuild=json.loads((p/'rebuild-check.json').read_text())
assert rebuild['passed'] and rebuild['atlas']==2048 and rebuild['samples']==96
for row in rebuild['files']:assert hashlib.sha256((p/row['file']).read_bytes()).hexdigest()==row['sha256']
names=['package_release.py','rebuild-check.json','README.txt','ATTRIBUTION.txt','living-quality-credits.txt','THREE-LICENSE.txt','OIDN-LICENSE.txt','dependency-record.json','sofa-provenance.json','background-provenance.json','package.json','index.html','studio.js','scene-lighting.js','refine-surfaces.js','studio.bundle.js','build-living.py','export-bake-data.py','save-clean-lightmap.py','rebuild.py','check-quality.mjs','check-browser.cjs','run-browser.py','build-preview.py','source-unbatched.blend','source-reference.glb','navigation.json','walk-navigation.js','build-manifest.json','quality-check.json','source-preservation.json','media-check.json','browser-check.log','web-build.log','living-desktop-final.png','living-mobile-final.png','living-orbit-final.png','living-mobile-reopened.png','living-poster.webp','living-quality.mp4','living-quality.gif','comparison-before.png','comparison-after.png','comparison.html','living-comparison.png','spruit_sunrise_1k.hdr','references/GlamVelvetSofa.glb','references/GlamVelvetSofa-LICENSE.md','references/GlamVelvetSofa-metadata.json']
names += [str(f.relative_to(p))for f in (p/'assets').iterdir()if f.is_file()]
names=sorted(set(names));assert all((p/n).is_file()for n in names)
(p/'SHA256SUMS').write_text(''.join(hashlib.sha256((p/n).read_bytes()).hexdigest()+'  '+n+'\n'for n in names))
zpath=p/'stroyka-living-quality-v30.zip'
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED)as z:
 for n in names+['SHA256SUMS']:z.write(p/n,n)
with zipfile.ZipFile(zpath)as z:
 assert z.testzip()is None
 for n in names:assert hashlib.sha256(z.read(n)).hexdigest()==hashlib.sha256((p/n).read_bytes()).hexdigest()
result={'passed':True,'file':zpath.name,'files':len(names)+1,'bytes':zpath.stat().st_size,'sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'scope':'one browser living-room quality study','productionReady':False,'visualAcceptancePending':True};(p/'package-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
