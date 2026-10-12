"""Diagnosis only: legal-key matching is never proof of cabinet ownership.

No account, invitation or relationship is written. Existing document visibility
uses the same server policies as the supplier portal; proposed historical access
is deliberately not predicted from a count of buyer-owned records.
"""
from typing import List, Literal, Optional

from fastapi import Depends, HTTPException, Path
from pydantic import BaseModel

from ..supplier_access.company_merge import check_company_documents
from ..supplier_access.service import supplier_invoice_visibility_filter, supplier_offer_visibility_filter
from ..supplier_team.policy import access_ids, enabled as team_enabled
from .service import admin_transaction


class Card(BaseModel):
    supplierId: int
    name: Optional[str]
    inn: Optional[str]
    ogrn: Optional[str]
    relationshipVersion: Optional[int]


class Cabinet(Card):
    hasBuyerRelationship: bool
    accountState: Literal['active', 'disabled', 'wrong_role', 'missing']
    ownerUserId: Optional[int]


class History(BaseModel):
    invoices: int
    receipts: int
    offers: int


class Visibility(BaseModel):
    invoices: int
    offers: int


class Blocker(BaseModel):
    code: str
    message: str


class ConnectionPreview(BaseModel):
    companyId: int
    platformAccountId: int
    supplier: Card
    cabinet: Optional[Cabinet]
    scenario: Literal['already_connected', 'connect_existing', 'merge_cards', 'no_cabinet', 'ambiguous', 'review']
    history: History
    currentVisibility: Optional[Visibility]
    blockers: List[Blocker]
    canApply: Literal[False]


def card(row):
    return dict(supplierId=row['id'], name=row['name'], inn=row['inn'], ogrn=row['ogrn'],
                relationshipVersion=row.get('link_version'))


def legal_key(value, lengths):
    value = str(value or '').strip()
    return value if value.isascii() and value.isdecimal() and len(value) in lengths else ''


