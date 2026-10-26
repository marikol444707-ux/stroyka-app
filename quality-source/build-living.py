"""Dedicated living-room quality study, derived from the existing house, not a new plan."""
import bpy,math,json,hashlib,os
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).parent;P=Path(os.environ.get('STUDIO_OUTPUT_DIR',str(ROOT)));P.mkdir(exist_ok=True,parents=True);A=P/'assets';A.mkdir(exist_ok=True)
SOURCE=Path(os.environ.get('STUDIO_SOURCE',str(ROOT/'source-unbatched.blend')))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=int(os.environ.get('STUDIO_SAMPLES','32'));scene.cycles.use_denoising=True
scene.cycles.max_bounces=7;scene.cycles.diffuse_bounces=4;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=5
scene.render.threads_mode='FIXED';scene.render.threads=8
interior=bpy.data.objects['07_interior'];new=[];removed=[]
for o in list(interior.children):
 if o.name.startswith(('sofa','coffee')) or o.name=='table foot':removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
def material(name,color,rough=.8,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal;return m
cloth=material('studio oatmeal woven upholstery',(.57,.52,.43),.95)
backcloth=material('studio warm ivory upholstery',(.73,.68,.57),.97)
accent=material('studio muted olive linen',(.25,.29,.21),.98)
seam=material('studio upholstery piping',(.48,.43,.35),.97)
metal=material('studio dark bronze feet',(.065,.059,.045),.4,.65)
stone=material('studio honed pale limestone',(.64,.60,.51),.72)
ceramic=material('studio matte handmade ceramic',(.76,.72,.63),.42)
pages=material('studio book pages',(.70,.65,.55),.96)
cover=material('studio linen book cover',(.22,.27,.25),.92)
rugmat=material('studio undyed wool rug',(.57,.54,.47),1)
# Fine woven normal/albedo maps are physical-scale repeatable maps, not a scene background.
import numpy as np
N=512;y,x=np.mgrid[0:N,0:N];warp=np.cos(x*2*math.pi/8);weft=np.cos(y*2*math.pi/8);alternating=((x//8+y//8)%2)*2-1
height=.5+.13*np.where(alternating>0,warp,weft)+.025*np.sin(x*.91+y*.37)
shade=.84+.08*np.where(alternating>0,warp,weft)+.025*np.sin(x*.91+y*.37)
pixels=np.ones((N,N,4),np.float32);pixels[:,:,:3]=shade[:,:,None]
im=bpy.data.images.new('studio woven cloth albedo',width=N,height=N,alpha=True);im.pixels.foreach_set(pixels.ravel());im.filepath_raw=str(A/'upholstery-albedo.png');im.file_format='PNG';im.save()
gx=np.roll(height,-1,1)-np.roll(height,1,1);gy=np.roll(height,-1,0)-np.roll(height,1,0);normal=np.stack((-gx*.7,-gy*.7,np.ones_like(gx)),axis=-1);normal/=np.linalg.norm(normal,axis=-1,keepdims=True);npix=np.ones((N,N,4),np.float32);npix[:,:,:3]=normal*.5+.5
nm=bpy.data.images.new('studio woven cloth normal',width=N,height=N,alpha=True);nm.colorspace_settings.name='Non-Color';nm.pixels.foreach_set(npix.ravel());nm.filepath_raw=str(A/'upholstery-normal.png');nm.file_format='PNG';nm.save()
for m in [cloth,backcloth,accent,rugmat]:
 nodes=m.node_tree.nodes;links=m.node_tree.links;b=nodes.get('Principled BSDF');uv=nodes.new('ShaderNodeUVMap');uv.uv_map='UVMap';mapping=nodes.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs[3].default_value=6;links.new(uv.outputs['UV'],mapping.inputs[0]);tex=nodes.new('ShaderNodeTexImage');tex.image=nm;tex.interpolation='Linear';links.new(mapping.outputs[0],tex.inputs['Vector']);n=nodes.new('ShaderNodeNormalMap');n.inputs['Strength'].default_value=.32;links.new(tex.outputs['Color'],n.inputs['Color']);links.new(n.outputs['Normal'],b.inputs['Normal'])
def finish(o,name,m):
 o.name=name;o.parent=interior;o.data.materials.clear();o.data.materials.append(m);new.append(o)
 if o.type=='MESH':
  for p in o.data.polygons:p.use_smooth=True
 return o
def box(name,loc,size,m,bevel=.035,soft=False):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);finish(o,name,m)
 mod=o.modifiers.new('continuous rounded upholstery','BEVEL');mod.width=bevel;mod.segments=7
 if soft:
  sub=o.modifiers.new('soft surface topology','SUBSURF');sub.levels=1;sub.render_levels=1
 else:o.modifiers.new('weighted surface normals','WEIGHTED_NORMAL')
 return o
def pipe(name,points,m,r=.0016):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=2;c.bevel_depth=r;c.bevel_resolution=2;s=c.splines.new('POLY');s.points.add(len(points)-1)
 for p,v in zip(s.points,points):p.co=(*v,1)
 s.use_cyclic_u=True;o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);return finish(o,name,m)
def roundloop(cx,cy,w,d,z,r=.035):
 pts=[]
 for x,y,a in [(cx+w/2-r,cy+d/2-r,0),(cx-w/2+r,cy+d/2-r,90),(cx-w/2+r,cy-d/2+r,180),(cx+w/2-r,cy-d/2+r,270)]:
  for j in range(8):
   t=math.radians(a+j*90/7);pts.append((x+r*math.cos(t),y+r*math.sin(t),z))
 return pts
box('studio sofa upholstered low base',(4.8,-3.5,.255),(2.70,1.02,.23),cloth,.065,True)
box('studio sofa upholstered rear',(4.8,-3.955,.675),(2.68,.21,.73),cloth,.065,True)
for x in [3.55,6.05]:box('studio sofa gently rounded arm',(x,-3.5,.565),(.20,1.00,.50),cloth,.085,True)
for x in [3.64,5.96]:
 for y0 in [-3.87,-3.13]:box('studio sofa recessed bronze leg',(x,y0,.137),(.045,.045,.16),metal,.012)
for i,cx in enumerate([4.0,4.8,5.6]):
 seat=box('studio sofa separate seat '+str(i),(cx,-3.40,.445),(.765,.755,.185),backcloth,.061,True)
 pipe('studio sofa seat tailored piping '+str(i),roundloop(cx,-3.40,.730,.72,.495,.05),seam,.0018)
 back=box('studio sofa separate back '+str(i),(cx,-3.83,.775),(.765,.22,.53),backcloth,.068,True);back.rotation_euler.x=.12
 # A restrained seam across the actual cushion front, no inflated ball shapes.
 pts=[(px,py,pz) for px,py,pz in roundloop(cx,.775,.715,.475,-3.701,.05)]
 pts=[(px,pz,py)for px,py,pz in pts];pipe('studio sofa back tailored piping '+str(i),pts,seam,.0014)
for i,(cx,ang) in enumerate([(4.04,.14),(5.57,-.16)]):
 p=box('studio loose linen cushion '+str(i),(cx,-3.64,.735),(.43,.18,.405),accent if i else rugmat,.075,True);p.rotation_euler=(.2,ang,ang*.5)
# A folded textile follows the arm and seat, rather than being a flat cube.
verts=[];uv=[];faces=[];nx=36;ny=28
for j in range(ny+1):
 v=j/ny
 for i in range(nx+1):
  u=i/nx;xx=3.475+u*.72;yy=-3.66+v*.55;zz=.53+.28*math.exp(-((u-.12)/.20)**2)+.009*math.sin(v*math.pi*14+u*1.4)*(1-.3*u);verts.append((xx,yy,zz));uv.append((u*2,v*2))
for j in range(ny):
 for i in range(nx):a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
me=bpy.data.meshes.new('arm throw folded cloth');me.from_pydata(verts,[],faces);me.update();layer=me.uv_layers.new(name='UVMap')
for po in me.polygons:
 for li in po.loop_indices:layer.data[li].uv=uv[me.loops[li].vertex_index]
o=bpy.data.objects.new('studio draped wool throw',me);bpy.context.collection.objects.link(o);finish(o,o.name,rugmat);solid=o.modifiers.new('textile thickness','SOLIDIFY');solid.thickness=.004
box('studio fitted woven rug',(4.73,-2.83,.067),(3.40,2.42,.018),rugmat,.012)
# Same coffee-table position and footprint, improved edge and pedestal construction.
for name,rad,depth,z,m in [('studio coffee stone top',.504,.045,.414,stone),('studio coffee oak pedestal',.19,.335,.233,bpy.data.materials['light oak'])]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=rad,depth=depth,location=(4.8,-2.15,z));o=bpy.context.object;finish(o,name,m);be=o.modifiers.new('soft machined edge','BEVEL');be.width=.009;be.segments=4;o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
box('studio coffee book pages',(4.77,-2.15,.454),(.225,.306,.029),pages,.003)
for z in [.438,.470]:box('studio coffee book cloth cover',(4.77,-2.15,z),(.231,.312,.004),cover,.002)
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.044,depth=.073,location=(5.03,-2.19,.474));cup=bpy.context.object;finish(cup,'studio coffee ceramic cup',ceramic);b=cup.modifiers.new('cup softened edge','BEVEL');b.width=.006;b.segments=4
# Neutralise the old orange wood image, preserving its real grain and UV layout.
source=bpy.data.images.get('oak-source.png');wood=source.copy();wood.name='studio natural muted oak';arr=np.array(source.pixels[:],np.float32).reshape((-1,4));lum=arr[:,:3]@np.array([.2126,.7152,.0722]);arr[:,:3]=np.clip(arr[:,:3]*.40+lum[:,None]*.60,0,1);arr[:,:3]=np.clip(arr[:,:3]*1.12,0,1);wood.pixels.foreach_set(arr.ravel());wood.filepath_raw=str(A/'studio-oak.png');wood.file_format='PNG';wood.save()
for name in ['oak','light oak']:
 m=bpy.data.materials[name];bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.65
 for node in m.node_tree.nodes:
  if node.type=='TEX_IMAGE' and node.image==source:node.image=wood
