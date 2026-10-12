from fastapi import Depends, Header, HTTPException, Query

from .service import admin_transaction, create_ticket, ready, ticket_view, ADMIN_ROLES
from ..invite_codes.supplier_relationship import directory
from .organization_directory import register_organization_directory
from .connection_preview import register_connection_preview

TRANSITIONS = {
    'new': {'in_progress'}, 'in_progress': {'waiting','resolved'},
    'waiting': {'in_progress'}, 'resolved': {'closed','in_progress'}, 'closed': {'in_progress'},
}


def register_participant_support(app, deps):
    authenticated = deps.get('authenticated') or deps['require_roles'](*deps['admin_roles'])
    admin = deps['require_roles'](*ADMIN_ROLES)
    register_organization_directory(app, deps, admin)
    register_connection_preview(app, deps, admin)

    @app.post('/participant-support/tickets')
    def report(data: dict, user: dict = Depends(authenticated),
               company: str = Header(None,alias='X-Company-Id'),
               mode: str = Header(None,alias='X-Company-Mode')):
        return create_ticket(deps,user,(company,mode),data)

    @app.get('/participant-support/tickets')
    def my_tickets(user: dict = Depends(authenticated),
                   company: str = Header(None,alias='X-Company-Id'),
                   mode: str = Header(None,alias='X-Company-Mode'),
                   offset: int = Query(0,ge=0), limit: int = Query(25,ge=1,le=100)):
        with directory(deps).transaction(user,(company,mode)) as (cur,owner,actor):
            ready(cur)
            cur.execute('''SELECT id,participant_type,participant_id,reason_code,status,result,created_at,updated_at
                FROM participant_access_tickets WHERE company_id=%s AND platform_account_id=%s AND reporter_id=%s
                ORDER BY id DESC LIMIT %s OFFSET %s''', (owner['id'],owner['platform_account_id'],user['id'],limit+1,offset))
            rows = cur.fetchall()
            return dict(items=[ticket_view(row) for row in rows[:limit]],hasMore=len(rows)>limit)

    @app.get('/participant-support/tickets/{ticket_id}')
    def my_detail(ticket_id: int,user: dict = Depends(authenticated),
                  company: str = Header(None,alias='X-Company-Id'),
                  mode: str = Header(None,alias='X-Company-Mode')):
        with directory(deps).transaction(user,(company,mode)) as (cur,owner,actor):
            ready(cur)
            cur.execute('''SELECT id,participant_type,participant_id,reason_code,status,result,created_at,updated_at
                FROM participant_access_tickets WHERE id=%s AND company_id=%s AND platform_account_id=%s AND reporter_id=%s''',
                (ticket_id,owner['id'],owner['platform_account_id'],user['id']))
            row=cur.fetchone()
            if not row:
                raise HTTPException(404,'Обращение недоступно')
            return ticket_view(row)

    @app.get('/system/companies/{company_id}/participants')
    def participants(company_id: int, user: dict = Depends(admin),
                     search: str = Query('',max_length=100), offset: int = Query(0,ge=0),
                     limit: int = Query(25,ge=1,le=100)):
        with admin_transaction(deps,user,company_id) as (cur,company):
            cur.execute('''SELECT s.id,s.name,s.inn,(s.user_id IS NOT NULL) AS has_account,
                l.source_type,l.status,l.version,
                (l.profile->>'mergedIntoSupplierId') AS merged_into_supplier_id,
                (SELECT count(*) FROM participant_access_tickets t WHERE t.company_id=l.company_id
                    AND t.platform_account_id=l.platform_account_id AND t.participant_type='supplier'
                    AND t.participant_id=s.id AND t.status<>'closed') AS open_tickets
                FROM company_supplier_links l JOIN suppliers s ON s.id=l.supplier_id
                WHERE l.company_id=%s AND l.platform_account_id=%s
                AND (s.name ILIKE %s OR s.inn ILIKE %s)
                ORDER BY s.name,s.id LIMIT %s OFFSET %s''',
                (company_id,company['platform_account_id'],'%'+search+'%','%'+search+'%',limit+1,offset))
            rows = cur.fetchall()
            return dict(items=[dict(row) for row in rows[:limit]],hasMore=len(rows)>limit,participantType='supplier')

    @app.get('/system/companies/{company_id}/participant-tickets')
    def tickets(company_id: int,user: dict = Depends(admin),
                status: str = Query(''), offset: int = Query(0,ge=0), limit: int = Query(25,ge=1,le=100)):
        if status and status not in TRANSITIONS:
            raise HTTPException(422,'Некорректный статус')
        with admin_transaction(deps,user,company_id) as (cur,company):
            cur.execute('''SELECT t.*,d.context FROM participant_access_tickets t
                JOIN participant_access_diagnostics d ON d.id=t.diagnostic_id
                AND d.company_id=t.company_id AND d.platform_account_id=t.platform_account_id
                WHERE t.company_id=%s AND t.platform_account_id=%s AND (%s='' OR t.status=%s)
                ORDER BY t.id DESC LIMIT %s OFFSET %s''',
                (company_id,company['platform_account_id'],status,status,limit+1,offset))
            rows = cur.fetchall()
            return dict(items=[ticket_view(row,True) for row in rows[:limit]],hasMore=len(rows)>limit)

    @app.get('/system/companies/{company_id}/participant-tickets/{ticket_id}')
    def detail(company_id: int,ticket_id: int,user: dict = Depends(admin)):
        with admin_transaction(deps,user,company_id) as (cur,company):
            cur.execute('''SELECT t.*,d.context FROM participant_access_tickets t
                JOIN participant_access_diagnostics d ON d.id=t.diagnostic_id
                AND d.company_id=t.company_id AND d.platform_account_id=t.platform_account_id
                WHERE t.id=%s AND t.company_id=%s AND t.platform_account_id=%s''',
                (ticket_id,company_id,company['platform_account_id']))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404,'Обращение недоступно')
            cur.execute('''SELECT actor_id,from_status,to_status,result,created_at
                FROM participant_access_ticket_events WHERE ticket_id=%s ORDER BY id''', (ticket_id,))
            return dict(ticket_view(row,True),history=[dict(event) for event in cur.fetchall()])

    @app.patch('/system/companies/{company_id}/participant-tickets/{ticket_id}')
    def update(company_id: int,ticket_id: int,data: dict,user: dict = Depends(admin)):
        if (set(data)-{'status','expectedVersion','result','verified'}
                or type(data.get('expectedVersion')) is not int
                or data['expectedVersion'] < 1 or not isinstance(data.get('status'),str)):
            raise HTTPException(422,'Укажите версию обращения и разрешённое действие')
        result = data.get('result','')
        if not isinstance(result,str) or len(result)>2000:
            raise HTTPException(422,'Результат слишком длинный')
        with admin_transaction(deps,user,company_id) as (cur,company):
            cur.execute('''SELECT status,version FROM participant_access_tickets
                WHERE id=%s AND company_id=%s AND platform_account_id=%s FOR UPDATE''',
                (ticket_id,company_id,company['platform_account_id']))
            before = cur.fetchone()
            if not before:
                raise HTTPException(404,'Обращение недоступно')
            if before['version'] != data['expectedVersion']:
                raise HTTPException(409,'Обращение изменилось. Обновите карточку')
            status = data.get('status')
            if status not in TRANSITIONS[before['status']]:
                raise HTTPException(409,'Недопустимый переход статуса')
            if status in ('resolved','closed') and len(result.strip())<5:
                raise HTTPException(422,'Опишите результат проверки')
            if status == 'closed' and data.get('verified') is not True:
                raise HTTPException(422,'Подтвердите проверку исходного сценария')
            cur.execute('''UPDATE participant_access_tickets SET status=%s,result=%s,
                version=version+1,updated_at=NOW(),assigned_to=%s WHERE id=%s RETURNING id,status,version''',
                (status,result.strip(),user['id'],ticket_id))
            row = dict(cur.fetchone())
            cur.execute('''INSERT INTO participant_access_ticket_events(ticket_id,actor_id,from_status,to_status,result)
                VALUES(%s,%s,%s,%s,%s)''', (ticket_id,user['id'],before['status'],status,result.strip()))
            return row
