"""Explicit first binding; never change balances, replace contracts or infer parties."""
from typing import Annotated, Optional
from uuid import UUID

import psycopg2.extras
from psycopg2.errors import LockNotAvailable
from fastapi import Depends, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .access import build_deal_access
from .contracts import serialize_contract
from .document_bindings import select_invoice_contract
from .legacy_binding_policy import validate_legacy_binding
from ..supplier_payments.contract_context import load_invoice_contract


class LegacyBindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: UUID
    contractVersionId: int = Field(strict=True, gt=0, le=2147483647)
    expectedAmount: str = Field(pattern=r'^[0-9]+\.[0-9]{2}$', max_length=30)
    reason: str = Field(min_length=1, max_length=1000)
    confirmed: bool = Field(strict=True)

    @field_validator('reason')
    @classmethod
    def reason_required(cls, value):
        if not value.strip(): raise ValueError('Укажите основание привязки')
        return value.strip()

    @field_validator('confirmed')
    @classmethod
    def confirmation_required(cls, value):
        if value is not True: raise ValueError('Подтвердите проверку счёта и договора')
        return value


def register_legacy_binding_routes(app, deps):
    company_actor, load_offer = build_deal_access(deps)

    def authorize(cur, invoice_id, user, header_id, header_mode):
        cur.execute('SELECT * FROM supplier_invoices WHERE id=%s', (invoice_id,))
        invoice = cur.fetchone()
        if not invoice: raise HTTPException(404, 'Счёт не найден')
        actor = company_actor(cur, user, invoice['company_id'], 'update', header_id, header_mode)
        deps['require_project_access'](actor, invoice.get('project_name') or '')
        if not deps['has_package_access'](actor, invoice.get('work_package') or 'Основная'):
            raise HTTPException(403, 'Нет доступа к разделу счёта')
        if not invoice.get('offer_id'):
            raise HTTPException(409, 'Счёт не связан с КП')
        offer, _ = load_offer(cur, invoice['offer_id'], user, 'read', header_id, header_mode)
        if any(invoice.get(k) != offer.get(k) for k in ('company_id','supplier_id','request_id')):
            raise HTTPException(409, 'Связи счёта и КП требуют сверки')
        return invoice, offer, actor

    @app.get('/supplier-invoices/{id}/legacy-contract-binding')
    def preview(id: Annotated[int, Path(gt=0)], current_user: dict = Depends(deps['get_current_user']),
                x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
                x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None):
        conn = deps['get_db']()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                invoice, offer, _ = authorize(cur, id, current_user, x_company_id, x_company_mode)
                cur.execute('SELECT * FROM supplier_contract_versions WHERE company_id=%s AND offer_id=%s ORDER BY version DESC LIMIT 1',
                            (invoice['company_id'], offer['id']))
                contract = cur.fetchone()
                return dict(invoiceId=id, companyId=invoice['company_id'], offerId=offer['id'],
                            amount=format(invoice['amount'], '.2f'), boundContractId=invoice['contract_version_id'],
                            contract=serialize_contract(contract) if contract else None)
        finally:
            conn.rollback(); conn.close()

    @app.post('/supplier-invoices/{id}/legacy-contract-binding')
    def bind(id: Annotated[int, Path(gt=0)], data: LegacyBindingInput,
             current_user: dict = Depends(deps['get_current_user']),
             x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
             x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None):
        conn = deps['get_db'](); conn.autocommit = False
        new_attempt = False
        company_id = None
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                initial, _, _ = authorize(cur, id, current_user, x_company_id, x_company_mode)
                # A one-time legacy transition must also exclude old writers which
                # predate the company protocol. NOWAIT prevents lock-order waits.
                try:
                    cur.execute('''LOCK TABLE supplier_invoices,warehouse_invoices,supply_requests,
                        supplier_offers,supply_deliveries,supplier_payment_documents,
                        supplier_invoice_line_specs,supplier_contract_versions,supplier_deal_parties,
                        supplier_legacy_contract_bindings IN ACCESS EXCLUSIVE MODE NOWAIT''')
                except LockNotAvailable:
                    raise HTTPException(409, 'Документы заняты другой операцией. Повторите запрос') from None
                cur.execute('SELECT pg_try_advisory_xact_lock(%s,%s) AS acquired', (1735289201, initial['company_id']))
                if not cur.fetchone()['acquired']:
                    raise HTTPException(409, 'Расчёты компании заняты другой операцией. Повторите запрос')
                invoice, offer, actor = authorize(cur, id, current_user, x_company_id, x_company_mode)
                if invoice['company_id'] != initial['company_id']:
                    raise HTTPException(409, 'Компания счёта изменилась')
                cur.execute('SELECT * FROM supplier_legacy_contract_bindings WHERE invoice_id=%s OR request_id=%s',
                            (id, str(data.requestId)))
                previous = cur.fetchall()
                if previous:
                    p = previous[0]
                    if len(previous)!=1 or any((p['invoice_id']!=id, p['company_id']!=invoice['company_id'],
                        str(p['request_id'])!=str(data.requestId), p['contract_version_id']!=data.contractVersionId,
                        p['reason']!=data.reason, p['actor_id']!=actor.get('id'),
                        invoice['contract_version_id']!=data.contractVersionId,
                        format(invoice['amount'], '.2f')!=data.expectedAmount)):
                        raise HTTPException(409, 'Запрос или привязка уже сохранены с другими данными')
                else:
                    new_attempt = True
                    company_id = invoice['company_id']
                    contract = select_invoice_contract(cur, offer['id'], data.contractVersionId)
                    cur.execute('''SELECT
                        EXISTS(SELECT 1 FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s) AS ledger,
                        EXISTS(SELECT 1 FROM warehouse_invoices WHERE supplier_invoice_id=%s) AS receipts,
                        EXISTS(SELECT 1 FROM supply_deliveries WHERE source_supplier_invoice_id=%s OR offer_id=%s) AS deliveries,
                        EXISTS(SELECT 1 FROM supplier_invoice_line_specs WHERE invoice_id=%s) AS sealed_lines''',
                                (id,id,id,offer['id'],id))
                    validate_legacy_binding(invoice, offer, contract, cur.fetchone())
                    if format(invoice['amount'], '.2f') != data.expectedAmount:
                        raise HTTPException(409, 'Сумма счёта изменилась. Проверьте его заново')
                    cur.execute('''INSERT INTO supplier_legacy_contract_bindings
                        (invoice_id,company_id,offer_id,contract_version_id,request_id,reason,actor_id,actor_name)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (id,invoice['company_id'],offer['id'],data.contractVersionId,str(data.requestId),
                         data.reason,actor['id'],actor.get('name') or actor.get('email') or ''))
                    cur.execute('UPDATE supplier_invoices SET contract_version_id=%s WHERE id=%s',
                                (data.contractVersionId,id))
                # Validate exact frozen scope/hash after the transactional change;
                # any mismatch rolls back both the audit and the binding.
                context = load_invoice_contract(cur, id, invoice['company_id'])
                for company in sorted({context['buyerCompanyId'],context['payerCompanyId']} - {invoice['company_id']}):
                    company_actor(cur,current_user,company,'update')
                conn.commit()
                return dict(invoiceId=id,companyId=invoice['company_id'],requestId=str(data.requestId),
                            contractVersionId=data.contractVersionId,bindingStatus='bound',replayed=bool(previous))
        except HTTPException as error:
            conn.rollback()
            if new_attempt and error.status_code == 409:
                raise HTTPException(409, dict(code='legacy_binding_not_saved', message=error.detail,
                    companyId=company_id, invoiceId=id, requestId=str(data.requestId))) from None
            raise
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
