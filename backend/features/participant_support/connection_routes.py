from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, StrictBool, conint, field_validator

from . import connections
from .service import admin_transaction

PositiveId = conint(strict=True,ge=1,le=2147483647)


class Confirmation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed: StrictBool

    @field_validator('confirmed')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True: raise ValueError('Подтвердите действие')
        return value

class Proposal(Confirmation):
    requestId: UUID
    targetSupplierId: PositiveId
    expectedSourceVersion: PositiveId


class Decision(Confirmation):
    expectedVersion: PositiveId


class ConnectionResult(BaseModel):
    id: UUID
    companyId: int
    targetSupplierId: int
    status: Literal['pending','accepted','declined','revoked']
    version: int
    expiresAt: datetime


class ConnectionItem(ConnectionResult):
    companyName: Optional[str]
    supplierName: Optional[str]
    inn: Optional[str]
    expired: bool
    correctionStatus: Optional[Literal['disconnected']] = None


class ConnectionPage(BaseModel):
    items: List[ConnectionItem]
    hasMore: bool


def register_connections(app,deps,admin):
    supplier=deps['require_roles']('поставщик')

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests',response_model=ConnectionResult)
    def propose(data: Proposal,company_id: int=Path(...,ge=1,le=2147483647),
                supplier_id: int=Path(...,ge=1,le=2147483647),user: dict=Depends(admin)):
        return connections.propose(deps,user,company_id,supplier_id,data)

    @app.get('/system/companies/{company_id}/participants/{supplier_id}/connection-requests',response_model=ConnectionPage)
    def requests(company_id: int=Path(...,ge=1,le=2147483647),supplier_id: int=Path(...,ge=1,le=2147483647),
                 user: dict=Depends(admin),offset: int=Query(0,ge=0),limit: int=Query(25,ge=1,le=100)):
        with admin_transaction(deps,user,company_id) as (cur,company):
            connections.connection_ready(cur)
            cur.execute('SELECT 1 FROM company_supplier_links WHERE company_id=%s AND platform_account_id=%s AND supplier_id=%s',
                        (company_id,company['platform_account_id'],supplier_id))
            if not cur.fetchone():raise HTTPException(404,'Карточка недоступна в выбранной организации')
            cur.execute('''SELECT r.*,c.name AS company_name,s.name AS supplier_name,s.inn,r.expires_at<=NOW() AS expired
                FROM supplier_buyer_connection_requests r JOIN companies c ON c.id=r.company_id
                JOIN suppliers s ON s.id=r.target_supplier_id
                WHERE r.company_id=%s AND r.platform_account_id=%s AND r.source_supplier_id=%s
                ORDER BY r.created_at DESC,r.id LIMIT %s OFFSET %s''',(company_id,company['platform_account_id'],supplier_id,limit+1,offset))
            result=page(cur.fetchall(),limit)
            if result['items']:
                cur.execute("SELECT to_regclass('public.supplier_connection_correction_plans') AS relation")
                if cur.fetchone()['relation']:
                    cur.execute('''SELECT p.connection_request_id FROM supplier_connection_correction_plans p
                        JOIN company_supplier_links l ON l.id=p.target_link_id AND l.company_id=p.company_id AND l.platform_account_id=p.platform_account_id
                        WHERE p.company_id=%s AND p.platform_account_id=%s AND p.connection_request_id=ANY(%s::uuid[])
                          AND p.applied_at IS NOT NULL AND l.status='Неактивный' ''',
                        (company_id,company['platform_account_id'],[r['id'] for r in result['items']]))
                    corrected={str(r['connection_request_id']) for r in cur.fetchall()}
                    for item in result['items']:
                        if item['id'] in corrected:item['correctionStatus']='disconnected'
            return result

    @app.post('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/revoke',response_model=ConnectionResult)
    def revoke(request_id: UUID,data: Decision,company_id: int=Path(...,ge=1,le=2147483647),
               supplier_id: int=Path(...,ge=1,le=2147483647),user: dict=Depends(admin)):
        return connections.decision(deps,user,request_id,data,'revoke',company_id=company_id,source_id=supplier_id)

    @app.get('/supplier/connection-requests',response_model=ConnectionPage)
    def inbox(user: dict=Depends(supplier),offset: int=Query(0,ge=0),limit: int=Query(25,ge=1,le=100)):
        with connections.transaction(deps) as cur:
            cur.execute('''SELECT r.*,c.name AS company_name,s.name AS supplier_name,s.inn,FALSE AS expired
                FROM supplier_buyer_connection_requests r
                JOIN suppliers s ON s.id=r.target_supplier_id AND s.user_id=r.owner_user_id
                    AND s.participant_owner_epoch=r.target_owner_epoch
                JOIN companies c ON c.id=r.company_id AND c.platform_account_id=r.platform_account_id AND c.active
                JOIN users u ON u.id=r.owner_user_id AND u.role='поставщик' AND COALESCE(u.active,TRUE)
                    AND u.supplier_team_epoch=r.owner_epoch
                JOIN users issuer ON issuer.id=r.created_by_user_id AND issuer.role=ANY(%s)
                    AND COALESCE(issuer.active,TRUE) AND issuer.supplier_team_epoch=r.issuer_epoch
                WHERE r.owner_user_id=%s AND r.status='pending' AND r.expires_at>NOW()
                ORDER BY r.created_at DESC,r.id LIMIT %s OFFSET %s''',
                (list(connections.ADMIN_ROLES),user['id'],limit+1,offset))
            return page(cur.fetchall(),limit)

    @app.post('/supplier/connection-requests/{request_id}/accept',response_model=ConnectionResult)
    def accept(request_id: UUID,data: Decision,user: dict=Depends(supplier)):
        return connections.decision(deps,user,request_id,data,'accept')

    @app.post('/supplier/connection-requests/{request_id}/decline',response_model=ConnectionResult)
    def decline(request_id: UUID,data: Decision,user: dict=Depends(supplier)):
        return connections.decision(deps,user,request_id,data,'decline')


def page(rows,limit):
    return dict(items=[dict(connections.view(r),companyName=r['company_name'],supplierName=r['supplier_name'],
                            inn=r['inn'],expired=r['expired']) for r in rows[:limit]],hasMore=len(rows)>limit)
