"""Customer approval of published terms, separate from editing and execution."""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request

ROLES = ('заказчик',)
PENDING = 'Ожидает согласования'
DECISIONS = {'approve': 'Утверждено отдельной допработой', 'reject': 'Отклонено'}
FIELDS = ('id', 'company_id', 'project_id', 'project_name', 'description', 'unit',
          'quantity', 'price', 'total', 'change_type', 'reason', 'estimate_id',
          'section_name', 'estimate_item_name', 'base_quantity', 'new_required_quantity',
          'delta_quantity', 'included_in_estimate_id')


def revision(row):
    value = json.dumps({key: row[key] for key in FIELDS}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(value.encode()).hexdigest()


def register_customer_extra_works(app, scope, authenticated):
    def read(cur, actors, row_id=None, lock=False):
        where, params = scope.visible(actors, ROLES)
        fields = (*FIELDS, 'status', 'approved_by', 'approved_at')
        if row_id is not None:
            where += ' AND r.id=%s'; params = [*params, row_id]
        cur.execute('SELECT ' + ','.join('r.' + field for field in fields)
                    + ' FROM unexpected_works r JOIN projects p ON p.id=r.project_id '
                    'AND p.company_id=r.company_id WHERE ' + where
                    + ' ORDER BY r.id DESC' + (' FOR UPDATE OF r,p' if lock else ''), params)
        return [dict(zip(fields, row)) for row in cur.fetchall()]

    @app.get('/unexpected-works/customer-visible')
    def list_offers(current_user: dict = Depends(authenticated), request: Request = None):
        with scope.transaction(current_user, request, ROLES) as (cur, actors):
            result = []
            for row in read(cur, actors):
                if row['status'] not in (PENDING, 'Утверждено', *DECISIONS.values()):
                    continue
                result.append({
                    'id': row['id'], 'companyId': row['company_id'], 'projectId': row['project_id'],
                    'projectName': row['project_name'], 'description': row['description'],
                    'unit': row['unit'], 'quantity': row['quantity'], 'price': row['price'],
                    'total': row['total'], 'changeType': row['change_type'], 'reason': row['reason'],
                    'status': row['status'], 'approvedBy': row['approved_by'], 'approvedAt': row['approved_at'],
                    'addedBy': 'Подрядчик', 'revision': revision(row),
                })
            return result

    @app.post('/unexpected-works/{id}/customer-decision')
    def decide(id: int, data: dict, current_user: dict = Depends(authenticated), request: Request = None):
        if (set(data) != {'decision', 'revision'} or not isinstance(data.get('decision'), str)
                or data['decision'] not in DECISIONS or not isinstance(data.get('revision'), str)):
            raise HTTPException(status_code=422, detail='Укажите решение и версию предложения')
        with scope.transaction(current_user, request, ROLES, write=True) as (cur, actors):
            rows = read(cur, actors, id, lock=True)
            if not rows:
                raise HTTPException(status_code=404, detail='Предложение не найдено в доступном объекте')
            row, actor = rows[0], actors[0]
            if revision(row) != data['revision']:
                raise HTTPException(status_code=409, detail='Условия предложения изменились. Обновите страницу перед решением.')
            status = DECISIONS[data['decision']]
            evidence = json.dumps(data, sort_keys=True)
            if row['status'] != PENDING:
                cur.execute("SELECT 1 FROM audit_log WHERE entity_type='unexpected_work' AND entity_id=%s "
                            "AND action='customer_decision' AND company_id=%s AND project_id=%s "
                            'AND user_id=%s AND description=%s LIMIT 1',
                            (id,row['company_id'],row['project_id'],actor['id'],evidence))
                if row['status'] == status and cur.fetchone():
                    return {'ok': True, 'status': status}
                raise HTTPException(status_code=409, detail='По предложению уже принято решение. Обновите страницу.')
            cur.execute('UPDATE unexpected_works SET status=%s,approved_by=%s,approved_at=%s WHERE id=%s',
                        (status,actor.get('name',''),datetime.now(ZoneInfo('Europe/Moscow')).date().isoformat(),id))
            cur.execute('INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,'
                        'description,project_name,owner_scope,company_id,project_id) '
                        "VALUES(%s,%s,'заказчик','customer_decision','unexpected_work',%s,%s,%s,'company',%s,%s)",
                        (actor['id'],actor.get('name',''),id,evidence,row['project_name'],row['company_id'],row['project_id']))
        return {'ok': True, 'status': status}
