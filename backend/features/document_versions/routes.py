"""Version snapshots require a frozen owner and a currently accessible typed parent."""
import json
from fastapi import Depends, HTTPException, Request

EXTERNAL_ROLES = ('заказчик','мастер','субподрядчик','бригадир')
PUBLIC_FIELDS = frozenset(('actNumber','act_number','workName','work_name','sectionName','section_name',
    'quantity','unit','workDate','work_date','conclusion','city','description','status'))


def visible_snapshot(snapshot, external):
    if not isinstance(snapshot, dict):
        return {} if external else snapshot
    return {key:value for key,value in snapshot.items() if key in PUBLIC_FIELDS and not isinstance(value,(dict,list))} if external else snapshot


def register_document_versions_module(app, deps):
    scope, authenticated = deps['record_scope'], deps['get_current_user']
    roles = tuple(deps['project_document_roles'])

    def read(cur, actors, *, version_id=None, document_type=None, document_id=None, snapshot=False):
        clauses, params = [], []
        for actor in actors:
            where, values = scope.visible([actor], roles)
            if actor.get('role') in EXTERNAL_ROLES:
                where += " AND w.status='Подтверждено' AND COALESCE(h.status,'') NOT IN ('Аннулирован','Аннулировано')"
                if actor.get('role') != 'заказчик':
                    where += ' AND w.master_id=%s';values=[*values,actor.get('id')]
            clauses.append('('+where+')');params.extend(values)
        columns='v.id,v.document_type,v.document_id,v.version_label,'+('v.snapshot_json,' if snapshot else '')+'v.changed_by,v.change_reason,v.created_at'
        query=('SELECT '+columns+' FROM document_versions v '
            "JOIN hidden_works_acts h ON v.document_type='hidden_works_act' AND h.id=v.document_id AND h.company_id=v.company_id "
            'JOIN work_journal w ON w.id=h.work_journal_id AND w.company_id=h.company_id '
            'JOIN projects p ON p.id=v.project_id AND p.company_id=v.company_id AND p.name=w.project AND p.name=h.project_name '
            'WHERE ('+(' OR '.join(clauses) or 'FALSE')+')')
        for column,value in [('v.id',version_id),('v.document_type',document_type),('v.document_id',document_id)]:
            if value is not None:
                query+=' AND '+column+'=%s';params.append(value)
        cur.execute(query+' ORDER BY v.created_at DESC LIMIT 200',params)
        return cur.fetchall()

    @app.get('/document-versions')
    def list_document_versions(document_type: str = None, document_id: int = None, request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user,request,roles) as (cur,actors):
            rows=read(cur,actors,document_type=document_type,document_id=document_id)
        return [dict(zip(('id','documentType','documentId','versionLabel','changedBy','changeReason','createdAt'),(*r[:6],str(r[6])))) for r in rows]

    @app.get('/document-versions/{vid}')
    def get_document_version(vid: int, request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user,request,roles) as (cur,actors):
            rows=read(cur,actors,version_id=vid,snapshot=True)
            if not rows: raise HTTPException(404,'Версия документа не найдена')
            row=rows[0]
            # Mixed effective roles use the restricted projection; an external
            # membership must never obtain a full snapshot through an OR clause.
            external=any(actor.get('role') in EXTERNAL_ROLES for actor in actors)
        try: snapshot=json.loads(row[4]) if isinstance(row[4],str) else (row[4] or {})
        except (ValueError,TypeError): snapshot={}
        return {'id':row[0],'documentType':row[1],'documentId':row[2],'versionLabel':row[3],
                'snapshot':visible_snapshot(snapshot,external),'changedBy':row[5] or '',
                'changeReason':row[6] or '', 'createdAt':str(row[7])}
