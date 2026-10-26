"""Bake details and batch by material, preserving every selectable layer.

Facade categories remain separate because roof-off views hide them by name.
Run after polish_house.py, before build_viewer.py; renders are unaffected.
"""
from pathlib import Path
import bpy,json,shutil
P=Path(__file__).resolve().parent
shutil.copyfile(P/'stroyka-polished.blend',P/'unbatched-polished.blend')
bpy.ops.wm.open_mainfile(filepath=str(P/'stroyka-polished.blend'))
s=bpy.context.scene
before=sum(o.type=='MESH' and o.parent and o.parent.name!='08_landscape' for o in s.objects)
parents=[o for o in s.objects if o.type=='EMPTY' and o.name!='08_landscape']
for parent in parents:
    objects=[o for o in parent.children if o.type in ('MESH','CURVE')]
    if not objects:continue
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    # Convert first: joining meshes directly would discard other objects' bevels.
    bpy.ops.object.convert(target='MESH')
    categories={}
    for o in parent.children:
        if o.type!='MESH':continue
        category=next((p for p in ('south facade','east facade','pergola') if o.name.startswith(p)),'detail')
        key=(category,tuple(m.name for m in o.data.materials))
        categories.setdefault(key,[]).append(o)
    for (category,mats),items in categories.items():
        if len(items)<2:continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in items:o.select_set(True)
        bpy.context.view_layer.objects.active=items[0];bpy.ops.object.join()
        bpy.context.object.name=category+' / '+parent.name+' / '+'-'.join(mats)
after=sum(o.type=='MESH' and o.parent and o.parent.name!='08_landscape' for o in s.objects)
bpy.ops.wm.save_as_mainfile(filepath=str(P/'stroyka-polished.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in s.objects:
    if o.type=='EMPTY' and o.name!='08_landscape':o.select_set(True)
    elif o.parent and o.parent.name!='08_landscape' and o.type=='MESH':o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(P/'stroyka-polished.glb'),use_selection=True,export_apply=True,export_format='GLB')
(P/'model-optimization.json').write_text(json.dumps({'meshes_before':before,'meshes_after':after,'preserved_semantic_layers':[o.name for o in parents]},indent=2))
print('OPTIMIZED',before,after)
