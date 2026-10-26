from pathlib import Path
import argparse,subprocess,os,json,hashlib
root=Path(__file__).parent
parser=argparse.ArgumentParser();parser.add_argument('--oidn',required=True);parser.add_argument('--output',default=str(root));parser.add_argument('--atlas',default=2048,type=int);parser.add_argument('--samples',default=96,type=int);args=parser.parse_args()
out=Path(args.output).resolve();out.mkdir(exist_ok=True,parents=True);binary=Path(args.oidn).resolve();assert binary.is_file();env=os.environ.copy();env.update(STUDIO_OUTPUT_DIR=str(out),STUDIO_ATLAS=str(args.atlas),STUDIO_SAMPLES=str(args.samples),STUDIO_SOURCE=str(root/'source-unbatched.blend'))
for script in ['build-living.py','export-bake-data.py']:
 with (out/(script+'.log')).open('w')as log:subprocess.run(['blender','-b','-t','8','--python',str(root/script)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
assert (out/'bake-raw.exr').is_file() and (out/'assets/living-studio.glb').is_file()
with (out/'oidn.log').open('w')as log:subprocess.run([str(binary),'-f','RTLightmap','--hdr',str(out/'irradiance-raw.pfm'),'--threads','8','-o',str(out/'irradiance-clean.pfm')],stdout=log,stderr=subprocess.STDOUT,check=True)
with (out/'save-clean-lightmap.log').open('w')as log:subprocess.run(['blender','-b','-t','4','--python',str(root/'save-clean-lightmap.py')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
result={'passed':True,'atlas':args.atlas,'samples':args.samples,'files':[{ 'file':str(f.relative_to(out)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size} for f in [out/'assets/living-studio.glb',out/'assets/living-daylight.exr']],'fixedDaylight':True};(out/'rebuild-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
