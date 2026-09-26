"""Explicit, default-off allocation HTTP adapter; no runtime registration.

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
from psycopg2.extras import RealDictCursor

from . import allocation_store
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
            try:
                if any(os.getenv(flag, '0') != '1' for flag in
                       ('SUPPLIER_PAYMENTS_ENABLED', 'SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED')):
                    raise HTTPException(404, 'Not found')
                response = await original(request)
            except RequestValidationError:
                response = JSONResponse(status_code=422, content={'detail': {
                    'code': 'invalid_allocation_command', 'message': 'Некорректный запрос распределения'}})
            except HTTPException as exc:
                code = {400: 'invalid_company_headers', 401: 'authentication_required',
                        403: 'access_denied', 404: 'allocation_not_found', 409: 'allocation_conflict',
                        422: 'invalid_allocation_command', 503: 'allocation_unavailable'}.get(exc.status_code, 'allocation_failed')
                detail = exc.detail if isinstance(exc.detail, dict) else dict(code=code, message=str(exc.detail))
                response = JSONResponse(status_code=exc.status_code, content={'detail': detail}, headers=exc.headers)
            except Exception:
                # Includes connection/commit uncertainty. Never replace the UUID
                # or expose driver details; the same command is the safe retry.
                message = ('Результат распределения не подтверждён. Сохраните и повторите тот же UUID и команду'
                           if request.method == 'POST' else 'Распределение временно недоступно; обновите данные')
                response = JSONResponse(status_code=503, content={'detail': {
                    'code': 'allocation_unconfirmed' if request.method == 'POST' else 'allocation_unavailable',
                    'message': message}})
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
