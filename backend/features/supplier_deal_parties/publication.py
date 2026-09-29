"""Publication addresses a version to its existing supplier, never to a caller-provided ID."""
from typing import Annotated, Optional
import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field
from .access import build_deal_access


def supplier_version_visible(alias='v'):
    if alias not in ('v','c'):
        raise ValueError('Unknown contract alias')
    # Saving a reviewed version addresses it to the supplier of that exact offer.
    # Callers must additionally apply live offer/company/manager authorization.
    return f"""EXISTS (SELECT 1 FROM supplier_offers recipient_offer
        WHERE recipient_offer.id={alias}.offer_id AND recipient_offer.company_id={alias}.company_id
          AND recipient_offer.supplier_id::text={alias}.snapshot_json #>> '{{supplier,supplierId}}')"""

class PublishDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: bool = Field(strict=True)


def register_contract_publication(app,deps):
    _,load_offer=build_deal_access(deps)
    @app.post('/supplier-offers/{id}/contracts/{version_id}/publish')
    def publish(id:Annotated[int,Path(gt=0,le=2147483647)],
                version_id:Annotated[int,Path(gt=0,le=2147483647)], data:PublishDecision,
                current_user:dict=Depends(deps['get_current_user']),
                x_company_id:Optional[str]=Header(None,alias='X-Company-Id'),
                x_company_mode:Optional[str]=Header(None,alias='X-Company-Mode')):
        if not data.confirmed:
            raise HTTPException(422,'Подтвердите передачу этой версии поставщику')
        conn=deps['get_db']();conn.autocommit=False
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer,actor=load_offer(cur,id,current_user,'update',x_company_id,x_company_mode)
            cur.execute('SELECT pg_advisory_xact_lock(73164,%s)',(offer['company_id'],))
            cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s AND offer_id=%s AND company_id=%s',(version_id,id,offer['company_id']))
            contract=cur.fetchone()
            if not contract:
                raise HTTPException(404,'Версия договора не найдена')
            cur.execute('SELECT contract_version_id FROM supplier_contract_publications WHERE contract_version_id=%s AND company_id=%s AND snapshot_hash=%s',(version_id,offer['company_id'],contract['snapshot_hash']))
            if not cur.fetchone():
                cur.execute('SELECT MAX(version) AS latest FROM supplier_contract_versions WHERE offer_id=%s',(id,))
                if cur.fetchone()['latest']!=contract['version']:
                    raise HTTPException(409,'Есть новая версия договора. Откройте её перед передачей')
                cur.execute('SELECT 1 FROM supplier_contract_registry_versions m JOIN supplier_contract_registry r ON r.id=m.registry_id AND r.company_id=m.company_id WHERE m.contract_version_id=%s AND m.company_id=%s AND r.archived',(version_id,offer['company_id']))
                if cur.fetchone():
                    raise HTTPException(422,'Договор в архиве. Сначала восстановите его')
                snapshot=contract['snapshot_json']
                if snapshot.get('supplier',{}).get('supplierId')!=offer['supplier_id']:
                    raise HTTPException(409,'Поставщик договора не совпадает с КП')
                files=[contract['source_file_id']]+[a['sourceFileId'] for a in snapshot.get('addenda',[])]
                for file_id in sorted(set(files)):
                    cur.execute("SELECT id FROM file_ownership WHERE id=%s AND company_id=%s AND COALESCE(deletion_status,'active')='active' FOR SHARE",(file_id,offer['company_id']))
                    if not cur.fetchone():
                        raise HTTPException(403,'Один из файлов договора недоступен')
                cur.execute('INSERT INTO supplier_contract_publications (contract_version_id,company_id,snapshot_hash,published_by_id,published_by) VALUES (%s,%s,%s,%s,%s)',(version_id,offer['company_id'],contract['snapshot_hash'],actor['id'],actor.get('name') or ''))
            conn.commit()
            return {'contractId':version_id,'companyId':offer['company_id'],'offerId':id,'published':True}
        except Exception:
            conn.rollback();raise
        finally:
            cur.close();conn.close()
