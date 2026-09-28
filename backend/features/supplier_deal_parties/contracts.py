"""Human-reviewed contract data, separate from signatures and accounting."""
import datetime as dt
import hashlib
import json
import os
from typing import Annotated, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .access import build_deal_access
from .routes import MAX_ID
from .review_context import register_contract_review_context
from .contract_provenance import RecognitionReview, prepare_contract_provenance
from .payment_schedule import PaymentSchedule
from .contract_registry import attach_registry
from .contract_addenda import Addendum, reviewed_addenda
from .contract_applicability import ContractApplicability, offer_project, eligible_applicability


class LegalParty(BaseModel):
    # Do not use profile normalization here: it invents missing signer defaults.
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    fullName: str = Field(min_length=1, max_length=500)
    inn: str = Field(pattern=r'^(?:[0-9]{10}|[0-9]{12})$')
    kpp: str = Field(default='', pattern=r'^(?:[0-9]{9})?$')
    ogrn: str = Field(default='', pattern=r'^(?:[0-9]{13}|[0-9]{15})?$')
    legalAddress: str = Field(default='', max_length=2000)
    bankName: str = Field(default='', max_length=500)
    bik: str = Field(default='', pattern=r'^(?:[0-9]{9})?$')
    rs: str = Field(default='', pattern=r'^(?:[0-9]{20})?$')
    ks: str = Field(default='', pattern=r'^(?:[0-9]{20})?$')
    directorName: str = Field(default='', max_length=255)
    directorPosition: str = Field(default='', max_length=255)
    basis: str = Field(default='', max_length=1000)
    phone: str = Field(default='', max_length=100)
    email: str = Field(default='', max_length=255)


