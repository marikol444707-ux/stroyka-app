"""Original-document line review for unused bound invoices, default-off routes."""
import re
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg2.extras import Json, RealDictCursor
from psycopg2.errors import LockNotAvailable

from ..supplier_deal_parties.access import build_deal_access
from .contract_context import load_invoice_contract
from .legacy_line_review import build_legacy_line_candidates, build_legacy_line_review


class LegacyLineReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: UUID
    contractVersionId: int = Field(strict=True, gt=0, le=2147483647)
    sourceFileId: int = Field(strict=True, gt=0, le=2147483647)
    expectedAmount: str = Field(pattern=r'^[0-9]+\.[0-9]{2}$', max_length=30)
    vatAmount: str = Field(pattern=r'^[0-9]+\.[0-9]{2}$', max_length=30)
    lines: list[dict] = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)
    confirmed: bool = Field(strict=True)

    @field_validator('reason')
    @classmethod
    def reason_required(cls, value):
        if not value.strip(): raise ValueError('Укажите основание проверки')
        return value.strip()

    @field_validator('confirmed')
    @classmethod
    def confirmed_required(cls, value):
        if value is not True: raise ValueError('Подтвердите сверку с оригиналом')
        return value


def register_legacy_line_review_routes(app, deps):
    company_actor, load_offer = build_deal_access(deps)

    def authorize(cur, invoice_id, user, header_id, header_mode):
        cur.execute('SELECT * FROM supplier_invoices WHERE id=%s', (invoice_id,))
        invoice = cur.fetchone()
        if not invoice: raise HTTPException(404, 'Счёт не найден')
        actor = company_actor(cur, user, invoice['company_id'], 'update', header_id, header_mode)
        deps['require_project_access'](actor, invoice.get('project_name') or '')
        if not deps['has_package_access'](actor, invoice.get('work_package') or 'Основная'):
            raise HTTPException(403, 'Нет доступа к разделу счёта')
        return invoice, actor

    def require_schema(cur):
        required=[('supplier_legacy_line_reviews',name) for name in
                  ('legacy_line_review_insert','legacy_line_review_complete','legacy_line_review_immutable','legacy_line_review_no_truncate')]
        required += [('supplier_invoice_line_specs','legacy_line_spec_insert')]
        cur.execute("""SELECT NOT EXISTS(SELECT 1 FROM unnest(%s::text[],%s::text[]) expected(table_name,trigger_name)
            WHERE NOT EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=to_regclass('public.'||expected.table_name)
                AND t.tgname=expected.trigger_name AND t.tgenabled IN ('O','A'))) AS ready""",
            ([table for table,_ in required],[name for _,name in required]))
        if not cur.fetchone()['ready']:raise HTTPException(503,'Схема сверки старых счетов не подготовлена')
        from .invoice_line_creation import require_invoice_line_schema
        from .receipt_vat_runtime import require_vat_schema
        require_invoice_line_schema(cur);require_vat_schema(cur)

    def context(cur, invoice, user, header_id, header_mode):
        bound = load_invoice_contract(cur, invoice['id'], invoice['company_id'])
        for company in sorted({bound['buyerCompanyId'],bound['payerCompanyId']} - {invoice['company_id']}):
            company_actor(cur, user, company, 'update')
        offer, _ = load_offer(cur, invoice['offer_id'], user, 'read', header_id, header_mode)
        if offer['status'] != 'Утверждено': raise HTTPException(409, 'КП должно быть утверждено')
        return bound

    def unused(cur, invoice):
        cur.execute('''SELECT
            EXISTS(SELECT 1 FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s)
            OR EXISTS(SELECT 1 FROM warehouse_invoices WHERE supplier_invoice_id=%s)
            OR EXISTS(SELECT 1 FROM supply_deliveries WHERE source_supplier_invoice_id=%s OR offer_id=%s)
            OR EXISTS(SELECT 1 FROM supplier_invoice_line_specs WHERE invoice_id=%s) AS used''',
            (invoice['id'],invoice['id'],invoice['id'],invoice['offer_id'],invoice['id']))
        if (cur.fetchone()['used'] or invoice['status']!='На утверждении'
                or invoice['paid_amount'] != 0 or invoice['warehouse_invoice_id'] is not None):
            raise HTTPException(409, 'Сверка строк доступна до утверждения, оплат и отгрузок счёта')
        if invoice['vat_amount'] is None:
            raise HTTPException(409, 'В старом счёте не сохранён НДС. Нужна отдельная сверка самого счёта')

    def sources(cur, invoice):
        cur.execute('''SELECT COALESCE(to_jsonb(o)->>'awarded_items_json',r.items_json) AS request_json,
            o.items_kp_json AS offer_json,o.total_price::NUMERIC AS offer_amount
            FROM supplier_offers o JOIN supply_requests r ON r.id=o.request_id AND r.company_id=o.company_id
            WHERE o.id=%s AND o.company_id=%s''', (invoice['offer_id'],invoice['company_id']))
        value = cur.fetchone()
        if not value: raise HTTPException(409, 'Не найдены исходные позиции КП')
        return dict(value)

    def attached_original(cur, invoice):
        match=re.fullmatch(r'/tenant-files/([1-9][0-9]*)/content',invoice.get('file_url') or '')
        if not match:
            return None
        cur.execute('''SELECT f.id,f.original_name,f.file_url FROM file_ownership f
            WHERE f.id=%s AND f.company_id=%s AND f.deletion_status='active'
              AND (f.project_id IS NULL OR f.project_id IN
                (SELECT id FROM projects WHERE company_id=%s AND name=%s))''',
            (int(match.group(1)),invoice['company_id'],invoice['company_id'],invoice['project_name']))
        row=cur.fetchone()
        return (dict(fileId=row['id'],name=row['original_name'] or 'Оригинал счёта',
                     url=f"/tenant-files/{row['id']}/content")
                if row else None)

    def result(cur, row, replayed=False):
        cur.execute('SELECT id FROM supplier_invoice_line_specs WHERE legacy_review_id=%s', (row['id'],))
        spec = cur.fetchone()
        if not spec: raise HTTPException(409, 'Сохранённая сверка требует проверки')
        return dict(invoiceId=row['invoice_id'],companyId=row['company_id'],requestId=str(row['request_id']),
                    reviewId=row['id'],specId=spec['id'],reviewed=True,replayed=replayed)

    @app.get('/supplier-invoices/{id}/legacy-line-review')
    def preview(id: Annotated[int, Path(gt=0)], current_user: dict=Depends(deps['get_current_user']),
                x_company_id: Annotated[Optional[str],Header(alias='X-Company-Id')]=None,
                x_company_mode: Annotated[Optional[str],Header(alias='X-Company-Mode')]=None):
        conn=deps['get_db']();conn.autocommit=False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                invoice,_=authorize(cur,id,current_user,x_company_id,x_company_mode)
                require_schema(cur)
                context(cur,invoice,current_user,x_company_id,x_company_mode)
                cur.execute('SELECT * FROM supplier_legacy_line_reviews WHERE invoice_id=%s',(id,))
                previous=cur.fetchone()
                if previous:return result(cur,previous,True)
                unused(cur,invoice)
                source=sources(cur,invoice)
                try:
                    spec=build_legacy_line_candidates(source['request_json'],source['offer_json'],
                        invoice_amount=invoice['amount'],offer_amount=source['offer_amount'],
                        work_package=invoice['work_package'])
                except ValueError:
                    raise HTTPException(409,'Состав КП и счёта требует сверки; автоматически восстановить строки нельзя') from None
                return dict(invoiceId=id,companyId=invoice['company_id'],contractVersionId=invoice['contract_version_id'],
                    amount=format(invoice['amount'],'.2f'),vatAmount=format(invoice['vat_amount'],'.2f'),
                    lines=spec['lines'],sourceFile=attached_original(cur,invoice),reviewed=False)
        finally:conn.rollback();conn.close()

    @app.post('/supplier-invoices/{id}/legacy-line-review')
    def review(id: Annotated[int,Path(gt=0)], data: LegacyLineReviewInput,
               current_user: dict=Depends(deps['get_current_user']),
               x_company_id: Annotated[Optional[str],Header(alias='X-Company-Id')]=None,
               x_company_mode: Annotated[Optional[str],Header(alias='X-Company-Mode')]=None):
        conn=deps['get_db']();conn.autocommit=False
        new_attempt=False;company_id=None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                initial,_=authorize(cur,id,current_user,x_company_id,x_company_mode)
                require_schema(cur)
                try:
                    cur.execute('''LOCK TABLE supplier_invoices,warehouse_invoices,supply_deliveries,
                        supplier_payment_documents,supplier_offers,supply_requests,supplier_contract_versions,
                        supplier_deal_parties,supplier_invoice_line_specs,supplier_invoice_lines,
                        supplier_legacy_line_reviews,file_ownership IN ACCESS EXCLUSIVE MODE NOWAIT''')
                except LockNotAvailable:
                    raise HTTPException(409,'Документы заняты другой операцией. Повторите запрос') from None
                cur.execute('SELECT pg_try_advisory_xact_lock(1735289201,%s) AS acquired',(initial['company_id'],))
                if not cur.fetchone()['acquired']:raise HTTPException(409,'Расчёты компании заняты другой операцией')
                invoice,actor=authorize(cur,id,current_user,x_company_id,x_company_mode)
                if invoice['company_id']!=initial['company_id']:raise HTTPException(409,'Компания счёта изменилась')
                context(cur,invoice,current_user,x_company_id,x_company_mode)
                command=data.model_dump(mode='json')
                cur.execute('SELECT * FROM supplier_legacy_line_reviews WHERE invoice_id=%s OR request_id=%s',(id,str(data.requestId)))
                previous=cur.fetchall()
                if previous:
                    row=previous[0]
                    if len(previous)!=1 or row['invoice_id']!=id or row['company_id']!=invoice['company_id'] or row['actor_id']!=actor['id'] or row['command_json']!=command:
                        raise HTTPException(409,'Сверка уже сохранена с другими данными')
                    return result(cur,row,True)
                new_attempt=True;company_id=invoice['company_id']
                unused(cur,invoice)
                if invoice['contract_version_id']!=data.contractVersionId or format(invoice['amount'],'.2f')!=data.expectedAmount:
                    raise HTTPException(409,'Договор или сумма счёта изменились')
                source=sources(cur,invoice)
                try:
                    payload=build_legacy_line_review(**source,invoice_amount=invoice['amount'],invoice_vat=invoice['vat_amount'],
                        work_package=invoice['work_package'],reviewed_lines=data.lines,reviewed_vat=data.vatAmount)
                except ValueError as error:raise HTTPException(409,str(error)) from None
                payload.update(sourceRequestJson=source['request_json'],sourceOfferJson=source['offer_json'],
                               sourceOfferAmount=format(source['offer_amount'],'.2f'),vatIncluded=invoice['vat_amount']>0)
                cur.execute('''SELECT f.id FROM file_ownership f WHERE f.id=%s AND f.company_id=%s AND f.deletion_status='active'
                    AND (f.project_id IS NULL OR f.project_id IN (SELECT id FROM projects WHERE company_id=%s AND name=%s))''',
                    (data.sourceFileId,company_id,company_id,invoice['project_name']))
                if not cur.fetchone():raise HTTPException(403,'Нет доступа к оригиналу счёта выбранной компании и объекта')
                cur.execute('''INSERT INTO supplier_legacy_line_reviews
                    (invoice_id,company_id,request_id,source_file_id,actor_id,reason,command_json,reviewed_payload)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (id,company_id,str(data.requestId),data.sourceFileId,actor['id'],data.reason,Json(command),Json(payload)))
                row=cur.fetchone()
                cur.execute('''INSERT INTO supplier_invoice_line_specs(company_id,invoice_id,row_count,amount,source_payload,legacy_review_id)
                    VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',(company_id,id,len(payload['lines']),payload['amount'],Json(payload),row['id']))
                spec_id=cur.fetchone()['id']
                for line in payload['lines']:
                    cur.execute('''INSERT INTO supplier_invoice_lines(spec_id,company_id,line_no,source_request_position,source_offer_position,
                        material_name,unit,work_package,quantity,unit_price,amount,vat_amount) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (spec_id,company_id,*[line[k] for k in ('lineNo','sourceRequestPosition','sourceOfferPosition',
                         'materialName','unit','workPackage','quantity','unitPrice','amount','vatAmount')]))
                cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s',(data.sourceFileId,))
                saved=result(cur,row)
                conn.commit();return saved
        except HTTPException as error:
            conn.rollback()
            if new_attempt and error.status_code in (400,403,409):
                raise HTTPException(error.status_code,dict(code='legacy_line_review_not_saved',message=error.detail,
                    companyId=company_id,invoiceId=id,requestId=str(data.requestId))) from None
            raise
        except Exception:conn.rollback();raise
        finally:conn.rollback();conn.close()
