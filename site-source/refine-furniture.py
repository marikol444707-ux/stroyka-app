"""Refine existing furniture only; wall/roof/window/door layout stays intact."""
from pathlib import Path
import math,json,bpy
from mathutils import Matrix,Vector
P=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(P/'base-interior.blend'))
layout=json.loads((P/'furniture-layout.json').read_text());g=bpy.data.objects['07_interior'];changed=[]
def move(o,m):o.matrix_world=m@o.matrix_world;changed.append(o.name)
c=Vector((4.8,-3.5,0));rotation=Matrix.Translation(c)@Matrix.Rotation(math.pi,4,'Z')@Matrix.Translation(-c)
for o in list(g.children):
 if o.name.startswith('sofa'):move(o,rotation)
old=Vector((4.7,-2.35,0));new=Vector((layout['coffee']['x'],-layout['coffee']['z'],0))
transform=Matrix.Translation(new)@Matrix.Diagonal((.9,.9,1,1))@Matrix.Translation(-old)
for o in list(g.children):
 if o.name.startswith('coffee') or o.name=='table foot':move(o,transform)
old=Vector((5.7,-.75,0));new=Vector((layout['dining']['x'],-layout['dining']['z'],0))
for o in list(g.children):
 if o.name.startswith('dining'):
  move(o,Matrix.Translation(new)@Matrix.Diagonal((.65/.75,.65/.75,1,1))@Matrix.Translation(-old))
 elif o.name.startswith('chair'):
  # Move each complete chair radially without distorting seat/leg dimensions.
  seatcenter=min([Vector((6.75,-.75,0)),Vector((5.7,.3,0)),Vector((4.65,-.75,0)),Vector((5.7,-1.8,0))],key=lambda c:(o.location.xy-c.xy).length)
  r=Matrix.Rotation(math.pi/4,4,'Z');target=new+r@(seatcenter-old)*(.95/1.05);move(o,Matrix.Translation(target)@r@Matrix.Translation(-seatcenter))
 elif o.name.startswith('pendant') and abs(o.location.x-5.7)<.02:
  move(o,Matrix.Translation(new-old))

def finish(o,name,mat,bevel=0):
 o.name=name;o.parent=g;o.data.materials.append(bpy.data.materials[mat])
 if bevel:
  mod=o.modifiers.new('soft edge','BEVEL');mod.width=bevel;mod.segments=4
  o.modifiers.new('weighted corner normals','WEIGHTED_NORMAL')
 return o
def box(name,location,dimensions,mat,bevel):
 bpy.ops.mesh.primitive_cube_add(size=1,location=location);o=bpy.context.object;o.dimensions=dimensions;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(o,name,mat,bevel)
for seat in [o for o in g.children if o.name.startswith('chair seat')]:
 x,y=seat.location.x,seat.location.y;d=Vector((x-new.x,y-new.y,0)).normalized();right=Vector((-d.y,d.x,0));vertices=[];uv=[]
 for row,h in enumerate([.5,.74,.98]):
  for j in range(13):
   a=-.85+j*1.7/12;v=Vector((x,y,h))+(d*math.cos(a)+right*math.sin(a))*(.225+.035*row/2);vertices.append(tuple(v));uv.append((j/12,row/2))
 faces=[(row*13+j,row*13+j+1,(row+1)*13+j+1,(row+1)*13+j) for row in range(2) for j in range(12)]
 mesh=bpy.data.meshes.new('curved chair back');mesh.from_pydata(vertices,[],faces);mesh.update();layer=mesh.uv_layers.new()
 for poly in mesh.polygons:
  poly.use_smooth=True
  for index in poly.loop_indices:layer.data[index].uv=uv[mesh.loops[index].vertex_index]
 o=bpy.data.objects.new('dining curved chair back',mesh);bpy.context.collection.objects.link(o);finish(o,o.name,'oak');solid=o.modifiers.new('plywood shell','SOLIDIFY');solid.thickness=.025;bevel=o.modifiers.new('rounded shell edge','BEVEL');bevel.width=.008;bevel.segments=3
 pad=box('dining chair soft seat',(x,y,.492),(.415,.415,.045),'sage',.025);pad.rotation_euler.z=math.pi/4

for old_duvet in [o for o in g.children if o.name.startswith('duvet')]:bpy.data.objects.remove(old_duvet,do_unlink=True)
for mattress in [o for o in g.children if o.name.startswith('mattress')]:
 cx,cy=mattress.location.x,mattress.location.y;width=float(mattress.dimensions.x)-.06;length=1.48;centerY=cy-.23;verts=[];uv=[];nx=30;ny=32
 # Lightly irregular soft duvet, above the existing mattress and within its footprint.
 for j in range(ny+1):
  v=j/ny
  for i in range(nx+1):
   u=i/nx;x=cx+(u-.5)*width;y=centerY+(v-.5)*length
   height=.624+.018*math.sin(math.pi*u)*math.sin(math.pi*v)+.006*math.sin(u*math.pi*13+v*4)+.003*math.sin(v*math.pi*9)
   verts.append((x,y,height));uv.append((u,v))
 faces=[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)]
 mesh=bpy.data.meshes.new('soft duvet folds');mesh.from_pydata(verts,[],faces);mesh.update();layer=mesh.uv_layers.new()
 for poly in mesh.polygons:
  poly.use_smooth=True
  for index in poly.loop_indices:layer.data[index].uv=uv[mesh.loops[index].vertex_index]
 o=bpy.data.objects.new('bed soft duvet',mesh);bpy.context.collection.objects.link(o);finish(o,o.name,'linen');solid=o.modifiers.new('duvet edge thickness','SOLIDIFY');solid.thickness=.035
 # A folded accent at the foot; all additions remain over the current bed.
 box('bed foot throw',(cx,cy-.68,.65),(width,.34,.035),'sage',.016)
for o in [o for o in g.children if o.name.startswith('headboard')]:
 o.data.materials.clear();o.data.materials.append(bpy.data.materials['fabric']);changed.append(o.name)
 for i in range(1,6):
  x=o.location.x-float(o.dimensions.x)/2+i*float(o.dimensions.x)/6
  box('headboard upholstered channel',(x,o.location.y-.055,.7),(.012,.012,.76),'linen',.005)
# Pack source images so the saved Blender files can be moved with the package.
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(P/'stroyka-polished.blend'))
(P/'furniture-changes.json').write_text(json.dumps({'changed':changed,'scope':'Furniture only; source building surfaces are checked against v17 after export.','layout':layout},indent=2))
print('FURNITURE_REFINED',len(changed))
