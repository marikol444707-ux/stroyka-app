"""Read-only facts about explicit company memberships and invitation purposes.

These projections are not authorization decisions and expose no bearer codes,
contacts, assignment names or other organizations' memberships.
"""
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel

from ..company_users.access import COMPANY_ROLES
from .service import admin_transaction


class MembershipItem(BaseModel):
    membershipId: int
    userId: int
    name: Optional[str]
    role: str
    status: Literal['active', 'inactive', 'disabled', 'review']
    activeRoleCount: int


class MembershipPage(BaseModel):
    items: List[MembershipItem]
    hasMore: bool


class InvitationItem(BaseModel):
    inviteId: int
    purpose: Literal['company_membership', 'supplier_registration']
    role: str
    status: Literal['pending', 'used', 'expired', 'review']
    createdAt: Optional[datetime]
    expiresAt: Optional[datetime]


class InvitationPage(BaseModel):
    items: List[InvitationItem]
    hasMore: bool


def validate_status(status, allowed):
    if status and status not in allowed:
        raise HTTPException(422, 'Некорректное состояние')


def register_organization_directory(app, deps, admin):
    @app.get('/system/companies/{company_id}/participant-memberships', response_model=MembershipPage)
    def memberships(company_id: int, user: dict = Depends(admin),
                    search: str = Query('', max_length=100), status: str = Query(''),
                    offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
        validate_status(status, ('active', 'inactive', 'disabled', 'review'))
        with admin_transaction(deps, user, company_id) as (cur, company):
            # NULL account is the existing company-user writer's representation;
            # the verified explicit company link supplies its account. A contradictory account
            # is never silently normalized. No users.company_id legacy fallback.
            cur.execute('''WITH scoped AS (
                SELECT m.id,m.user_id,u.name,m.role,m.active,u.active AS user_active,
                    u.role AS global_role,c.active AS company_active,
                    count(*) FILTER (WHERE COALESCE(m.active,TRUE) AND m.role=ANY(%s))
                        OVER (PARTITION BY m.user_id) AS active_roles
                FROM user_company_roles m JOIN users u ON u.id=m.user_id
                JOIN companies c ON c.id=m.company_id
                WHERE m.company_id=%s AND (m.platform_account_id IS NULL OR m.platform_account_id=%s)
            ), classified AS (
                SELECT *, CASE WHEN NOT COALESCE(active,TRUE) THEN 'inactive'
                    WHEN NOT COALESCE(user_active,TRUE) OR NOT COALESCE(company_active,TRUE) THEN 'disabled'
                    WHEN role<>ALL(%s) OR global_role IS NULL OR global_role<>ALL(%s)
                        OR active_roles>1 THEN 'review' ELSE 'active' END AS state FROM scoped
            ) SELECT id AS "membershipId",user_id AS "userId",name,role,state AS status,
                active_roles AS "activeRoleCount" FROM classified
            WHERE (name ILIKE %s OR role ILIKE %s) AND (%s='' OR state=%s)
            ORDER BY name NULLS LAST,id LIMIT %s OFFSET %s''',
                (list(COMPANY_ROLES), company_id, company['platform_account_id'],
                 list(COMPANY_ROLES), list(COMPANY_ROLES), '%'+search+'%', '%'+search+'%',
                 status, status, limit+1, offset))
            rows = cur.fetchall()
            return dict(items=rows[:limit], hasMore=len(rows)>limit)

    @app.get('/system/companies/{company_id}/participant-invitations', response_model=InvitationPage)
    def invitations(company_id: int, user: dict = Depends(admin), status: str = Query(''),
                    offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
        validate_status(status, ('pending', 'used', 'expired', 'review'))
        with admin_transaction(deps, user, company_id) as (cur, company):
            cur.execute("SELECT to_regclass('public.supplier_team_invites') AS relation")
            team_filter = ('AND NOT EXISTS(SELECT 1 FROM supplier_team_invites t WHERE t.invite_id=i.id)'
                           if cur.fetchone()['relation'] else '')
            cur.execute('''WITH scoped AS (
                SELECT i.id,i.role,i.created_at,i.expires_at,
                    CASE WHEN b.invite_id IS NULL THEN 'company_membership'
                        ELSE 'supplier_registration' END AS purpose,
                    CASE WHEN i.used IS TRUE THEN 'used'
                        WHEN i.used IS NULL OR i.expires_at IS NULL THEN 'review'
                        WHEN i.expires_at<=LOCALTIMESTAMP THEN 'expired' ELSE 'pending' END AS state
                FROM invite_codes i LEFT JOIN supplier_invite_companies b ON b.invite_id=i.id
                WHERE (i.platform_account_id IS NULL OR i.platform_account_id=%s)
                AND ((b.invite_id IS NULL AND i.company_id=%s AND i.role=ANY(%s))
                    OR (b.company_id=%s AND b.platform_account_id=%s AND i.role='поставщик'
                        AND (i.company_id IS NULL OR i.company_id=%s)))
                '''+team_filter+'''
            ) SELECT id AS "inviteId",purpose,role,state AS status,
                created_at AS "createdAt",expires_at AS "expiresAt" FROM scoped
            WHERE (%s='' OR state=%s) ORDER BY id DESC LIMIT %s OFFSET %s''',
                (company['platform_account_id'], company_id, list(COMPANY_ROLES),
                 company_id, company['platform_account_id'], company_id, status, status, limit+1, offset))
            rows = cur.fetchall()
            return dict(items=rows[:limit], hasMore=len(rows)>limit)
