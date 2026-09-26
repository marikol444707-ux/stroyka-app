"""Read-only prerequisites for the customer's human contract review form."""
import re
from typing import Annotated, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path

from .access import build_deal_access
from .routes import MAX_ID


def build_contract_review_context(deps):
    company_actor, load_offer = build_deal_access(deps)

    def review_context(
        id, current_user, x_company_id=None, x_company_mode=None,
    ):
        if current_user.get('role') == 'поставщик':
            raise HTTPException(403, 'Реквизиты заказчика проверяет его уполномоченный сотрудник')
        conn = deps['get_db']()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer, _ = load_offer(cur, id, current_user, 'read', x_company_id, x_company_mode)
            company_actor(cur, current_user, offer['company_id'], 'update', x_company_id, x_company_mode)
            if offer['status'] != 'Утверждено':
                raise HTTPException(409, 'Для проверки договора нужно утверждённое КП')
            cur.execute('SELECT * FROM supplier_deal_parties WHERE offer_id=%s ORDER BY version DESC LIMIT 1', (id,))
            parties = cur.fetchone()
            if not parties:
                raise HTTPException(409, 'Сначала выберите покупателя и плательщика сделки')
            for company_id in sorted({parties['buyer_company_id'], parties['payer_company_id']} - {offer['company_id']}):
                company_actor(cur, current_user, company_id, 'update')
            cur.execute('SELECT company_id,full_name,inn FROM company_requisites WHERE company_id=ANY(%s)',
                        ([parties['buyer_company_id'], parties['payer_company_id']],))
            companies = {row['company_id']: row for row in cur.fetchall()}
            cur.execute('SELECT name,inn FROM suppliers WHERE id=%s', (offer['supplier_id'],))
            supplier = cur.fetchone() or {}

            def legal_identity(row, name):
                inn = str(row.get('inn') or '').strip()
                if not re.fullmatch(r'(?:[0-9]{10}|[0-9]{12})', inn):
                    raise HTTPException(409, 'Заполните корректный ИНН всех сторон в карточках организаций')
                return {'fullName': str(row.get(name) or '').strip(), 'inn': inn}

            identities = {side: {**legal_identity(companies.get(parties[side + '_company_id'], {}), 'full_name'),
                                 'companyId': parties[side + '_company_id']} for side in ('buyer', 'payer')}
            identities['supplier'] = {**legal_identity(supplier, 'name'), 'supplierId': offer['supplier_id']}
            cur.execute('SELECT COALESCE(MAX(version),0) AS version FROM supplier_contract_versions WHERE offer_id=%s', (id,))
            return {'offerId': id, 'companyId': offer['company_id'], 'partyVersion': parties['version'],
                    'expectedVersion': cur.fetchone()['version'], 'identitySource': 'company_profiles', **identities}
        finally:
            cur.close()
            conn.close()
    return review_context


def register_contract_review_context(app, deps):
    load_context = build_contract_review_context(deps)

    @app.get('/supplier-offers/{id}/contract-review-context')
    def review_context(
        id: Annotated[int, Path(gt=0, le=MAX_ID)],
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        return load_context(id, current_user, x_company_id, x_company_mode)
