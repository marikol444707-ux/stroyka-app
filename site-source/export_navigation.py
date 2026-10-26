"""Derive horizontal collision polygons from the existing, unbatched model."""
import bpy,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(P/'unbatched-polished.blend'))
deps=bpy.context.evaluated_depsgraph_get()
def hull(points):
    points=sorted(set(points))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[];hi=[]
    for p in points:
        while len(lo)>1 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(points):
        while len(hi)>1 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return lo[:-1]+hi[:-1]
colliders=[]
for o in bpy.context.scene.objects:
    if not o.parent or o.type not in ('MESH','CURVE'):continue
    group=o.parent.name
    if group not in ('03_walls','07_interior','09_wall_core','10_insulation','11_vent_gap','12_cladding','13_inner_finish'):continue
    ev=o.evaluated_get(deps);mesh=ev.to_mesh()
    vertices=[o.matrix_world@v.co for v in mesh.vertices]
    if not vertices:ev.to_mesh_clear();continue
    zmin=min(v.z for v in vertices);zmax=max(v.z for v in vertices)
    # Walkable floor/rug details and elements above head height do not obstruct.
    if zmax<.20 or zmin>1.78:ev.to_mesh_clear();continue
    poly=hull([(round(v.x,4),round(-v.y,4)) for v in vertices])
    if len(poly)>=3:
        colliders.append({'name':o.name,'group':group,'polygon':poly,'height':[round(zmin,4),round(zmax,4)]})
    ev.to_mesh_clear()
rooms=[
 {'id':'living','title':'Кухня-гостиная','point':[2.65,4.05],'yaw':0,'description':'Общее пространство с выходом на террасу. Мебель и проходы пока предложены для обсуждения.'},
 {'id':'hall','title':'Коридор','point':[-.75,.15],'yaw':1.57,'description':'Соединяет три спальни и общее пространство. Проверьте удобство маршрутов для вашей семьи.'},
 {'id':'bedroom1','title':'Спальня 1','point':[-3.55,3.05],'yaw':1.57,'description':'Предложение спальни с двуспальной кроватью и местом хранения.'},
 {'id':'bedroom2','title':'Спальня 2','point':[-3.55,0],'yaw':1.57,'description':'Комната с односпальной кроватью. Назначение и мебель можно обсудить после выбора планировки.'},
 {'id':'bedroom3','title':'Спальня 3','point':[-3.55,-3.05],'yaw':1.57,'description':'Третья спальня в этом эскизе. Распределение комнат между членами семьи не утверждено.'},
 {'id':'bath','title':'Санузел','point':[1.5,-2.25],'yaw':0,'description':'Показано примерное расположение сантехники. Эргономика и инженерные подключения требуют проверки.'},
 {'id':'utility','title':'Хозпомещение','point':[3.65,-2.4],'yaw':0,'description':'Зона хозяйственного оборудования. Состав оборудования и требования к помещению предстоит согласовать.'},
 {'id':'office','title':'Кабинет','point':[5.7,-2.25],'yaw':0,'description':'Рабочее место в отдельной комнате. Возможность другого назначения обсудим с проектировщиком.'}
]
# Initial room views face the actual bed, with a modest downward look.
import math
layout=json.loads((P/'furniture-layout.json').read_text())
for bed in layout['bedrooms']:
 r=next(r for r in rooms if r['id']==bed['id'])
 dx=bed['center'][0]-r['point'][0];dz=bed['center'][1]-r['point'][1]
 r['yaw']=math.atan2(-dx,-dz);r['pitch']=math.atan2(.83-1.705,math.hypot(dx,dz))
data={'version':1,'source':'unbatched-polished.blend','units':'metres','radius':.22,'eyeHeight':1.65,'floorHeight':.055,'modelSha256':hashlib.sha256((P/'stroyka-polished.glb').read_bytes()).hexdigest(),'bounds':[-6.85,6.85,-4.85,4.85],'colliders':colliders,'rooms':rooms}
(P/'navigation.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
print('COLLISION_POLYGONS',len(colliders))
