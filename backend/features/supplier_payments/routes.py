"""Default-off HTTP boundary. Explicit registration only; never imports main/config.

Mount behind the application's existing authenticated-session/CSRF middleware.
Dependencies: get_db, get_current_user, resolve_documents (WRITE resolver),
authorize_read (read-mode financial access).
No read may fall back to write authorization. No callback may commit/open a DB.
"""
import os
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, Response
from psycopg2 import DatabaseError

from .commands import normalize_command
from .cancellations import cancel_request
from .engine import execute
from .policy import validate_new_payment
from . import reads


def require_enabled():
    if os.getenv('SUPPLIER_PAYMENTS_ENABLED', '0') != '1':
        raise HTTPException(404, 'Not found')


def _headers(request, company_id):
    company_ids = request.headers.getlist('X-Company-Id')
    modes = request.headers.getlist('X-Company-Mode')
    if len(company_ids) > 1 or len(modes) > 1:
        raise HTTPException(400, 'Заголовки выбранной компании не должны повторяться')
    if modes and modes != ['company']:
        raise HTTPException(400, 'Выберите одну компанию')
    if len(company_ids) != 1 or not company_ids[0]:
        raise HTTPException(400, 'Укажите выбранную компанию в X-Company-Id')
    if company_ids[0] != str(company_id):
        raise HTTPException(409, 'Компания запроса не совпадает с выбранной')


def _query(request, allowed):
    keys = list(request.query_params.keys())
    if set(keys) - set(allowed) or any(len(request.query_params.getlist(k)) != 1 for k in keys):
        raise HTTPException(422, 'Недопустимые или повторные параметры запроса')


def register_supplier_payment_routes(app, deps):
    router = APIRouter(dependencies=[Depends(require_enabled)])
    authenticate = deps['get_current_user']

    @router.post('/companies/{company_id}/supplier-payments')
    def payment(request: Request, response: Response, body: Any = Body(...),
                company_id: int = Path(..., ge=1, le=2147483647), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ())
        command = normalize_command(body)
        response.headers['Cache-Control'] = 'no-store'
        resolver = deps.get('resolve_documents')
        if not callable(resolver):
            raise HTTPException(503, 'Сервис оплат не подготовлен')

        def authorize(cur, actor_id, owner_id, normalized):
            reads.require_schema(cur, deps)
            return resolver(cur, actor_id, owner_id, normalized)

        try:
            result = execute(deps['get_db'], authorize, user['id'], company_id, body,
                             validate_new=validate_new_payment)
        except DatabaseError:
            raise HTTPException(503, 'Результат оплаты не подтверждён. Повторите тот же UUID') from None
        return {**result, 'companyId': company_id, 'requestId': command['requestId'],
                'documentKind': command['documentKind'], 'documentId': command['documentId']}

    @router.post('/companies/{company_id}/supplier-payments/cancel-request')
    def cancel_payment_request(request: Request, response: Response, body: Any = Body(...),
                               company_id: int = Path(..., ge=1, le=2147483647),
                               user: dict = Depends(authenticate)):
        try:
            _headers(request, company_id)
            _query(request, ())
            command = normalize_command(body)
            response.headers['Cache-Control'] = 'no-store'
            resolver = deps.get('resolve_documents')
            if not callable(resolver):
                raise HTTPException(503, 'Сервис оплат не подготовлен')

            def authorize(cur, actor_id, owner_id, normalized):
                # cancel_request holds the engine company lock and owns the
                # transaction. Current WRITE authority precedes schema/UUID
                # conflicts; a read-only subscription must not cancel attempts.
                context = resolver(cur, actor_id, owner_id, normalized)
                reads.require_schema(cur, deps, require_cancellations=True)
                return context

            result = cancel_request(deps['get_db'], authorize, user['id'], company_id, body)
        except DatabaseError:
            raise HTTPException(503, dict(code='cancellation_unconfirmed',
                message='Результат отмены не подтверждён. Сохраните и повторите тот же UUID')) from None
        except HTTPException as exc:
            if isinstance(exc.detail, dict):
                raise
            code = {400: 'invalid_company_headers', 403: 'access_denied',
                    404: 'document_not_found', 409: 'cancellation_conflict',
                    422: 'invalid_command', 503: 'cancellation_unavailable'}.get(exc.status_code, 'cancellation_failed')
            raise HTTPException(exc.status_code, dict(code=code, message=str(exc.detail)),
                                headers=exc.headers) from None
        # Preserve the module's confirmed _result exactly, notably the persisted
        # kind/amount. Only outer identity comes from the normalized command.
        return {**result, 'companyId': company_id, 'requestId': command['requestId'],
                'documentKind': command['documentKind'], 'documentId': command['documentId'],
                'kind': command['kind']}

    @router.get('/companies/{company_id}/supplier-payments')
    def history(request: Request, response: Response,
                company_id: int = Path(..., ge=1, le=2147483647),
                limit: int = Query(50, ge=1, le=100),
                beforeId: Optional[int] = Query(None, ge=1, le=9223372036854775807),
                documentKind: Optional[Literal['invoice', 'warehouse']] = Query(None),
                documentId: Optional[int] = Query(None, ge=1, le=2147483647),
                payerCompanyId: Optional[int] = Query(None, ge=1, le=2147483647),
                supplierId: Optional[int] = Query(None, ge=1, le=2147483647),
                projectName: Optional[str] = Query(None, min_length=1, max_length=300),
                requestId: Optional[UUID] = Query(None), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ('limit', 'beforeId', 'documentKind', 'documentId', 'payerCompanyId',
                         'supplierId', 'projectName', 'requestId'))
        if (documentKind is None) != (documentId is None):
            raise HTTPException(422, 'Укажите вид и ID документа вместе')
        filters = dict(documentKind=documentKind, documentId=documentId, payerCompanyId=payerCompanyId,
                       supplierId=supplierId, projectName=projectName)
        if requestId is not None and (beforeId is not None or any(v is not None for v in filters.values())):
            raise HTTPException(422, 'Поиск UUID нельзя ограничивать другими фильтрами')
        response.headers['Cache-Control'] = 'no-store'
        with reads.transaction(deps, company_id) as cur:
            return reads.history(cur, deps, user['id'], company_id, limit=limit, before_id=beforeId,
                                 request_id=str(requestId) if requestId is not None else None, **filters)

    @router.get('/companies/{company_id}/supplier-payment-documents/{kind}/{id}')
    def document(request: Request, response: Response,
                 company_id: int = Path(..., ge=1, le=2147483647),
                 kind: Literal['invoice', 'warehouse'] = Path(...),
                 id: int = Path(..., ge=1, le=2147483647), user: dict = Depends(authenticate)):
        _headers(request, company_id)
        _query(request, ())
        response.headers['Cache-Control'] = 'no-store'
        with reads.transaction(deps, company_id) as cur:
            return reads.document(cur, deps, user['id'], company_id, kind, id)

    app.include_router(router)
