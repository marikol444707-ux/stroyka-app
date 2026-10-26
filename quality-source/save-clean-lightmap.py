import bpy,numpy as np,os
from pathlib import Path
P=Path(os.environ.get('STUDIO_OUTPUT_DIR',str(Path(__file__).parent)))
with (P/'irradiance-clean.pfm').open('rb')as f:
 assert f.readline().strip()==b'PF';w,h=map(int,f.readline().split());scale=float(f.readline());assert scale<0;rgb=np.fromfile(f,dtype='<f4').reshape(h,w,3)
with (P/'irradiance-raw.pfm').open('rb')as f:
 f.readline();f.readline();f.readline();raw=np.fromfile(f,dtype='<f4').reshape(h,w,3)
rgb[np.max(raw,axis=2)<1e-6]=0
assert np.isfinite(rgb).all() and rgb.max()>1 and rgb.max()<64
rgba=np.ones((h,w,4),np.float32);rgba[:,:,:3]=np.maximum(0,rgb)
im=bpy.data.images.new('clean baked daylight',width=w,height=h,alpha=False,float_buffer=True);im.colorspace_settings.name='Non-Color';im.pixels.foreach_set(rgba.ravel());scene=bpy.context.scene;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='16';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.exr_codec='ZIP';im.save_render(str(P/'assets/living-daylight.exr'),scene=scene)
print('CLEAN_LIGHTMAP',w,h,float(rgb.max()),flush=True)