class ContractReview(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    partyVersion: int = Field(strict=True, gt=0, le=MAX_ID)
    expectedVersion: int = Field(strict=True, ge=0, lt=MAX_ID)
    sourceFileId: int = Field(strict=True, gt=0, le=MAX_ID)
    number: str = Field(min_length=1, max_length=100)
    date: dt.date
    reviewConfirmed: bool = Field(strict=True)
    buyer: LegalParty
    payer: LegalParty
    supplier: LegalParty
    paymentTerms: str = Field(default='', max_length=4000)
    reason: str = Field(min_length=1, max_length=1000)
    recognitionReview: Optional[RecognitionReview] = None
    reusedFromContractId: Optional[int] = Field(default=None, strict=True, gt=0, le=MAX_ID)
    revisesContractId: Optional[int] = Field(default=None, strict=True, gt=0, le=MAX_ID)
    addendum: Optional[Addendum] = None
    paymentSchedule: Optional[PaymentSchedule] = None
    applicability: Optional[ContractApplicability] = None

    @model_validator(mode='after')
    def one_source(self):
        if self.addendum is not None and self.revisesContractId is None:
            raise ValueError('Для допсоглашения выберите текущий договор')
        if self.reusedFromContractId is not None and self.revisesContractId is not None:
            raise ValueError('Выберите один исходный договор')
        return self

    @field_validator('reviewConfirmed')
    @classmethod
    def must_review(cls, value):
        if not value:
            raise ValueError('Требуется проверка данных человеком')
        return value


def build_snapshot(review, parties):
    result = {
        'number': review.number, 'date': review.date.isoformat(),
        'buyer': {**review.buyer.model_dump(), 'companyId': parties['buyer_company_id']},
        'payer': {**review.payer.model_dump(), 'companyId': parties['payer_company_id']},
        'supplier': {**review.supplier.model_dump(), 'supplierId': parties['supplier_id']},
        'paymentTerms': review.paymentTerms,
        'signatureStatus': 'not_verified', 'appliedToAccounting': False,
    }
    result['missingRequisites'] = [
        f'{side}.{field}' for side in ('buyer','payer','supplier')
        for field in ('legalAddress','bankName','bik','rs','ks','directorName','basis')
        if not result[side][field]
    ]
    if review.applicability is not None:
        result['applicability'] = review.applicability.model_dump(mode='json')
    if review.paymentSchedule is not None:
        result['paymentSchedule'] = review.paymentSchedule.model_dump()
    return result


def serialize_contract(row):
    return {
        'registryId': row.get('registry_id'),
        'id': row['id'], 'offerId': row['offer_id'], 'companyId': row['company_id'],
        'version': row['version'], 'partyVersion': row['party_version'],
        'sourceFileId': row['source_file_id'],
        'sourceFileUrl': f"/tenant-files/{row['source_file_id']}/content",
        'status': 'reviewed', 'snapshot': row['snapshot_json'],
        'snapshotHash': row['snapshot_hash'], 'reason': row['reason'],
        'reviewedBy': row['reviewed_by'], 'reviewedAt': str(row['reviewed_at']),
    }


def register_supplier_contracts_module(app, deps):
    register_contract_review_context(app, deps)
    get_db = deps['get_db']
    company_actor, load_offer = build_deal_access(deps)

    @app.post('/supplier-offers/{id}/contracts')
    def review_contract(
        id: Annotated[int, Path(gt=0, le=MAX_ID)], data: ContractReview,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        if data.paymentSchedule is not None and not (
            os.getenv('SUPPLIER_PAYMENT_SCHEDULES_ENABLED') == '1'
            and os.getenv('SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED') == '1'
        ):
            raise HTTPException(409, 'Сохранение графиков оплаты ещё не включено')
        evidence, source_row = prepare_contract_provenance(
            deps, id, data, current_user, x_company_id, x_company_mode)
        conn = get_db()
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer, actor = load_offer(cur, id, current_user, 'update', x_company_id, x_company_mode)
            cur.execute('SELECT pg_advisory_xact_lock(73164,%s)', (offer['company_id'],))
            if offer['status'] != 'Утверждено':
                raise HTTPException(409, 'Договор привязывается к утверждённому КП')
            cur.execute('SELECT * FROM supplier_deal_parties WHERE offer_id=%s ORDER BY version DESC LIMIT 1', (id,))
            parties = cur.fetchone()
            if not parties or parties['version'] != data.partyVersion:
                raise HTTPException(409, 'Состав сторон изменился или не задан. Обновите карточку')
            for company_id in sorted({parties['buyer_company_id'], parties['payer_company_id']} - {offer['company_id']}):
                company_actor(cur, current_user, company_id, 'update')
            cur.execute('SELECT COALESCE(MAX(version),0) AS version FROM supplier_contract_versions WHERE offer_id=%s', (id,))
            version = cur.fetchone()['version']
            if version != data.expectedVersion:
                raise HTTPException(409, 'Версия договора изменилась. Обновите карточку')
            cur.execute('''SELECT company_id,inn FROM company_requisites
                           WHERE company_id=ANY(%s) FOR SHARE''',
                        ([parties['buyer_company_id'], parties['payer_company_id']],))
            identities = {row['company_id']: str(row['inn'] or '').strip() for row in cur.fetchall()}
            for side in ('buyer', 'payer'):
                if identities.get(parties[side + '_company_id']) != getattr(data, side).inn:
                    raise HTTPException(409, 'ИНН стороны договора не совпадает с выбранным юрлицом или не заполнен в его реквизитах')
            cur.execute('SELECT inn FROM suppliers WHERE id=%s FOR SHARE', (offer['supplier_id'],))
            supplier = cur.fetchone()
            if not supplier or str(supplier['inn'] or '').strip() != data.supplier.inn:
                raise HTTPException(409, 'ИНН договора не совпадает с выбранным поставщиком или не заполнен')
            cur.execute('''SELECT *,COALESCE(deletion_status,'active') AS deletion_status
                           FROM file_ownership WHERE id=%s FOR UPDATE''', (data.sourceFileId,))
            file = cur.fetchone()
            if not file or file['company_id'] != offer['company_id'] or file['deletion_status'] != 'active':
                raise HTTPException(403, 'Нет доступа к активному файлу договора')
            if source_row is not None and any(file.get(key) != value for key, value in source_row.items()):
                raise HTTPException(409, 'Исходный файл изменился. Повторите распознавание и проверку')
            if file['project_id']:
                cur.execute('SELECT id FROM projects WHERE id=%s AND company_id=%s AND name=%s',
                            (file['project_id'], offer['company_id'], offer['project']))
                if not cur.fetchone():
                    raise HTTPException(403, 'Файл относится к другому объекту')
            if (parties['buyer_company_id'] == parties['payer_company_id']
                    and data.buyer != data.payer):
                raise HTTPException(409, 'Реквизиты покупателя и плательщика одной компании должны совпадать')
            project = offer_project(cur, offer) if data.applicability is not None else None
            if data.applicability is not None:
                if data.applicability.scope == 'project' and (not project or project['id'] != data.applicability.projectId):
                    raise HTTPException(422, 'Выберите объект этой сделки')
                if file['project_id'] and (data.applicability.scope != 'project' or data.applicability.projectId != file['project_id']):
                    raise HTTPException(422, 'Этот оригинал доступен только для своего объекта')
            registry_source = None
            revised_from = None
            if data.revisesContractId is not None:
                cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s AND company_id=%s AND offer_id=%s AND version=%s',
                            (data.revisesContractId,offer['company_id'],id,data.expectedVersion))
                registry_source = cur.fetchone()
                if registry_source is None:
                    raise HTTPException(422, 'Исходная версия договора изменилась. Откройте договор заново')
                revised_from = {'contractId':registry_source['id'],'offerId':id,
                                'version':registry_source['version'],'snapshotHash':registry_source['snapshot_hash']}
            reused_from = None
            if data.reusedFromContractId is not None:
                cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s AND company_id=%s',
                            (data.reusedFromContractId, offer['company_id']))
                source = cur.fetchone()
                if not source or source['offer_id'] == id or source['source_file_id'] != data.sourceFileId:
                    raise HTTPException(409, 'Выбранный договор недоступен. Выберите его заново')
                load_offer(cur, source['offer_id'], current_user, 'read', x_company_id, x_company_mode)
                old = source['snapshot_json']
                if (not eligible_applicability(old, project['id'] if project else None)
                    or data.applicability is None
                    or data.applicability.model_dump(mode='json') != old.get('applicability')):
                    raise HTTPException(422, 'Срок или область действия договора не подходят. Проверьте новую версию договора')
                if (old.get('paymentSchedule') or any(
                    old.get(side, {}).get(key) != value for side, key, value in (
                        ('buyer', 'companyId', parties['buyer_company_id']),
                        ('payer', 'companyId', parties['payer_company_id']),
                        ('supplier', 'supplierId', offer['supplier_id']),
                        ('buyer', 'inn', data.buyer.inn), ('payer', 'inn', data.payer.inn),
                        ('supplier', 'inn', data.supplier.inn)))):
                    raise HTTPException(409, 'Этот договор не подходит к выбранной сделке')
                registry_source = source
                reused_from = {'contractId': source['id'], 'offerId': source['offer_id'],
                               'version': source['version'], 'snapshotHash': source['snapshot_hash']}
            addenda = reviewed_addenda(cur, registry_source, data, offer['company_id'], project)
            snapshot = build_snapshot(data, parties)
            if addenda:
                snapshot['addenda'] = addenda
            if revised_from is not None:
                snapshot['revises'] = revised_from
            if reused_from is not None:
                snapshot['reusedFrom'] = reused_from
            if evidence is not None:
                snapshot['recognitionReview'] = evidence
            encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            digest = hashlib.sha256(encoded.encode()).hexdigest()
            cur.execute('''INSERT INTO supplier_contract_versions
                (offer_id,company_id,party_version,version,source_file_id,snapshot_json,snapshot_hash,
                 reason,reviewed_by_id,reviewed_by)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) RETURNING *''',
                        (id,offer['company_id'],data.partyVersion,version+1,data.sourceFileId,
                         encoded,digest,data.reason,actor['id'],actor.get('name') or actor.get('email') or ''))
            saved = cur.fetchone()
            registry_id = attach_registry(cur, saved, parties, registry_source)
            result = serialize_contract({**saved,'registry_id':registry_id})
            cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s', (data.sourceFileId,))
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    @app.get('/supplier-offers/{id}/contracts')
    def list_contracts(
        id: Annotated[int, Path(gt=0, le=MAX_ID)],
        beforeVersion: Annotated[Optional[int], Query(gt=0, le=MAX_ID)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            load_offer(cur, id, current_user, 'read', x_company_id, x_company_mode)
            cur.execute('''SELECT c.*,m.registry_id FROM supplier_contract_versions c
                           LEFT JOIN supplier_contract_registry_versions m ON m.contract_version_id=c.id AND m.company_id=c.company_id
                           WHERE c.offer_id=%s AND c.version < %s ORDER BY c.version DESC LIMIT %s''',
                        (id,beforeVersion if beforeVersion is not None else MAX_ID + 1,limit+1))
            rows = cur.fetchall()
            items = [serialize_contract(row) for row in rows[:limit]]
            return {'items':items, 'nextBeforeVersion':items[-1]['version'] if len(rows)>limit else None}
        finally:
            cur.close()
            conn.close()