# Bake an actual daylight solution, including contacts, skylight and diffuse bounces.
for o in list(scene.objects):
 if o.type=='LIGHT':bpy.data.objects.remove(o,do_unlink=True)
world=bpy.data.worlds.new('studio sunrise environment');world.use_nodes=True;scene.world=world;nodes=world.node_tree.nodes;nodes.clear();env=nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'spruit_sunrise_1k.hdr'));bg=nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.55;out=nodes.new('ShaderNodeOutputWorld');balance=nodes.new('ShaderNodeHueSaturation');balance.inputs['Saturation'].default_value=.22;world.node_tree.links.new(env.outputs['Color'],balance.inputs['Color']);world.node_tree.links.new(balance.outputs['Color'],bg.inputs['Color']);world.node_tree.links.new(bg.outputs['Background'],out.inputs['Surface'])
bpy.ops.object.light_add(type='SUN',location=(-8,-10,12));sun=bpy.context.object;sun.name='studio low afternoon daylight';sun.rotation_euler=Vector((8,10,-12)).to_track_quat('-Z','Y').to_euler();sun.data.energy=1.25;sun.data.angle=math.radians(9)
bpy.ops.object.light_add(type='AREA',location=(3,-4.93,1.7));fill=bpy.context.object;fill.name='studio window soft skylight';fill.rotation_euler=Vector((0,1,-.08)).to_track_quat('-Z','Y').to_euler();fill.data.energy=180;fill.data.shape='RECTANGLE';fill.data.size=5.8;fill.data.size_y=2.2;fill.data.color=(.9,.95,1.)
# Convert all visible meshes/curves in the existing house, preserving coordinates.
selected=[];glasses=[]
for o in list(scene.objects):
 if o.type not in ['MESH','CURVE'] or not o.parent or o.hide_render:continue
 if o.parent.name=='08_landscape':continue
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 if o.type=='CURVE':bpy.ops.object.convert(target='MESH');o=bpy.context.object
 for mod in list(o.modifiers):
  if mod.type!='WEIGHTED_NORMAL' or o.type=='MESH':
   try:bpy.ops.object.modifier_apply(modifier=mod.name)
   except RuntimeError:pass
 mats=[m for m in o.data.materials if m]
 if mats and all(m.name=='glass'for m in mats):o.visible_shadow=False;glasses.append(o)
 else:selected.append(o)
