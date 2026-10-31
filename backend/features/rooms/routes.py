"""Room measurements with explicit owner identity; legacy unassigned rows stay private."""
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel


class RoomModel(BaseModel):
    projectId: int | None = None
    floor: int = 1
    liter: str = ''
    roomType: str = 'Комната'
    project: str
    name: str
    floorArea: float = 0
    wallArea: float = 0
    ceilingArea: float = 0
    height: float = 0
    ceilingType: str = "Простой"
    wallMaterial: str = "Штукатурка"
    floorMaterial: str = "Стяжка"
    windows: int = 0
    doors: int = 0
    photoUrl: str = ""
    notes: str = ""


ROOM_FIELDS = {
    'name':'name', 'floorArea':'floor_area', 'wallArea':'wall_area', 'ceilingArea':'ceiling_area',
    'height':'height', 'ceilingType':'ceiling_type', 'wallMaterial':'wall_material',
    'floorMaterial':'floor_material', 'windows':'windows', 'doors':'doors', 'photoUrl':'photo_url',
    'notes':'notes', 'floor':'floor', 'liter':'liter', 'roomType':'room_type',
}


def register_rooms_module(app, deps):
    scope = deps['record_scope']
    authenticated = deps['get_current_user']
    read_roles = tuple(deps['read_roles'])
    write_roles = tuple(deps['write_roles'])
    recalculate = deps['run_project_ai_control_safely']

    def room(cur, actors, room_id, roles, *, lock=False):
        where, params = scope.visible(actors, roles)
        cur.execute('SELECT r.id,p.name FROM rooms r JOIN projects p '
                    'ON p.id=r.project_id AND p.company_id=r.company_id WHERE r.id=%s AND ' + where +
                    (' FOR UPDATE OF r,p' if lock else ''), (room_id,*params))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Помещение не найдено в доступном объекте')
        return row

    @app.get('/rooms')
    def get_rooms(request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, read_roles) as (cur, actors):
            where, params = scope.visible(actors, read_roles)
            cur.execute('SELECT r.id,p.name,r.project_id,r.company_id,' + ','.join('r.'+c for c in ROOM_FIELDS.values()) +
                        ' FROM rooms r JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id WHERE ' + where + ' ORDER BY r.id', params)
            rows = cur.fetchall()
        return [dict(zip(('id','project','projectId','companyId',*ROOM_FIELDS),row)) for row in rows]

    @app.post('/rooms')
    def create_room(r: RoomModel, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            parent = scope.parent(cur, actors[0], {'projectId':r.projectId,'projectName':r.project}, write_roles)
            values = [parent['id'],parent['companyId'],parent['name'],*[getattr(r,k) for k in ROOM_FIELDS]]
            cur.execute('INSERT INTO rooms (project_id,company_id,project,' + ','.join(ROOM_FIELDS.values()) + ') VALUES (' +
                        ','.join(['%s']*len(values)) + ') RETURNING id', values)
            record_id = cur.fetchone()[0]
        recalculate(parent['name'], 'room:create')
        return {'id':record_id, **r.model_dump(), **{column: getattr(r, field) for field, column in ROOM_FIELDS.items()},
                'company_id':parent['companyId'], 'project_id':parent['id'],
                'companyId':parent['companyId'],'projectId':parent['id'],'project':parent['name']}

    @app.put('/rooms/{id}')
    def update_room(id: int, r: RoomModel, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            room(cur, actors, id, write_roles, lock=True)
            parent = scope.parent(cur, actors[0], {'projectId':r.projectId,'projectName':r.project}, write_roles)
            cur.execute('UPDATE rooms SET project_id=%s,company_id=%s,project=%s,' +
                        ','.join(c+'=%s' for c in ROOM_FIELDS.values())+' WHERE id=%s',
                        (parent['id'],parent['companyId'],parent['name'],*[getattr(r,k) for k in ROOM_FIELDS],id))
        recalculate(parent['name'], 'room:update')
        return {'ok':True}

    @app.delete('/rooms/{id}')
    def delete_room(id: int, request: Request, current_user: dict = Depends(authenticated)):
        with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
            room(cur, actors, id, write_roles, lock=True)
            for table in ('room_windows','room_doors','room_works'):
                cur.execute('DELETE FROM '+table+' WHERE room_id=%s', (id,))
            cur.execute('DELETE FROM rooms WHERE id=%s', (id,))
        return {'ok':True}

    def register_child(path, table, fields):
        # table/fields are fixed registration constants, never request input.
        def child(cur, actors, record_id):
            where, params = scope.visible(actors, write_roles)
            cur.execute('SELECT c.room_id FROM '+table+' c JOIN rooms r ON r.id=c.room_id '
                        'JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id '
                        'WHERE c.id=%s AND '+where+' FOR UPDATE OF c,r,p', (record_id,*params))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, 'Запись не найдена в доступном помещении')
            return row[0]

        def values(data):
            return [convert(data.get(camel, data.get(column, default))) for column,camel,default,convert in fields]

        @app.get(path)
        def read(request: Request, current_user: dict = Depends(authenticated)):
            with scope.transaction(current_user, request, read_roles) as (cur, actors):
                where, params = scope.visible(actors, read_roles)
                cur.execute('SELECT c.id,c.room_id,'+','.join('c.'+f[0] for f in fields)+' FROM '+table+
                            ' c JOIN rooms r ON r.id=c.room_id JOIN projects p ON p.id=r.project_id '
                            'AND p.company_id=r.company_id WHERE '+where+' ORDER BY c.id', params)
                rows = cur.fetchall()
            return [dict(zip(('id','room_id',*[f[0] for f in fields]),row)) for row in rows]

        @app.post(path)
        def create(data: dict, request: Request, current_user: dict = Depends(authenticated)):
            with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
                parent = room(cur, actors, data.get('roomId') or data.get('room_id'), write_roles, lock=True)
                parameters = [parent[0],*values(data)]
                cur.execute('INSERT INTO '+table+' (room_id,'+','.join(f[0] for f in fields)+') VALUES ('+
                            ','.join(['%s']*len(parameters))+') RETURNING *', parameters)
                result = cur.fetchone()
            recalculate(parent[1], table[:-1]+':create')
            return result

        @app.put(path+'/{id}')
        def update(id: int, data: dict, request: Request, current_user: dict = Depends(authenticated)):
            with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
                old_parent = child(cur, actors, id)
                parent = room(cur, actors, data.get('roomId') or data.get('room_id') or old_parent, write_roles, lock=True)
                cur.execute('UPDATE '+table+' SET room_id=%s,'+','.join(f[0]+'=%s' for f in fields)+' WHERE id=%s',
                            (parent[0],*values(data),id))
            recalculate(parent[1], table[:-1]+':update')
            return {'ok':True}

        @app.delete(path+'/{id}')
        def delete(id: int, request: Request, current_user: dict = Depends(authenticated)):
            with scope.transaction(current_user, request, write_roles, write=True) as (cur, actors):
                child(cur, actors, id)
                cur.execute('DELETE FROM '+table+' WHERE id=%s', (id,))
            return {'ok':True}

    common = [('name','name','',str),('width','width',0,lambda v: float(v or 0)),('height','height',0,lambda v: float(v or 0))]
    reveals = [('reveal_depth','revealDepth',0,lambda v: float(v or 0)),('reveal_material','revealMaterial','Штукатурка',str),('order_num','orderNum',0,lambda v: int(v or 0))]
    register_child('/room-windows','room_windows',[*common,('window_type','windowType','ПВХ',str),*reveals])
    register_child('/room-doors','room_doors',[*common,('door_type','doorType','Деревянная',str),('door_purpose','doorPurpose','Межкомнатная',str),*reveals])