def diagnose(cur, company, supplier_id):
    # Start from an explicit relationship, never a user-supplied global supplier.
    cur.execute('''SELECT s.id,s.name,s.inn,s.ogrn,s.user_id,s.status AS supplier_status,
        l.status AS relationship_status,l.version AS link_version,l.profile
        FROM company_supplier_links l JOIN suppliers s ON s.id=l.supplier_id
        WHERE l.company_id=%s AND l.platform_account_id=%s AND s.id=%s''',
        (company['id'],company['platform_account_id'],supplier_id))
    source=cur.fetchone()
    if not source:
        raise HTTPException(404,'Поставщик недоступен в выбранной организации')
    blockers=[]
    def block(code, message):
        blockers.append(dict(code=code,message=message))
    if source['relationship_status']!='Активный' or source['supplier_status'] not in (None,'','Активный'):
        block('NEW_OPERATIONS_PAUSED','Поставщик или отношение с этой компанией неактивны. Возможность новых закупок нужно проверить отдельно от доступа к архиву.')
    history={}
    for key,table in (('invoices','supplier_invoices'),('receipts','warehouse_invoices'),('offers','supplier_offers')):
        # Table names are fixed application constants. All request values are parameters.
        cur.execute('SELECT count(*) AS count FROM '+table+' WHERE company_id=%s AND supplier_id=%s',
                    (company['id'],supplier_id))
        history[key]=cur.fetchone()['count']
    target=None
    scenario='no_cabinet'
    if (source['profile'] or {}).get('mergedIntoSupplierId'):
        block('SOURCE_CARD_MERGED','Карточка уже объединена. Откройте основную карточку в каталоге компании.')
        scenario='review'
    elif source['user_id']:
        target=source
        scenario='already_connected'
    else:
        inn,ogrn=legal_key(source['inn'],(10,12)),legal_key(source['ogrn'],(13,15))
        if not inn and not ogrn:
            block('LEGAL_IDENTITY_REQUIRED','Уточните ИНН или ОГРН в карточке. Название и контакты не подтверждают принадлежность.')
            scenario='review'
        else:
            # Existing public legal identities only. No contacts, foreign links,
            # documents or buyer names are returned by this candidate lookup.
            cur.execute('''SELECT s.id,s.name,s.inn,s.ogrn,s.user_id,l.version AS link_version,l.profile
                FROM suppliers s LEFT JOIN company_supplier_links l ON l.supplier_id=s.id
                    AND l.company_id=%s AND l.platform_account_id=%s
                WHERE s.id<>%s AND s.user_id IS NOT NULL
                    AND ((%s<>'' AND s.inn=%s) OR (%s<>'' AND s.ogrn=%s))
                ORDER BY s.id LIMIT 2''',
                (company['id'],company['platform_account_id'],supplier_id,inn,inn,ogrn,ogrn))
            matches=cur.fetchall()
            if len(matches)>1:
                block('MULTIPLE_CABINETS','С этими реквизитами найдено несколько кабинетов. Сначала установите, какой из них принадлежит поставщику.')
                scenario='ambiguous'
            elif matches:
                target=matches[0]
                scenario='merge_cards' if target['link_version'] is not None else 'connect_existing'
                for key in ('inn','ogrn'):
                    if source[key] and target[key] and str(source[key]).strip()!=str(target[key]).strip():
                        block('LEGAL_IDENTITY_CONFLICT','ИНН или ОГРН карточек различаются. Объединять разные юрлица нельзя.')
                        break
                if scenario=='merge_cards':
                    block('HISTORICAL_ACCESS_REVIEW_REQUIRED','Кабинет уже есть у этого покупателя. Объединение старой карточки и доступ к её документам проверяются отдельно.')
                else:
                    block('OWNER_VERIFICATION_REQUIRED','Нужно подтвердить принадлежность существующего кабинета. Совпадение реквизитов не выдаёт доступ.')
            else:
                block('NO_EXISTING_CABINET','По точным реквизитам кабинет не найден. Это не подтверждает, что других кабинетов нет.')
        cur.execute('''SELECT 1 FROM company_supplier_links WHERE supplier_id=%s
            AND (company_id<>%s OR platform_account_id IS DISTINCT FROM %s) LIMIT 1''',
            (supplier_id,company['id'],company['platform_account_id']))
        if cur.fetchone():
            block('SHARED_SOURCE_CARD','Карточка используется вне выбранной организации. Перепривязка пользователя может раскрыть чужую историю.')
        cur.execute('SELECT 1 FROM supplier_team_members WHERE supplier_id=%s LIMIT 1',(supplier_id,))
        if cur.fetchone():
            block('SOURCE_TEAM_EXISTS','У карточки есть команда. Проверьте действующие членства перед изменением связи.')
            if scenario=='no_cabinet':
                scenario='review'
        try:
            check_company_documents(cur,supplier_id,company['id'])
        except HTTPException as error:
            if error.status_code!=409:
                raise
            block('DOCUMENT_OWNER_REVIEW','Есть документы с другой или неизвестной компанией-владельцем. Их содержимое здесь не раскрывается.')
        if any(history.values()):
            block('HISTORY_REVIEW_REQUIRED','До выдачи доступа нужно проверить адресатов документов выбранной организации.')
    cabinet=None
    visibility=None
    if target:
        if (target.get('profile') or {}).get('mergedIntoSupplierId') and target['id']!=supplier_id:
            block('TARGET_CARD_MERGED','Найденная карточка уже объединена в этой компании. Сначала проверьте основную карточку.')
        cur.execute('SELECT id,active,role FROM users WHERE id=%s',(target['user_id'],))
        owner=cur.fetchone()
        state=('missing' if not owner else 'disabled' if owner['active'] is False else
               'wrong_role' if owner['role']!='поставщик' else 'active')
        cabinet=dict(card(target),hasBuyerRelationship=target.get('link_version') is not None,
                     accountState=state,ownerUserId=target['user_id'])
        if state!='active':
            block('CABINET_ACCOUNT_DISABLED','Пользователь кабинета отключён, отсутствует или имеет другую роль. Подключение нельзя считать действующим.')
        elif target['id']==supplier_id:
            # Visibility may depend on another explicitly owned card in the same
            # recipient group. Resolve the actor's real IDs, then constrain every
            # count to this supplier AND this buyer. Never return those other IDs.
            if team_enabled():
                actor_ids=access_ids(cur,owner)
            else:
                cur.execute('SELECT id FROM suppliers WHERE user_id=%s ORDER BY id',(owner['id'],))
                actor_ids=[row['id'] for row in cur.fetchall()]
            visibility={}
            for key,table,alias,policy in (
                ('invoices','supplier_invoices','si',supplier_invoice_visibility_filter),
                ('offers','supplier_offers','supplier_offers',supplier_offer_visibility_filter),
            ):
                scope,params=policy(actor_ids,owner['id'])
                cur.execute('SELECT count(*) AS count FROM '+table+' '+alias+
                            ' WHERE '+alias+'.company_id=%s AND '+alias+'.supplier_id=%s'+scope,
                            [company['id'],supplier_id]+params)
                visibility[key]=cur.fetchone()['count']
    return dict(companyId=company['id'],platformAccountId=company['platform_account_id'],
                supplier=card(source),cabinet=cabinet,scenario=scenario,history=history,
                currentVisibility=visibility,blockers=blockers,canApply=False)


def register_connection_preview(app, deps, admin):
    @app.get('/system/companies/{company_id}/participants/{supplier_id}/connection-preview',
             response_model=ConnectionPreview)
    def connection_preview(company_id: int=Path(...,ge=1,le=2147483647), supplier_id: int=Path(...,ge=1,le=2147483647),
                           user: dict=Depends(admin)):
        with admin_transaction(deps,user,company_id,snapshot=True) as (cur,company):
            return diagnose(cur,company,supplier_id)