# Join opaque surfaces for one shared atlas and efficient browser draw groups.
bpy.ops.object.select_all(action='DESELECT')
for o in selected:o.select_set(True)
bpy.context.view_layer.objects.active=selected[0];bpy.ops.object.join();opaque=bpy.context.object;opaque.name='studio house opaque surfaces';opaque.parent=None
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
if not opaque.data.uv_layers:opaque.data.uv_layers.new(name='UVMap')
opaque.data.uv_layers[0].name='UVMap';opaque.data.uv_layers.new(name='LightMap');opaque.data.uv_layers.active_index=1;opaque.data.uv_layers[0].active_render=True
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(68),island_margin=.004,area_weight=.4,correct_aspect=True);bpy.ops.object.mode_set(mode='OBJECT')
size=int(os.environ.get('STUDIO_ATLAS','1024'));irr=bpy.data.images.new('studio daylight irradiance',width=size,height=size,alpha=False,float_buffer=True);irr.colorspace_settings.name='Non-Color'
for m in set(opaque.data.materials):
 if not m or not m.use_nodes:continue
 for n in m.node_tree.nodes:n.select=False
 node=m.node_tree.nodes.new('ShaderNodeTexImage');node.name='BAKE_IRRADIANCE';node.image=irr;node.select=True;m.node_tree.nodes.active=node
