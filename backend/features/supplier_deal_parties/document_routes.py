"""Read the frozen contract attached to an already-authorized supply document."""
from typing import Annotated, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path

from .access import build_deal_access
from .contracts import serialize_contract
from .payment_schedule import schedule_projection


def register_document_contract_routes(app, deps):
    company_actor, load_offer = build_deal_access(deps)

    def register(path, table, project_column):
        @app.get(path)
        def context(
            id: Annotated[int, Path(gt=0)],
            current_user: dict = Depends(deps['get_current_user']),
            x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
            x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
        ):
            conn = deps['get_db']()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute('SELECT * FROM ' + table + ' WHERE id=%s', (id,))
                document = cur.fetchone()
                if not document:
                    raise HTTPException(404, 'Документ не найден')
                if not document.get('company_id'):
                    raise HTTPException(409, 'Владелец документа не определён')
                if document.get('offer_id'):
                    offer, _ = load_offer(cur, document['offer_id'], current_user, 'read', x_company_id, x_company_mode)
                    if any(document.get(field) != offer[field] for field in ('company_id', 'supplier_id', 'request_id')):
                        raise HTTPException(409, 'Нарушена связь документа со сделкой')
                elif current_user.get('role') == 'поставщик':
                    if document['supplier_id'] not in deps['current_supplier_ids'](cur, current_user):
                        raise HTTPException(403, 'Нет доступа к документу')
                else:
                    actor = company_actor(cur, current_user, document['company_id'], 'read', x_company_id, x_company_mode)
                    deps['require_project_access'](actor, document.get(project_column) or '')
                    if not deps['has_package_access'](actor, document.get('work_package') or 'Основная'):
                        raise HTTPException(403, 'Нет доступа к пакету документа')
                contract = None
                if document['contract_version_id'] is not None:
                    cur.execute('''SELECT * FROM supplier_contract_versions
                        WHERE id=%s AND company_id=%s AND offer_id=%s''',
                        (document['contract_version_id'], document['company_id'], document['offer_id']))
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(409, 'Версия договора документа не найдена')
                    contract = serialize_contract(row)
                payment_schedule = None
                if contract and contract['snapshot'].get('paymentSchedule') is not None:
                    amount = document.get('amount')
                    invoice_id = document['id']
                    invoice_date = document.get('invoice_date') or document.get('created_at')
                    if table == 'supply_deliveries':
                        invoice_id = document['source_supplier_invoice_id']
                        cur.execute('''SELECT amount,invoice_date,created_at FROM supplier_invoices WHERE id=%s AND company_id=%s
                                       AND contract_version_id=%s AND offer_id=%s''',
                                    (document['source_supplier_invoice_id'], document['company_id'],
                                     document['contract_version_id'], document['offer_id']))
                        invoice = cur.fetchone()
                        if not invoice:
                            raise HTTPException(409, 'Исходный счёт отгрузки не найден')
                        amount = invoice['amount']
                        invoice_date = invoice.get('invoice_date') or invoice.get('created_at')
                    cur.execute('''SELECT CASE WHEN COUNT(*)>0 AND BOOL_AND(received_at IS NOT NULL
                                   AND COALESCE(status IN ('Принято','Проблема'), FALSE)) THEN MAX(received_at) END AS accepted_at
                                   FROM supply_deliveries WHERE source_supplier_invoice_id=%s AND company_id=%s
                                   AND contract_version_id=%s''',
                                (invoice_id, document['company_id'], document['contract_version_id']))
                    acceptance_date = cur.fetchone()['accepted_at']
                    try:
                        payment_schedule = schedule_projection(contract['snapshot'], amount, invoice_date, acceptance_date)
                    except ValueError:
                        raise HTTPException(409, 'График или сумма документа требуют проверки')
                return {'documentId': id, 'companyId': document['company_id'], 'paymentSchedule': payment_schedule,
                        'bindingStatus': 'bound' if contract else 'unbound',
                        'sourceSupplierInvoiceId': document.get('source_supplier_invoice_id'), 'contract': contract}
            finally:
                cur.close()
                conn.close()

    register('/supplier-invoices/{id}/contract-context', 'supplier_invoices', 'project_name')
    register('/supply-deliveries/{id}/contract-context', 'supply_deliveries', 'project')
