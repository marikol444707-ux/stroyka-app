"""Versioned party proposals; never rewrite invoice/payment ownership."""
from typing import Annotated, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .access import build_deal_access


MAX_ID = 2147483647


class PartyDraftInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    buyerCompanyId: int = Field(strict=True, gt=0, le=MAX_ID)
    payerCompanyId: int = Field(strict=True, gt=0, le=MAX_ID)
    expectedVersion: int = Field(strict=True, ge=0, lt=MAX_ID)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def nonempty_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Укажите основание выбора сторон')
        return value


def serialize(offer, draft):
    draft = draft or {}
    return {
        'offerId': offer['id'], 'requestId': offer['request_id'],
        'companyId': offer['company_id'], 'supplierId': offer['supplier_id'],
        'buyerCompanyId': draft.get('buyer_company_id'),
        'payerCompanyId': draft.get('payer_company_id'),
        'version': draft.get('version', 0),
        'status': 'draft' if draft else 'not_configured',
        'appliedToAccounting': False,
        'reason': draft.get('reason', ''), 'createdBy': draft.get('created_by', ''),
        'createdAt': str(draft['created_at']) if draft.get('created_at') else None,
    }


def register_supplier_deal_parties_module(app, deps):
    get_db = deps['get_db']
    get_current_user = deps['get_current_user']
    company_actor, load_authorized_offer = build_deal_access(deps)

    def latest(cur, offer_id):
        cur.execute('''SELECT * FROM supplier_deal_parties
                       WHERE offer_id=%s ORDER BY version DESC LIMIT 1''', (offer_id,))
        return cur.fetchone()

    @app.get('/supplier-offers/{id}/parties')
    def get_parties(
        id: Annotated[int, Path(gt=0, le=MAX_ID)],
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer, _ = load_authorized_offer(cur, id, current_user, 'read', x_company_id, x_company_mode)
            return serialize(offer, latest(cur, id))
        finally:
            cur.close()
            conn.close()

    @app.put('/supplier-offers/{id}/parties')
    def propose_parties(
        id: Annotated[int, Path(gt=0, le=MAX_ID)], data: PartyDraftInput,
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer, actor = load_authorized_offer(cur, id, current_user, 'update', x_company_id, x_company_mode)
            if offer['status'] != 'Утверждено':
                raise HTTPException(409, 'Стороны сделки задаются для утверждённого КП')
            # The selected owner header must not be reused as the payer header.
            # Resolve authority independently; existing account/membership rules apply.
            for company_id in sorted({data.buyerCompanyId, data.payerCompanyId} - {offer['company_id']}):
                company_actor(cur, current_user, company_id, 'update')
            previous = latest(cur, id)
            version = previous['version'] if previous else 0
            if data.expectedVersion != version:
                raise HTTPException(409, 'Стороны сделки уже изменены. Обновите карточку')
            cur.execute('''INSERT INTO supplier_deal_parties
                           (offer_id,company_id,request_id,supplier_id,buyer_company_id,
                            payer_company_id,version,reason,created_by_id,created_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                        (id, offer['company_id'], offer['request_id'], offer['supplier_id'],
                         data.buyerCompanyId, data.payerCompanyId, version + 1, data.reason,
                         actor.get('id'), actor.get('name') or actor.get('email') or ''))
            result = serialize(offer, cur.fetchone())
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get('/supplier-offers/{id}/parties/history')
    def party_history(
        id: Annotated[int, Path(gt=0, le=MAX_ID)],
        beforeVersion: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        current_user: dict = Depends(get_current_user),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer, _ = load_authorized_offer(cur, id, current_user, 'read', x_company_id, x_company_mode)
            cur.execute('''SELECT * FROM supplier_deal_parties WHERE offer_id=%s
                           AND version < %s ORDER BY version DESC LIMIT %s''',
                        (id, beforeVersion or MAX_ID, limit + 1))
            rows = cur.fetchall()
            items = [serialize(offer, row) for row in rows[:limit]]
            return {'items': items, 'nextBeforeVersion': items[-1]['version'] if len(rows) > limit else None}
        finally:
            cur.close()
            conn.close()
