"""Admin entry for company-local grouping; never grants historical cabinet access."""
import hashlib
import json

from fastapi import Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, StrictBool, constr

from .connections import authorities, company_lock, is_admin, source_link
from .history_merge import Id, transaction
from ..supplier_access import company_merge
from ..supplier_access.legal_identity import canonical_legal, legal_sql


class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    targetSupplierId: Id


class Confirmation(Review):
    expectedReview: constr(min_length=64,max_length=64)
    confirmed: StrictBool
    reason: constr(strip_whitespace=True,min_length=10,max_length=1000)


def checked_preview(cur,user,company_id,source_id,target_id):
    company=company_lock(cur,company_id)
    # Resolve company-local provenance before inspecting or locking identities.
    for sid in sorted({source_id,target_id}):
        source_link(cur,company,sid)
    suppliers,users=authorities(cur,source_id,target_id,[user['id']])
    actor=users.get(user['id'])
    if not is_admin(actor):
        raise HTTPException(403,'Полномочия администратора изменились')
    if not company['active']:
        raise HTTPException(409,'Компания отключена')
    review=company_merge.preview(cur,company,target_id,source_id)
    review.update(sourceInn=suppliers[source_id]['inn'] or '',targetInn=suppliers[target_id]['inn'] or '')
    review['canCompleteInn']=bool(review['hasSupplierAccount'] and not review['targetInn'].strip()
        and canonical_legal(review['sourceInn'], (10, 12)))
    # Includes legal values and actor epoch so changed identity/authority demands review.
    evidence=dict(review,actorEpoch=actor['supplier_team_epoch'],
                  identities={sid:{key:suppliers[sid][key] for key in ('inn','ogrn','user_id')}
                              for sid in sorted(suppliers)})
    review['reviewVersion']=hashlib.sha256(json.dumps(evidence,sort_keys=True,default=str).encode()).hexdigest()
    return review


def register_duplicate_merge(app,deps,admin):
    @app.post('/system/companies/{company_id}/participants/{source_id}/duplicate-preview')
    def preview(data:Review,company_id:int=Path(...,ge=1),source_id:int=Path(...,ge=1),user:dict=Depends(admin)):
        with transaction(deps) as cur:
            return checked_preview(cur,user,company_id,source_id,data.targetSupplierId)

    @app.post('/system/companies/{company_id}/participants/{source_id}/duplicate-complete-inn')
    def complete_inn(data:Confirmation,company_id:int=Path(...,ge=1),source_id:int=Path(...,ge=1),user:dict=Depends(admin)):
        if not data.confirmed:
            raise HTTPException(422,'Подтвердите ИНН по документу кабинета')
        with transaction(deps) as cur:
            review=checked_preview(cur,user,company_id,source_id,data.targetSupplierId)
            if not review['canCompleteInn'] or review['reviewVersion']!=data.expectedReview:
                raise HTTPException(409,'Реквизиты изменились или ИНН уже заполнен. Повторите проверку')
            cur.execute('SELECT 1 FROM company_supplier_links WHERE supplier_id=%s AND company_id<>%s LIMIT 1',
                        (data.targetSupplierId,company_id))
            if cur.fetchone():
                raise HTTPException(409,'Кабинет используется другими организациями. Уточните общий профиль отдельно')
            normalized_inn = canonical_legal(review['sourceInn'], (10, 12))
            cur.execute('SELECT 1 FROM suppliers WHERE '+legal_sql('inn', (10, 12))+
                        '=%s AND user_id IS NOT NULL AND id<>%s LIMIT 1',
                        (normalized_inn,data.targetSupplierId))
            if cur.fetchone():
                raise HTTPException(409,'С этим ИНН уже есть другой кабинет. Нужна проверка реквизитов')
            # Identity advisory and supplier locks are held by checked_preview.
            # Never change an existing INN, account owner or issued document.
            cur.execute('UPDATE suppliers SET inn=%s WHERE id=%s',(normalized_inn,data.targetSupplierId))
            cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,
                description,owner_scope,company_id) VALUES(%s,%s,%s,'supplier_missing_inn_completed','supplier',%s,%s,'company',%s)''',
                (user['id'],user.get('name',''),user['role'],data.targetSupplierId,
                 json.dumps(dict(sourceSupplierId=source_id,inn=normalized_inn,reason=data.reason),ensure_ascii=False),company_id))
            return dict(ok=True,sourceId=source_id,targetId=data.targetSupplierId,inn=normalized_inn)

    @app.post('/system/companies/{company_id}/participants/{source_id}/duplicate-merge')
    def merge(data:Confirmation,company_id:int=Path(...,ge=1),source_id:int=Path(...,ge=1),user:dict=Depends(admin)):
        if not data.confirmed:
            raise HTTPException(422,'Подтвердите принадлежность карточек одному поставщику')
        with transaction(deps) as cur:
            review=checked_preview(cur,user,company_id,source_id,data.targetSupplierId)
            if review['hasSupplierAccount']:
                raise HTTPException(409,'У основной карточки есть кабинет. Используйте проверку доступа к старой истории.')
            if review['reviewVersion']!=data.expectedReview:
                raise HTTPException(409,'Карточки или документы изменились. Проверьте последствия ещё раз')
            # Both cards remain unowned. Only the selected company's link is grouped.
            cur.execute('SELECT id,profile FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s',
                        (company_id,source_id))
            link=cur.fetchone()
            cur.execute('SELECT id FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s',
                        (company_id,data.targetSupplierId))
            target_link=cur.fetchone()
            company_merge.apply_pair(cur,dict(id=data.targetSupplierId,link_id=target_link['id']),
                                     dict(id=source_id,link_id=link['id'],profile=link['profile']))
            cur.execute('''INSERT INTO audit_log(user_id,user_name,user_role,action,entity_type,entity_id,
                description,owner_scope,company_id) VALUES(%s,%s,%s,'supplier_cards_merged','supplier',%s,%s,'company',%s)''',
                (user['id'],user.get('name',''),user['role'],source_id,
                 json.dumps(dict(targetSupplierId=data.targetSupplierId,reviewVersion=data.expectedReview,reason=data.reason),ensure_ascii=False),company_id))
            return dict(ok=True,sourceId=source_id,targetId=data.targetSupplierId)
