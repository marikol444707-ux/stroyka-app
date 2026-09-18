"""Optional API registration. The flag gate runs before even the auth dependency."""
from contextlib import contextmanager
from datetime import date
import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from .models import DistributionInput, ReturnInput, TransferInput, TransferReceiptInput, MAX_ID, MAIN, decimal_text
from .service import allocation_views, issue, physical_return
from . import transfers


WAREHOUSE_WRITERS = {'директор', 'зам_директора', 'кладовщик', 'снабженец'}


def validate_search(q):
    if '\x00' in q:
        raise HTTPException(422, 'Недопустимый символ в поиске')
    return q.strip()


def require_enabled():
    if os.environ.get('WAREHOUSE_DISTRIBUTION_ENABLED') != '1':
        raise HTTPException(404, 'Not found')


def require_transfers_enabled():
    require_enabled()
    if os.environ.get('WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED') != '1':
        raise HTTPException(404, 'Not found')


def require_active_membership(context):
    if (context.get('mode') != 'company' or context.get('source') != 'membership'
            or not context.get('active') or not context.get('companyActive')
            or not context.get('membershipId')):
        raise HTTPException(403, 'Выберите компанию с активным членством')


def register_warehouse_distribution_module(app, deps):
    router = APIRouter(prefix='/warehouse-distributions', dependencies=[Depends(require_enabled)])

    @contextmanager
    def transaction(write=False):
        conn = deps['get_db']()
        try:
            if write:
                # A refresh after a lock wait must see newly committed revocations.
                conn.set_session(isolation_level='READ COMMITTED', autocommit=False)
            else:
                conn.autocommit = False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if write:
                    cur.execute("SET LOCAL lock_timeout='3s'")
                    cur.execute("SET LOCAL statement_timeout='15s'")
                yield cur
            conn.commit()
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode in ('40P01', '40001', '55P03'):
                raise HTTPException(409, 'Конкурирующая операция; повторите запрос с тем же requestId') from error
            if error.pgcode in ('23503', '23505', '23514', 'P0001'):
                raise HTTPException(409, 'Складские данные изменились или защищены от изменения') from error
            raise
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def authorize(cur, user, requested, write, header_id, header_mode):
        context = deps['resolve_work_company_context'](
            cur, user, requested, 'write' if write else 'read',
            x_company_id=header_id, x_company_mode=header_mode)
        company_id = context.get('companyId') or context.get('company_id')
        if context.get('mode') != 'company' or not company_id:
            raise HTTPException(400, 'Выберите одну компанию')
        if requested is not None and company_id != requested:
            raise HTTPException(409, 'Компания запроса не совпадает с выбранной компанией')
        require_active_membership(context)
        if write:
            # Keep all three locks through the stock command and commit, including
            # replay. Never fall through to a second, unlocked membership on refresh.
            membership_id = context['membershipId']
            cur.execute('SELECT id FROM users WHERE id=%s AND active=TRUE FOR SHARE', (user['id'],))
            if not cur.fetchone():
                raise HTTPException(403, 'Пользователь отключён')
            cur.execute('SELECT id FROM companies WHERE id=%s FOR SHARE', (company_id,))
            if not cur.fetchone():
                raise HTTPException(403, 'Компания больше не доступна')
            cur.execute('SELECT id FROM user_company_roles WHERE id=%s AND user_id=%s AND company_id=%s FOR SHARE',
                        (membership_id, user['id'], company_id))
            if not cur.fetchone():
                raise HTTPException(403, 'Членство больше не действует')
            context = deps['resolve_work_company_context'](
                cur, user, company_id, 'write',
                x_company_id=header_id, x_company_mode=header_mode)
            require_active_membership(context)
            if (context.get('membershipId') != membership_id
                    or (context.get('companyId') or context.get('company_id')) != company_id):
                raise HTTPException(403, 'Членство больше не действует')
        allowed = WAREHOUSE_WRITERS if write else set(deps['finance_roles']) | WAREHOUSE_WRITERS
        # The shared actor adapter can fall back to user.role for an empty role;
        # this strict boundary requires the selected membership's role itself.
        if context.get('role') not in allowed or (write and context.get('readOnly')):
            raise HTTPException(403, 'Роль в выбранной компании не позволяет выполнить действие')
        actor = next((a for a in deps['effective_company_actors'](user, context)
                      if (a.get('companyId') or a.get('company_id')) == company_id
                      and a.get('role') == context['role']), None)
        if actor is None:
            raise HTTPException(403, 'Роль в выбранной компании не позволяет выполнить действие')
        return company_id, actor

    @router.get('/sources')
    def sources(
        companyId: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
        beforeId: Annotated[Optional[int], Query(gt=0, le=9223372036854775807)] = None,
        limit: Annotated[int, Query(gt=0, le=200)] = 200,
        q: Annotated[str, Query(max_length=200)] = '',
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        q = validate_search(q)
        with transaction() as cur:
            company_id, _ = authorize(cur, current_user, companyId, False, x_company_id, x_company_mode)
            conditions, values = [], [company_id, MAIN]
            if beforeId is not None:
                conditions.append('l.id<%s')
                values.append(beforeId)
            if q:
                conditions.append("strpos(lower(concat_ws(' ',i.number,l.material_name)),lower(%s))>0")
                values.append(q)
            extra = ''.join(' AND ' + condition for condition in conditions)
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute('''SELECT l.id,l.warehouse_invoice_id,l.invoice_line_index,l.material_name,
                l.unit,l.available_quantity,i.number FROM warehouse_receipt_lots l
                JOIN warehouse_invoices i ON i.id=l.warehouse_invoice_id AND i.company_id=l.company_id
                WHERE l.company_id=%s AND l.status='active' AND l.warehouse_target='main'
                  AND l.warehouse_location=%s AND l.available_quantity>0
                  AND coalesce(i.status,'Принята')<>'Аннулирована'
                ''' + extra + ' ORDER BY l.id DESC LIMIT %s', [*values, limit + 1])
            rows = cur.fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            return dict(items=[dict(lotId=r['id'], warehouseInvoiceId=r['warehouse_invoice_id'],
                                    invoiceNumber=str(r['number'] or ''), invoiceLineIndex=r['invoice_line_index'],
                                    materialName=r['material_name'], unit=r['unit'],
                                    availableQuantity=decimal_text(r['available_quantity'])) for r in rows],
                        max=limit, truncated=more, nextCursor=rows[-1]['id'] if more else None)

    @router.get('')
    def allocations(
        companyId: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
        beforeId: Annotated[Optional[int], Query(gt=0, le=9223372036854775807)] = None,
        limit: Annotated[int, Query(gt=0, le=200)] = 100,
        q: Annotated[str, Query(max_length=200)] = '',
        projectId: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
        dateFrom: Optional[date] = None,
        dateTo: Optional[date] = None,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        q = validate_search(q)
        if dateFrom and dateTo and dateFrom > dateTo:
            raise HTTPException(422, 'Начало периода позже окончания')
        with transaction() as cur:
            # One report snapshot keeps returned totals and event histories consistent.
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            company_id, _ = authorize(cur, current_user, companyId, False, x_company_id, x_company_mode)
            conditions, values = ['company_id=%s'], [company_id]
            if beforeId is not None:
                conditions.append('id<%s')
                values.append(beforeId)
            if q:
                conditions.append("strpos(lower(concat_ws(' ',project_name,material_name,receipt_number,id::text)),lower(%s))>0")
                values.append(q)
            if projectId is not None:
                conditions.append('project_id=%s')
                values.append(projectId)
            if dateFrom:
                conditions.append("created_at >= (%s::date::timestamp AT TIME ZONE 'UTC')")
                values.append(dateFrom)
            if dateTo:
                conditions.append("created_at < ((%s::date + 1)::timestamp AT TIME ZONE 'UTC')")
                values.append(dateTo)
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute('SELECT * FROM warehouse_distribution_allocations WHERE '
                        + ' AND '.join(conditions) + ' ORDER BY id DESC LIMIT %s', [*values, limit + 1])
            rows = cur.fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            return dict(items=allocation_views(cur, rows), truncated=more,
                        nextCursor=rows[-1]['id'] if more else None)

    @router.post('')
    def distribute(
        data: DistributionInput,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        with transaction(write=True) as cur:
            _, actor = authorize(cur, current_user, data.companyId, True, x_company_id, x_company_mode)
            return issue(cur, deps, data, actor)

    @router.get('/transfers', dependencies=[Depends(require_transfers_enabled)])
    def transfer_list(
        companyId: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
        beforeId: Annotated[Optional[int], Query(gt=0, le=9223372036854775807)] = None,
        limit: Annotated[int, Query(gt=0, le=200)] = 100,
        q: Annotated[str, Query(max_length=200)] = '',
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        q = validate_search(q)
        with transaction() as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            company_id, _ = authorize(cur,current_user,companyId,False,x_company_id,x_company_mode)
            transfers.require_schema(cur)
            conditions, values = ['t.company_id=%s'], [company_id]
            if beforeId is not None:
                conditions.append('t.id<%s')
                values.append(beforeId)
            if q:
                conditions.append("strpos(lower(concat_ws(' ',a.project_name,t.to_project_name,a.material_name,a.receipt_number,t.id::text)),lower(%s))>0")
                values.append(q)
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute('''SELECT t.* FROM warehouse_distribution_transfers t
                JOIN warehouse_distribution_allocations a ON a.id=t.source_allocation_id AND a.company_id=t.company_id
                WHERE '''+' AND '.join(conditions)+' ORDER BY t.id DESC LIMIT %s',[*values,limit+1])
            rows = cur.fetchall()
            more = len(rows)>limit
            rows = rows[:limit]
            return dict(items=transfers.views(cur,rows),truncated=more,nextCursor=rows[-1]['id'] if more else None)

    @router.post('/transfers', dependencies=[Depends(require_transfers_enabled)])
    def dispatch_transfer(
        data: TransferInput,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        with transaction(write=True) as cur:
            _, actor = authorize(cur,current_user,data.companyId,True,x_company_id,x_company_mode)
            result = transfers.dispatch(cur,deps,data,actor)
            return {key: result[key] for key in ('ok','requestId','item')}

    @router.post('/transfers/{transfer_id}/receipts', dependencies=[Depends(require_transfers_enabled)])
    def receive_transfer(
        transfer_id: Annotated[int, Path(gt=0, le=9223372036854775807)], data: TransferReceiptInput,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        with transaction(write=True) as cur:
            _, actor = authorize(cur,current_user,data.companyId,True,x_company_id,x_company_mode)
            result = transfers.receive(cur,deps,transfer_id,data,actor)
            return {key: result[key] for key in ('ok','requestId','item')}

    @router.post('/{allocation_id}/returns')
    def return_allocation(
        allocation_id: Annotated[int, Path(gt=0, le=9223372036854775807)], data: ReturnInput,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        with transaction(write=True) as cur:
            _, actor = authorize(cur, current_user, data.companyId, True, x_company_id, x_company_mode)
            return physical_return(cur, deps, allocation_id, data, actor)

    app.include_router(router)
