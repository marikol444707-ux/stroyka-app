"""Dedicated living-room quality study, derived from the existing house, not a new plan."""
import bpy,bmesh,math,json,hashlib,os
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).parent;P=Path(os.environ.get('STUDIO_OUTPUT_DIR',str(ROOT)));P.mkdir(exist_ok=True,parents=True);A=P/'assets';A.mkdir(exist_ok=True)
SOURCE=Path(os.environ.get('STUDIO_SOURCE',str(ROOT/'source-unbatched.blend')))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=int(os.environ.get('STUDIO_SAMPLES','32'));scene.cycles.use_denoising=False
scene.cycles.max_bounces=7;scene.cycles.diffuse_bounces=4;scene.cycles.glossy_bounces=3;scene.cycles.transmission_bounces=5
scene.render.threads_mode='FIXED';scene.render.threads=8
interior=bpy.data.objects['07_interior'];new=[];removed=[]
for o in list(interior.children):
 if o.name.startswith(('sofa','coffee')) or o.name=='table foot':removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
# Preserve legacy terrace geometry in the asset for provenance, but omit the
# rough furnishing from this focused interior view and its light bake.
legacy_cache={}
for o in list(bpy.data.objects['06_facade'].children):
 if o.type=='MESH' and o.name.startswith(('outdoor','terrace table')):
  for i,m in enumerate(list(o.data.materials)):
   if not m:continue
   if m.name not in legacy_cache:
    hidden=m.copy();hidden.name='legacy terrace furniture / '+m.name;hidden.diffuse_color=(*hidden.diffuse_color[:3],0);hidden.surface_render_method='DITHERED';hidden.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=0;legacy_cache[m.name]=hidden
   o.data.materials[i]=legacy_cache[m.name]
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
rng=np.random.default_rng(28);yy,xx=np.mgrid[0:512,0:512];tone=.82+.024*np.sin(yy*.071+np.sin(xx*.022)*2)+.014*np.sin(yy*.31+xx*.011)+rng.normal(0,.006,(512,512))
for k in range(125):
 cx,cy=rng.uniform(0,512,2);rx,ry=rng.uniform(1,5),rng.uniform(.3,1.0);d=((xx-cx)/rx)**2+((yy-cy)/ry)**2;tone-=np.exp(-d*2)*rng.uniform(.018,.055)
pix=np.ones((512,512,4),np.float32);pix[:,:,:3]=np.clip(tone,0,1)[:,:,None]*np.array([1,.975,.93]);image=bpy.data.images.new('studio mineral limestone',width=512,height=512,alpha=True);image.pixels.foreach_set(pix.ravel());image.filepath_raw=str(A/'limestone-albedo.png');image.file_format='PNG';image.save()
nt=stone.node_tree;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image;bs=nt.nodes.get('Principled BSDF');nt.links.new(tex.outputs['Color'],bs.inputs['Base Color']);bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.15;bump.inputs['Distance'].default_value=.0007;nt.links.new(tex.outputs['Color'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
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
# Use a licensed, artist-authored sofa rather than another collection of boxes.
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'references/GlamVelvetSofa.glb'));imported=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
for o in imported:
 world=o.matrix_world.copy();o.parent=None;o.matrix_world=Matrix.Rotation(math.pi,4,'Z')@world
bpy.context.view_layer.update();points=[o.matrix_world@Vector(v)for o in imported for v in o.bound_box];mn=Vector([min(v[k]for v in points)for k in range(3)]);mx=Vector([max(v[k]for v in points)for k in range(3)]);center=(mn+mx)/2;scale=min(2.68/(mx.x-mn.x),1.015/(mx.y-mn.y));offset=Vector((4.8,-3.5,.055))-Vector((center.x*scale,center.y*scale,mn.z*scale))
velvet=bpy.data.materials['GlamVelvetSofa_fabric_gray'];velvet.name='licensed tailored velvet / warm grey';bs=velvet.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.26,.235,.20,1);bs.inputs['Roughness'].default_value=.82
for n in velvet.node_tree.nodes:
 if n.type=='UVMAP':n.uv_map='UVMap'
for o in imported:
 o.scale*=scale;o.location=o.location*scale+offset;o.parent=interior;o.name='licensed sofa '+o.name;new.append(o)
 if o.data.uv_layers:o.data.uv_layers[0].name='UVMap'
 if any('fabric' in m.name.lower() for m in o.data.materials if m):o.data.materials.clear();o.data.materials.append(velvet)
