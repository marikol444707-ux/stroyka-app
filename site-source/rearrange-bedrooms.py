"""Rearrange existing bed assemblies against solid partition walls only."""
from pathlib import Path
import bpy,math,json
from mathutils import Matrix,Vector
P=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(P/'previous-interior.blend'))
g=bpy.data.objects['07_interior'];rows=[]
config=[
 {'id':'bedroom1','oldZ':3.15,'z':2.75,'angle':0,'table':[-4.3,2.05],'oldTable':[-4.3,2.45],'rugZ':2.95,'rugDepth':2.45},
 {'id':'bedroom2','oldZ':0,'z':.35,'angle':math.pi,'table':[-4.5,1.05],'oldTable':[-4.3,-.7],'rugZ':.05,'rugDepth':2.7},
 {'id':'bedroom3','oldZ':-3.1,'z':-2.75,'angle':math.pi,'table':[-4.3,-2.05],'oldTable':[-4.3,-3.8],'rugZ':-2.95,'rugDepth':2.45}]
def worldz(o):
 values=[(o.matrix_world@Vector(c)).y for c in o.bound_box]
 return -(min(values)+max(values))/2
def room(z):return min(config,key=lambda c:abs(c['oldZ']-z))
assemblies={c['id']:[] for c in config};tables={c['id']:[] for c in config};rugs={}
for o in list(g.children):
 name=o.name
 if name.startswith('bedside'):tables[room(worldz(o))['id']].append(o)
 elif name.startswith('bedroom rug'):rugs[room(worldz(o))['id']]=o
 elif name.startswith(('bed base','mattress','pillow','headboard','bed soft duvet','bed foot throw')):assemblies[room(worldz(o))['id']].append(o)
for c in config:
 old=Vector((-5.5,-c['oldZ'],0));new=Vector((-5.5,-c['z'],0));rot=Matrix.Rotation(c['angle'],4,'Z');transform=Matrix.Translation(new)@rot@Matrix.Translation(-old)
 for o in assemblies[c['id']]:o.matrix_world=transform@o.matrix_world
 oldt=Vector((c['oldTable'][0],-c['oldTable'][1],0));newt=Vector((c['table'][0],-c['table'][1],0));t=Matrix.Translation(newt)@rot@Matrix.Translation(-oldt)
 for o in tables[c['id']]:o.matrix_world=t@o.matrix_world
 rug=rugs[c['id']];rug.location.y=-c['rugZ'];rug.dimensions.y=c['rugDepth']
 # One ordinary pillow for the single bed, rather than two miniature pillows.
 if c['id']=='bedroom2':
  pillows=sorted([o for o in assemblies[c['id']] if o.name.startswith('pillow')],key=lambda o:o.name)
  assert len(pillows)==2
  pillows[0].location.x=-5.5;pillows[0].dimensions.x=.62;bpy.data.objects.remove(pillows[1],do_unlink=True)
 rows.append({**c,'center':[-5.5,c['z']],'rotatedDegrees':round(c['angle']*180/math.pi),'movedBedParts':len(assemblies[c['id']]),'movedTableParts':len(tables[c['id']]),'solidPartition':1.55 if c['id']=='bedroom1' else 1.55 if c['id']=='bedroom2' else -1.55})
bpy.context.view_layer.update();bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(P/'stroyka-polished.blend'))
layout=json.loads((P/'furniture-layout.json').read_text());layout['version']=2;layout['bedrooms']=[{'id':c['id'],'center':[-5.5,c['z']],'bedside':c['table'],'headDirection':'negative-z' if c['id']=='bedroom1' else 'positive-z','approved':False} for c in config];(P/'furniture-layout.json').write_text(json.dumps(layout,indent=2))
(P/'bedroom-changes.json').write_text(json.dumps({'scope':'Existing bedroom furniture only; building/window/door geometry preserved.','rooms':rows,'ergonomicsApproved':False},indent=2))
print('BEDROOMS_REARRANGED',json.dumps(rows))
