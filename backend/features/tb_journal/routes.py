"""Safety journal records belong to one stored company and project."""
import json
from fastapi import Depends, Request

COLUMNS = 'id,project_name,master_name,instructor,instruction_type,program,instruction_text,participants_json,photo_url,date,ai_filled,created_at,company_id,project_id'


def serialize(row):
    try:
        participants = json.loads(row[7]) if row[7] else []
    except (ValueError, TypeError):
        participants = []
    return {'id':row[0],'projectName':row[1] or '', 'masterName':row[2] or '',
        'instructor':row[3] or '', 'instructionType':row[4] or '', 'program':row[5] or '',
        'instructionText':row[6] or '', 'participants':participants if isinstance(participants,list) else [],
        'photoUrl':row[8] or '', 'date':str(row[9]) if row[9] else '', 'aiFilled':bool(row[10]),
        'createdAt':str(row[11]), 'companyId':row[12], 'projectId':row[13]}


def register_tb_journal(app, scope, authenticated, read_roles, write_roles, delete_roles):
    @app.get('/tb-journal')
    def list_entries(project_name: str = None, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user,request,read_roles) as (cur,actors):
            where,params=scope.visible(actors,read_roles)
            if project_name:
                where+=' AND p.name=%s';params.append(project_name)
            columns=','.join('p.name' if col=='project_name' else 'r.'+col for col in COLUMNS.split(','))
            cur.execute('SELECT '+columns+' FROM tb_journal r JOIN projects p '
                'ON p.id=r.project_id AND p.company_id=r.company_id WHERE '+where+' ORDER BY r.id DESC',params)
            return [serialize(row) for row in cur.fetchall()]

    @app.post('/tb-journal')
    def create_entry(data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user,request,write_roles,write=True) as (cur,actors):
            actor=actors[0];parent=scope.parent(cur,actor,data,write_roles)
            cur.execute('''INSERT INTO tb_journal(project_name,master_name,instructor,instruction_type,
                program,instruction_text,participants_json,photo_url,date,ai_filled,company_id,project_id,created_by_user_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING '''+COLUMNS,
                (parent['name'],data.get('masterName',''),data.get('instructor',''),
                 data.get('instructionType','Первичный инструктаж'),data.get('program',''),
                 data.get('instructionText',''),json.dumps(data.get('participants') or [],ensure_ascii=False),
                 data.get('photoUrl',''),data.get('date') or None,bool(data.get('aiFilled',False)),
                 parent['companyId'],parent['id'],actor['id']))
            saved=serialize(cur.fetchone())
        return dict(saved,ok=True)

    @app.delete('/tb-journal/{id}')
    def delete_entry(id: int, current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user,request,delete_roles,write=True) as (cur,actors):
            scope.record(cur,actors[0],'tb_journal',id,delete_roles)
            cur.execute('DELETE FROM tb_journal WHERE id=%s',(id,))
        return {'ok':True}
