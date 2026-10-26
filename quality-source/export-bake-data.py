from pathlib import Path
import bpy,numpy as np,os
P=Path(os.environ.get('STUDIO_OUTPUT_DIR',str(Path(__file__).parent)));bpy.ops.wm.open_mainfile(filepath=str(P/'living-studio.blend'));scene=bpy.data.scenes['Scene'];bpy.context.window.scene=scene
im=bpy.data.images.load(str(P/'bake-raw.exr'),check_existing=False);w,h=im.size;data=np.array(im.pixels[:],np.float32).reshape(h,w,4)[:,:,:3]
def pfm(path,d):
 with path.open('wb')as f:f.write(f'PF\n{w} {h}\n-1.0\n'.encode());d.astype('<f4').tofile(f)
pfm(P/'irradiance-raw.pfm',data);print('RADIANCE',np.percentile(data,[0,10,50,90,99,100]),flush=True)
print('EXPORTED_RADIANCE',w,h,flush=True)
