"""Version reads require the saved owner and a currently accessible typed parent."""
import json

from fastapi import Depends, HTTPException, Request

EXTERNAL_ROLES = frozenset(('заказчик', 'мастер', 'субподрядчик', 'бригадир'))
PUBLIC_FIELDS = frozenset(('act_number', 'work_name', 'section_name', 'quantity',
    'unit', 'work_date', 'conclusion', 'city', 'status'))


def owned_snapshot(raw, document_id, company_id, project_name, journal_id, work_package):
    """The server's row_to_json snapshot is evidence; never guess a legacy owner."""
    try:
        snapshot = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    if not isinstance(snapshot, dict):
        return None
    if (type(snapshot.get('id')) is not int or snapshot['id'] != document_id
            or type(snapshot.get('company_id')) is not int
            or snapshot['company_id'] != company_id
            or snapshot.get('project_name') != project_name
            or snapshot.get('work_journal_id') != journal_id
            or (snapshot.get('work_package') or 'Основная') != (work_package or 'Основная')):
        return None
    return snapshot


def register_document_versions_module(app, deps):
    scope = deps['record_scope']
    authenticated = deps['get_current_user']
    roles = tuple(deps['project_document_roles'])
    package_filter = deps['package_access_filter']

    def read(cur, actors, *, version_id=None, document_type=None, document_id=None, detail=False):
        clauses, params = [], []
        for actor in actors:
            where, values = scope.visible([actor], roles)
            package_sql, package_params = package_filter(actor, 'h.work_package')
            where += package_sql
            values = [*values, *package_params]
            if actor.get('role') in EXTERNAL_ROLES:
                where += " AND w.status='Подтверждено' AND COALESCE(h.status,'') NOT IN ('Аннулирован','Аннулировано')"
                if actor.get('role') != 'заказчик':
                    where += ' AND w.master_id=%s'
                    values.append(actor['id'])
            clauses.append('(' + where + ')')
            params.extend(values)
        query = ("SELECT v.id,v.document_type,v.document_id,v.version_label,v.snapshot_json,"
                 "v.changed_by,v.change_reason,v.created_at,h.company_id,h.project_name,h.work_journal_id,h.work_package "
                 "FROM document_versions v JOIN hidden_works_acts h "
                 "ON v.document_type='hidden_works_act' AND h.id=v.document_id "
                 "JOIN projects p ON p.company_id=h.company_id AND p.name=h.project_name "
                 "LEFT JOIN work_journal w ON w.id=h.work_journal_id AND w.company_id=h.company_id "
                 "AND w.project=h.project_name WHERE (" + (' OR '.join(clauses) or 'FALSE') + ')'
                 ' AND NOT EXISTS (SELECT 1 FROM projects other WHERE other.company_id=p.company_id '
                 'AND other.name=p.name AND other.id<>p.id)')
        for column, value in [('v.id', version_id), ('v.document_type', document_type), ('v.document_id', document_id)]:
            if value is not None:
                query += ' AND ' + column + '=%s'
                params.append(value)
        cur.execute(query + ' ORDER BY v.created_at DESC,v.id DESC LIMIT 200', params)
        external = any(actor.get('role') in EXTERNAL_ROLES for actor in actors)
        result = []
        for row in cur:
            snapshot = owned_snapshot(row[4], row[2], row[8], row[9], row[10], row[11])
            if snapshot is None:
                continue
            item = dict(id=row[0], documentType=row[1], documentId=row[2], versionLabel=row[3],
                        changedBy='' if external else row[5] or '',
                        changeReason='' if external else row[6] or '', createdAt=str(row[7]))
            if detail:
                item['snapshot'] = ({k: v for k, v in snapshot.items() if k in PUBLIC_FIELDS
                                     and not isinstance(v, (dict, list))} if external else snapshot)
            result.append(item)
            if len(result) >= 200:
                break
        return result

    @app.get('/document-versions')
    def list_document_versions(document_type: str = None, document_id: int = None,
                               request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user, request, roles) as (cur, actors):
            return read(cur, actors, document_type=document_type, document_id=document_id)

    @app.get('/document-versions/{vid}')
    def get_document_version(vid: int, request: Request = None, _current_user: dict = Depends(authenticated)):
        with scope.transaction(_current_user, request, roles) as (cur, actors):
            rows = read(cur, actors, version_id=vid, detail=True)
            if not rows:
                raise HTTPException(404, 'Версия документа не найдена')
            return rows[0]
