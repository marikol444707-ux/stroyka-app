"""Supplier-card originals, sharing the immutable contract registry with offers."""
import datetime as dt
import hashlib
import json
from typing import Annotated, Optional
from uuid import UUID
import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict, Field
from .access import build_deal_access
from .contracts import LegalParty, ContractReview, build_snapshot, serialize_contract
from .contract_applicability import ContractApplicability
from .contract_addenda import Addendum, reviewed_addenda
from .contract_registry import attach_registry
from .contract_extraction import extract_contract_parties
from .contract_text_source import read_contract_text
from ..company_requisites.service import company_requisites_to_api

class OriginalInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requestId:UUID
    sourceFileId:int=Field(strict=True,gt=0)
    number:str=Field(min_length=1,max_length=100)
    date:dt.date
    buyer:LegalParty
    supplier:LegalParty
    paymentTerms:str=Field(default='',max_length=4000)
    applicability:ContractApplicability
    reviewConfirmed:bool=Field(strict=True)
    revisesContractId:Optional[int]=Field(default=None,strict=True,gt=0)
    addendum:Optional[Addendum]=None

class OriginalRecognition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sourceFileId:int=Field(strict=True,gt=0)


def register_supplier_originals(app,deps):
    from .cabinet_contracts import register_cabinet_contracts
    register_cabinet_contracts(app, deps)
    company_actor,_=build_deal_access(deps)
    def authorize(cur,company,supplier,user,action,header,mode):
        if user.get('role')=='поставщик':
            raise HTTPException(403,'Договор в карточке проверяет сотрудник покупателя')
        actor=company_actor(cur,user,company,action,header,mode)
        cur.execute('''SELECT s.* FROM company_supplier_links l JOIN suppliers s ON s.id=l.supplier_id
            JOIN companies c ON c.id=l.company_id AND c.platform_account_id=l.platform_account_id
            WHERE l.company_id=%s AND l.supplier_id=%s FOR SHARE OF l,c,s''',(company,supplier))
        row=cur.fetchone()
        if not row:raise HTTPException(404,'Поставщик не найден в выбранной компании')
        return actor,dict(row)

    def profile(cur,company,supplier):
        cur.execute('SELECT * FROM company_requisites WHERE company_id=%s FOR SHARE',(company,))
        buyer=cur.fetchone() or {}
        def clean(row):
            value=company_requisites_to_api(row)
            return {key:value.get(key,'') for key in LegalParty.model_fields}
        return {'buyer':clean(buyer),'supplier':clean({**supplier,'full_name':supplier.get('name'),
            'bank_name':supplier.get('bank'),'rs':supplier.get('account'),'ks':supplier.get('kor_account')})}

    def source_file(cur,company,file_id):
        cur.execute("SELECT *,COALESCE(deletion_status,'active') AS state FROM file_ownership WHERE id=%s AND company_id=%s",(file_id,company))
        row=cur.fetchone()
        if not row or row['state']!='active':raise HTTPException(403,'Файл недоступен')
        if row.get('project_id'):raise HTTPException(422,'Для общего договора загрузите файл без привязки к объекту')
        return dict(row)

    def connection():
        conn=deps['get_db']();conn.autocommit=False
        return conn,conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base='/companies/{company}/suppliers/{supplier}/contracts'
    @app.get(base)
    def listing(company:Annotated[int,Path(gt=0)],supplier:Annotated[int,Path(gt=0)],
                user:dict=Depends(deps['get_current_user']),
                header:Optional[str]=Header(None,alias='X-Company-Id'),mode:Optional[str]=Header(None,alias='X-Company-Mode')):
        conn,cur=connection()
        try:
            authorize(cur,company,supplier,user,'read',header,mode)
            cur.execute("""SELECT v.*,r.id AS registry_id,COALESCE(r.archived,FALSE) AS archived
                FROM supplier_contract_versions v
                LEFT JOIN supplier_contract_registry_versions m ON m.contract_version_id=v.id AND m.company_id=v.company_id
                LEFT JOIN supplier_contract_registry r ON r.id=m.registry_id AND r.company_id=m.company_id
                LEFT JOIN supplier_offers o ON o.id=v.offer_id AND o.company_id=v.company_id
                WHERE v.company_id=%s AND COALESCE(r.supplier_id,o.supplier_id)=%s
                  AND (r.id IS NULL OR NOT EXISTS (SELECT 1 FROM supplier_contract_registry_versions n
                    WHERE n.registry_id=r.id AND n.company_id=r.company_id AND n.contract_version_id>v.id))
                  AND (v.offer_id IS NULL OR NOT EXISTS (SELECT 1 FROM supplier_contract_versions n WHERE n.offer_id=v.offer_id AND n.version>v.version))
                ORDER BY v.reviewed_at DESC,v.id DESC LIMIT 101""",(company,supplier))
            rows=cur.fetchall()
            if len(rows)>100:raise HTTPException(409,'Слишком много договоров. Откройте архив документов.')
            _,supplier_row=authorize(cur,company,supplier,user,'read',header,mode)
            return {'companyId':company,'supplierId':supplier,'items':[{**serialize_contract(r),'archived':r['archived']} for r in rows],**profile(cur,company,supplier_row)}
        finally:conn.rollback();cur.close();conn.close()

    @app.post(base+'/recognize')
    def recognize(company:Annotated[int,Path(gt=0)],supplier:Annotated[int,Path(gt=0)],data:OriginalRecognition,response:Response,
                  user:dict=Depends(deps['get_current_user']),header:Optional[str]=Header(None,alias='X-Company-Id'),mode:Optional[str]=Header(None,alias='X-Company-Mode')):
        conn,cur=connection()
        try:
            _,supplier_row=authorize(cur,company,supplier,user,'update',header,mode)
            identities=profile(cur,company,supplier_row)
            row=source_file(cur,company,data.sourceFileId)
            # Release read locks before bounded OCR, then re-authorize its result.
            conn.rollback()
            text,digest=read_contract_text(row,deps)
            _,latest=authorize(cur,company,supplier,user,'update',header,mode)
            if source_file(cur,company,data.sourceFileId)!=row or profile(cur,company,latest)!=identities:
                raise HTTPException(409,'Файл или реквизиты изменились. Повторите распознавание.')
            result=extract_contract_parties(text,{'buyer':identities['buyer']['inn'],'payer':identities['buyer']['inn'],'supplier':identities['supplier']['inn']})
            response.headers['Cache-Control']='private, no-store'
            return {**result,'companyId':company,'supplierId':supplier,'sourceFileId':data.sourceFileId,'sourceContentHash':digest}
        finally:conn.rollback();cur.close();conn.close()

    @app.post(base)
    def save(company:Annotated[int,Path(gt=0)],supplier:Annotated[int,Path(gt=0)],data:OriginalInput,
             user:dict=Depends(deps['get_current_user']),header:Optional[str]=Header(None,alias='X-Company-Id'),mode:Optional[str]=Header(None,alias='X-Company-Mode')):
        conn,cur=connection()
        try:
            actor,supplier_row=authorize(cur,company,supplier,user,'update',header,mode)
            cur.execute('SELECT pg_advisory_xact_lock(73164,%s)',(company,))
            actor,supplier_row=authorize(cur,company,supplier,user,'update',header,mode)
            # Exact request equality is retained for safe retries after a lost response.
            request_payload=hashlib.sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()
            cur.execute('SELECT * FROM supplier_contract_versions WHERE company_id=%s AND request_id=%s',(company,str(data.requestId)))
            previous=cur.fetchone()
            if previous:
                if previous['snapshot_json'].get('supplierCardRequestHash')!=request_payload or previous['snapshot_json']['supplier']['supplierId']!=supplier:raise HTTPException(409,'Этот запрос уже использован для другого сохранения')
                return serialize_contract(previous)
            if not data.reviewConfirmed:raise HTTPException(422,'Проверьте реквизиты перед сохранением')
            current=profile(cur,company,supplier_row)
            if data.buyer.inn!=current['buyer']['inn'] or data.supplier.inn!=current['supplier']['inn']:
                raise HTTPException(409,'ИНН изменился. Обновите карточку')
            if data.applicability.scope!='company':raise HTTPException(422,'В карточке поставщика сохраняется общий договор компании')
            cur.execute('SELECT id FROM file_ownership WHERE id=%s FOR UPDATE',(data.sourceFileId,))
            source_file(cur,company,data.sourceFileId)
            source=None
            if data.revisesContractId:
                cur.execute('''SELECT v.* FROM supplier_contract_versions v
                    LEFT JOIN supplier_contract_registry_versions m ON m.contract_version_id=v.id AND m.company_id=v.company_id
                    LEFT JOIN supplier_contract_registry r ON r.id=m.registry_id AND r.company_id=m.company_id
                    LEFT JOIN supplier_offers o ON o.id=v.offer_id AND o.company_id=v.company_id
                    WHERE v.id=%s AND v.company_id=%s AND COALESCE(r.supplier_id,o.supplier_id)=%s''',(data.revisesContractId,company,supplier))
                source=cur.fetchone()
                if not source:raise HTTPException(404,'Исходный договор недоступен')
            elif data.addendum:raise HTTPException(422,'Выберите основной договор')
            review=ContractReview(partyVersion=1,expectedVersion=0,sourceFileId=data.sourceFileId,number=data.number,date=data.date,
                buyer=data.buyer,payer=data.buyer,supplier=data.supplier,paymentTerms=data.paymentTerms,applicability=data.applicability,
                reviewConfirmed=True,reason='Проверено в карточке поставщика',revisesContractId=data.revisesContractId,addendum=data.addendum)
            parties={'supplier_id':supplier,'buyer_company_id':company,'payer_company_id':company}
            addenda=reviewed_addenda(cur,source,review,company,None)
            snapshot=build_snapshot(review,parties)
            if addenda:snapshot['addenda']=addenda
            if source and source['snapshot_json'].get('paymentSchedule'):
                raise HTTPException(409,'График оплаты относится к КП. Измените этот договор в исходной сделке.')
            if source:snapshot['revises']={'contractId':source['id'],'offerId':source['offer_id'],'version':source['version'],'snapshotHash':source['snapshot_hash']}
            snapshot['supplierCardRequestHash']=request_payload
            encoded=json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            cur.execute('''INSERT INTO supplier_contract_versions
                (company_id,offer_id,party_version,version,source_file_id,snapshot_json,snapshot_hash,reason,reviewed_by_id,reviewed_by,request_id)
                VALUES (%s,NULL,NULL,%s,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING *''',
                (company,(source['version']+1) if source else 1,data.sourceFileId,encoded,hashlib.sha256(encoded.encode()).hexdigest(),
                 review.reason,actor['id'],actor.get('name') or '',str(data.requestId)))
            saved=cur.fetchone();registry_id=attach_registry(cur,saved,parties,source)
            cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s',(data.sourceFileId,))
            conn.commit()
            return serialize_contract({**saved,'registry_id':registry_id})
        except Exception:conn.rollback();raise
        finally:cur.close();conn.close()