scene.render.bake.use_clear=True;scene.render.bake.margin=8;scene.render.bake.use_pass_color=False;scene.render.bake.use_pass_direct=True;scene.render.bake.use_pass_indirect=True
print('BAKING',size,'samples',scene.cycles.samples,flush=True);bpy.ops.object.bake(type='DIFFUSE',pass_filter={'DIRECT','INDIRECT'},use_clear=True,margin=8)
irr.filepath_raw=str(P/'bake-raw.exr');irr.file_format='OPEN_EXR'
scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='16';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.exr_codec='ZIP';irr.save_render(str(P/'bake-raw.exr'),scene=scene)
# Export UV0 original albedo + UV1 irradiance atlas; browser assigns the lightmap explicitly.
for m in set(opaque.data.materials):
 if m and m.use_nodes:
  for n in list(m.node_tree.nodes):
   if n.name=='BAKE_IRRADIANCE':m.node_tree.nodes.remove(n)
bpy.ops.object.select_all(action='DESELECT');opaque.select_set(True)
for o in glasses:o.select_set(True)
bpy.context.view_layer.objects.active=opaque
bpy.ops.export_scene.gltf(filepath=str(A/'living-studio.glb'),export_format='GLB',use_selection=True,export_yup=True,export_texcoords=True,export_normals=True,export_materials='EXPORT',export_extras=True)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(P/'living-studio.blend'))
manifest={'source':str(SOURCE),'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'removedObjects':removed,'newFurnitureAuthoringParts':len(new),'atlas':size,'samples':scene.cycles.samples,'camera':{'position':[1.3,1.705,2.0],'target':[4.6,1.02,3.1]},'fixedDaylight':True,'geometryScope':'existing house and plan, replacement sofa and coffee table at original centres; dedicated quality study','notProductionReady':True}
(P/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('QUALITY_ASSETS_EXPORTED',flush=True)
