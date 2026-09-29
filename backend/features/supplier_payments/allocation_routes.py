"""Explicit, default-off allocation and linked-refund HTTP adapter.

The future mount must retain the existing session/CSRF middleware. Inject
get_db, get_current_user, distinct authorize_allocation_write/read callbacks,
and require_allocation_schema(cur). Authorization callbacks retain current
authority locks and cannot commit. No receipt registration endpoint is exposed.
"""
import os
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from psycopg2 import DatabaseError
from psycopg2.extras import RealDictCursor

from . import allocation_store, refund_store
from .refund_commands import normalize_refund_command
from .policy import validate_new_payment
from .allocation_commands import normalize_allocation_command
from .routes import _headers, _query


def _unavailable():
    return HTTPException(503, dict(code='allocation_unavailable',
        message='Сервис распределения временно недоступен'))


class _AllocationRoute(APIRoute):
    """Keep flag, validation, auth and database failures non-cacheable too."""
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            is_refund = request.url.path.endswith('/allocated-refunds')
            try:
                if any(os.getenv(flag, '0') != '1' for flag in
                       ('SUPPLIER_PAYMENTS_ENABLED', 'SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED')):
                    raise HTTPException(404, 'Not found')
                response = await original(request)
            except RequestValidationError:
                response = JSONResponse(status_code=422, content={'detail': {
                    'code': 'invalid_refund_command' if is_refund else 'invalid_allocation_command',
                    'message': 'Некорректный запрос возврата' if is_refund else 'Некорректный запрос распределения'}})
            except HTTPException as exc:
                code = {400: 'invalid_company_headers', 401: 'authentication_required',
                        403: 'access_denied', 404: 'allocation_not_found', 409: 'allocation_conflict',
                        422: 'invalid_allocation_command', 503: 'allocation_unavailable'}.get(exc.status_code, 'allocation_failed')
                detail = dict(exc.detail) if isinstance(exc.detail, dict) else dict(code=code, message=str(exc.detail))
                if is_refund and isinstance(detail.get('code'), str):
                    detail['code'] = detail['code'].replace('allocation', 'refund')
                response = JSONResponse(status_code=exc.status_code, content={'detail': detail}, headers=exc.headers)
            except Exception as exc:
                # A PostgreSQL constraint rejection is a confirmed rollback.
                # Connection/commit uncertainty requires the exact same UUID.
                if is_refund and isinstance(exc, DatabaseError) and exc.pgcode == '23514':
                    response = JSONResponse(status_code=409, content={'detail': {
                        'code': 'refund_conflict', 'message': 'Возврат не проведён: обновите остаток и распределение оплаты'}})
                else:
                    message = ('Результат распределения не подтверждён. Сохраните и повторите тот же UUID и команду'
                               if request.method == 'POST' else 'Распределение временно недоступно; обновите данные')
                    code = 'allocation_unconfirmed' if request.method == 'POST' else 'allocation_unavailable'
                    if is_refund:
                        code = 'refund_unconfirmed'
                        message = 'Результат возврата не подтверждён. Повторите тот же UUID и команду'
                    response = JSONResponse(status_code=503, content={'detail': {'code': code, 'message': message}})
            response.headers['Cache-Control'] = 'no-store'
            return response

        return handle


def _authorize(deps, operation):
    authority = deps.get('authorize_allocation_' + operation)
    schema = deps.get('require_allocation_schema')
    if not callable(authority) or not callable(schema) or not callable(deps.get('get_db')):
        raise _unavailable()

    def authorize(cur, actor_id, company_id, command):
        context = authority(cur, actor_id, company_id, command)
        try:
            schema(cur)
        except Exception:
            raise _unavailable() from None
        return context

    return authorize


def register_supplier_allocation_routes(app, deps):
    router = APIRouter(route_class=_AllocationRoute)
    authenticate = deps['get_current_user']

    @router.post('/companies/{company_id}/supplier-payments/allocations')
    def replace(request: Request, body: Any = Body(...),
                company_id: int = Path(..., ge=1, le=2147483647), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ())
        command = normalize_allocation_command(body)
        result = allocation_store.replace_allocations(deps['get_db'], _authorize(deps, 'write'),
                                                       user['id'], company_id, command)
        return {**result, 'companyId': company_id}

    @router.post('/companies/{company_id}/supplier-payments/allocated-refunds')
    def refund(request: Request, body: Any = Body(...),
               company_id: int = Path(..., ge=1, le=2147483647), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ())
        command = normalize_refund_command(body)
        resolver = deps.get('resolve_documents')
        if not callable(resolver):
            raise _unavailable()
        result = refund_store.refund(deps['get_db'], _authorize(deps, 'write'), resolver,
            user['id'], company_id, command, validate_new=validate_new_payment)
        return {**result, 'companyId': company_id, 'requestId': command['requestId'],
                'paymentId': command['paymentId']}

    @router.get('/companies/{company_id}/supplier-payments/refund-context/{invoice_id}')
    def refund_context(request: Request, company_id: int = Path(..., ge=1, le=2147483647),
                       invoice_id: int = Path(..., ge=1, le=2147483647), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ())
        resolver = deps.get('resolve_documents_read')
        if not callable(resolver):
            raise _unavailable()
        authorize = _authorize(deps, 'read')
        conn = deps['get_db']()
        try:
            conn.set_session(isolation_level='READ COMMITTED', autocommit=False)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET LOCAL lock_timeout='3s'")
                cur.execute("SET LOCAL statement_timeout='15s'")
                cur.execute('SELECT pg_advisory_xact_lock(%s,%s)', (1735289201,company_id))
                resolver(cur,user['id'],company_id,dict(documentKind='invoice',documentId=invoice_id))
                deps['require_allocation_schema'](cur)
                cur.execute('''SELECT g.id FROM supplier_payment_allocation_groups g
                    JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
                    WHERE d.company_id=%s AND d.document_kind='invoice' AND d.document_id=%s''',
                    (company_id,invoice_id))
                group = cur.fetchone()
                if not group:
                    return dict(companyId=company_id,invoiceId=invoice_id,groupId=None)
                result = allocation_store.read_allocations_in_transaction(cur,authorize,user['id'],company_id,group['id'])
                cur.execute('SELECT id,warehouse_invoice_id FROM supplier_payment_receipt_relations WHERE group_id=%s AND company_id=%s',
                            (group['id'],company_id))
                receipts = {row['id']:row['warehouse_invoice_id'] for row in cur.fetchall()}
                result['receipts'] = [dict(row,warehouseId=receipts[row['receiptId']]) for row in result['receipts']]
                return dict(result,companyId=company_id,invoiceId=invoice_id)
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()

    @router.get('/companies/{company_id}/supplier-payments/allocation-groups/{group_id}')
    def read(request: Request, company_id: int = Path(..., ge=1, le=2147483647),
             group_id: int = Path(..., ge=1, le=9223372036854775807), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ())
        authorize = _authorize(deps, 'read')
        conn = deps['get_db']()
        try:
            conn.set_session(isolation_level='READ COMMITTED', autocommit=False)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET LOCAL lock_timeout='3s'")
                cur.execute("SET LOCAL statement_timeout='15s'")
                result = allocation_store.read_allocations_in_transaction(cur, authorize, user['id'], company_id, group_id)
            return {**result, 'companyId': company_id}
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()

    app.include_router(router)