# Pinched, puffed cloth forms with a real sewn perimeter, not rounded cubes.
def cushion(name,position,color,angle):
 m=material(name+' linen',color,.96);n=32;verts=[];uvs=[];faces=[]
 for side in [-1,1]:
  for j in range(n+1):
   v=j/n*2-1
   for i in range(n+1):
    u=i/n*2-1;bulge=max(0,(1-u*u)*(1-v*v))**.43;xx=u*.215*(1-.15*abs(v)**8);zz=v*.205*(1-.15*abs(u)**8);edge=max(abs(u),abs(v));fold=.0035*math.sin(19*u+6*v)*math.sin(11*v-3*u)*max(0,(edge-.5)*2);yy=side*(.012+.068*bulge+fold);verts.append((xx,yy,zz));uvs.append(((u+1)/2,(v+1)/2))
 count=(n+1)**2
 for side in range(2):
  off=side*count
  for j in range(n):
   for i in range(n):
    a=off+j*(n+1)+i;f=(a,a+1,a+n+2,a+n+1);faces.append(tuple(reversed(f)) if side else f)
 edge=[i for i in range(n+1)]+[j*(n+1)+n for j in range(1,n+1)]+[n*(n+1)+i for i in range(n-1,-1,-1)]+[j*(n+1)for j in range(n-1,0,-1)]
 for k,a in enumerate(edge):b=edge[(k+1)%len(edge)];faces.append((a,b,b+count,a+count))
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges),'Pillow must be a closed manifold';assert bm.calc_volume(signed=True)>0,'Pillow normals must face out';bm.to_mesh(mesh);bm.free();layer=mesh.uv_layers.new(name='UVMap')
 for po in mesh.polygons:
  for li in po.loop_indices:layer.data[li].uv=uvs[mesh.loops[li].vertex_index]
 o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);finish(o,name,m);o.location=position;o.rotation_euler=angle
 # Keep the seam part of the same transforming cushion.
 pts=[verts[i] for i in edge];sewing=pipe(name+' perimeter seam',pts,m,.0012);sewing.location=position;sewing.rotation_euler=angle
 return o
cushion('studio clay scatter cushion',(3.97,-3.69,.65),(.38,.17,.085),(.24,.05,.12))
cushion('studio ivory scatter cushion',(5.57,-3.69,.65),(.70,.65,.54),(.17,-.04,-.10))
# Quiet, sub-millimetre floor joints rather than a dark graphic grid.
jointmat=material('studio quiet timber joints',(.35,.30,.23),.9)
for o in list(interior.children):
 if o.type=='MESH' and o.name.startswith(('floor micro joint','floor end joint')):
  if o.name.startswith('floor micro joint'):o.dimensions.x=.0007
  else:o.dimensions.y=.0007
  o.dimensions.z=.0004;o.location.z=.0504;o.data.materials.clear();o.data.materials.append(jointmat)
box('studio fitted woven rug',(4.73,-2.83,.067),(3.40,2.42,.018),rugmat,.012)
# Same coffee-table position and footprint, improved edge and pedestal construction.
for name,rad,depth,z,m in [('studio coffee stone top',.504,.065,.405,stone),('studio coffee oak pedestal',.19,.335,.233,bpy.data.materials['light oak'])]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=rad,depth=depth,location=(4.8,-2.15,z));o=bpy.context.object;finish(o,name,m);be=o.modifiers.new('soft machined edge','BEVEL');be.width=.009;be.segments=4;o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
for i in range(36):
 a=i*2*math.pi/36;x=4.8+math.cos(a)*.184;y=-2.15+math.sin(a)*.184
 bpy.ops.mesh.primitive_cylinder_add(vertices=10,radius=.0095,depth=.30,location=(x,y,.225));finish(bpy.context.object,'studio coffee pedestal timber flute',bpy.data.materials['light oak'])
box('studio coffee book pages',(4.77,-2.15,.454),(.225,.306,.029),pages,.003)
for z in [.438,.470]:box('studio coffee book cloth cover',(4.77,-2.15,z),(.231,.312,.004),cover,.002)
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=1,location=(5.07,-2.3,.498));bowl=bpy.context.object;bm=bmesh.new();bm.from_mesh(bowl.data);bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.z>.001],context='VERTS');bm.to_mesh(bowl.data);bm.free();bowl.scale=(.12,.12,.06);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);finish(bowl,'studio handmade ceramic bowl',ceramic);solid=bowl.modifiers.new('ceramic wall and real open rim','SOLIDIFY');solid.thickness=.004;solid.offset=-1
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
opaque.data.uv_layers[0].name='UVMap'
while len(opaque.data.uv_layers)>1:opaque.data.uv_layers.remove(opaque.data.uv_layers[-1])
opaque.data.uv_layers.new(name='LightMap');opaque.data.uv_layers.active_index=1;opaque.data.uv_layers[0].active_render=True
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
manifest={'source':str(SOURCE),'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'removedObjects':removed,'newFurnitureAuthoringParts':len(new),'atlas':size,'samples':scene.cycles.samples,'camera':{'position':[3.65,1.4,1.65],'target':[4.8,.65,3.48]},'fixedDaylight':True,'geometryScope':'existing house and plan, replacement sofa and coffee table at original centres; dedicated quality study','notProductionReady':True}
(P/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('QUALITY_ASSETS_EXPORTED',flush=True)
