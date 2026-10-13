"""Review one accepted buyer connection. This is not an undo or an apply plan.

The read-only snapshot keeps counts, pages and owner checks consistent. An
inactive catalog link does not revoke addressed document access; report that
explicitly rather than projecting a false access revocation.
"""
import os
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Query
from psycopg2 import sql
from pydantic import BaseModel

from .history_preview import Category, TABLES, inventory, live_access
from .service import ADMIN_ROLES, admin_transaction

REGISTRIES = dict(TABLES, contracts='supplier_contract_versions', files='file_ownership')


class HistoryCount(BaseModel):
    total: Optional[int]
    afterConnection: Optional[int]
    undated: Optional[int]


class CorrectionItem(BaseModel):
    id: int
    createdAfterConnection: Optional[bool]
    currentSupplierAccess: Literal['available', 'unavailable', 'needs_check']


class CorrectionPreview(BaseModel):
    companyId: int
    companyName: str
    platformAccountId: int
    requestId: UUID
    connectedAt: datetime
    sourceId: int
    targetId: int
    sourceName: Optional[str]
    targetName: Optional[str]
    sourceVersion: int
    targetVersion: int
    requestVersion: int
    summary: dict[str, HistoryCount]
    category: Category
    items: list[CorrectionItem]
    hasMore: bool
    blockers: list[dict[str, str]]
    canApply: Literal[False]
    addressedAccessRequiresSeparateCorrection: Literal[True]


def creation_time(cur, table):
    cur.execute('''SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name='created_at' ''', (table,))
    row = cur.fetchone()
    if row and row['data_type'] == 'timestamp with time zone':
        return sql.SQL('t.created_at')
    if row and row['data_type'] == 'timestamp without time zone':
        # Legacy application timestamps are UTC, including on a non-UTC DB.
        return sql.SQL("t.created_at AT TIME ZONE 'UTC'")
    return sql.SQL('NULL::timestamptz')


def document_queries(cur, company, source, target):
    # Reuse the existing company-owned original references. A shared file/version
    # occurs once even when both cards refer to it. No original URLs leave here.
    first, _, unresolved_source = inventory(cur, company, source)
    second, _, unresolved_target = inventory(cur, company, target)
    queries = {}
    for kind in first.keys() & second.keys():
        left, left_params = first[kind]
        right, right_params = second[kind]
        query = sql.SQL('''SELECT t.id, {created} AS created_at FROM {table} t
            JOIN (({left}) UNION ({right})) owned ON owned.id=t.id''').format(
                created=creation_time(cur, REGISTRIES[kind]), table=sql.Identifier(REGISTRIES[kind]),
                left=sql.SQL(left), right=sql.SQL(right))
        queries[kind] = (query, left_params+right_params)
    return queries, unresolved_source+unresolved_target


def review(cur, company, source_id, request_id, category, offset, limit, actor_id):
    cur.execute('SELECT role,active FROM users WHERE id=%s', (actor_id,))
    actor = cur.fetchone()
    if not actor or actor['active'] is False or actor['role'] not in ADMIN_ROLES:
        raise HTTPException(403, 'Полномочия администратора изменились')
    cur.execute('''SELECT r.*, c.name AS company_name,
        s.name AS source_name, t.name AS target_name, t.user_id AS current_owner,
        t.participant_owner_epoch AS current_owner_epoch,
        sl.version AS source_link_version, tl.version AS target_link_version,
        sl.profile AS source_profile, tl.profile AS target_profile,
        u.active AS owner_active, u.role AS owner_role, u.supplier_team_epoch AS current_team_epoch
        FROM supplier_buyer_connection_requests r
        JOIN companies c ON c.id=r.company_id AND c.platform_account_id=r.platform_account_id
        JOIN company_supplier_links sl ON sl.company_id=r.company_id AND sl.platform_account_id=r.platform_account_id AND sl.supplier_id=r.source_supplier_id
        LEFT JOIN company_supplier_links tl ON tl.company_id=r.company_id AND tl.platform_account_id=r.platform_account_id AND tl.supplier_id=r.target_supplier_id
        JOIN suppliers s ON s.id=r.source_supplier_id JOIN suppliers t ON t.id=r.target_supplier_id
        LEFT JOIN users u ON u.id=t.user_id
        WHERE r.id=%s AND r.company_id=%s AND r.platform_account_id=%s AND r.source_supplier_id=%s''',
        (str(request_id), company['id'], company['platform_account_id'], source_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, 'Подключение недоступно в выбранной организации')
    if row['status'] != 'accepted':
        raise HTTPException(409, 'Проверка исправления доступна только для выполненного подключения')
    if row['target_link_version'] is None:
        raise HTTPException(409, 'Связь кабинета уже изменена. Нужна отдельная проверка истории')
    blockers = []
    owner_changed = (row['current_owner'] != row['owner_user_id'] or
                     row['current_owner_epoch'] != row['target_owner_epoch'])
    if owner_changed:
        blockers.append(dict(code='CABINET_OWNER_CHANGED', message='После подключения изменился владелец кабинета. Нужна отдельная проверка принадлежности.'))
    if row['owner_active'] is False or row['owner_role'] != 'поставщик' or row['current_team_epoch'] != row['owner_epoch']:
        blockers.append(dict(code='CABINET_PERMISSIONS_CHANGED', message='После подключения изменились полномочия пользователя кабинета.'))
    if any((row[key] or {}).get('mergedIntoSupplierId') for key in ('source_profile', 'target_profile')):
        blockers.append(dict(code='MERGE_REQUIRES_SEPARATE_CORRECTION', message='Карточки уже объединялись. Исправление подключения не отменяет объединение истории.'))
    for table in TABLES.values():
        cur.execute(sql.SQL('SELECT 1 FROM {} WHERE supplier_id=ANY(%s) AND company_id IS NULL LIMIT 1').format(sql.Identifier(table)),
                    ([source_id, row['target_supplier_id']],))
        if cur.fetchone():
            blockers.append(dict(code='UNASSIGNED_DOCUMENTS', message='У карточки есть записи без подтверждённой компании. Их принадлежность нужно выяснить отдельно.'))
            break
    queries, unresolved = document_queries(cur, company['id'], source_id, row['target_supplier_id'])
    summary = {kind:dict(total=None, afterConnection=None, undated=None) for kind in REGISTRIES}
    for kind, (query, params) in queries.items():
        cur.execute(sql.SQL('''SELECT count(*) AS total,
            count(*) FILTER (WHERE created_at >= %s) AS after,
            count(*) FILTER (WHERE created_at IS NULL) AS undated FROM ({query}) docs''').format(query=query),
            [row['decided_at']]+params)
        counts = cur.fetchone()
        summary[kind] = dict(total=counts['total'], afterConnection=counts['after'], undated=counts['undated'])
    if any(value['total'] is None for value in summary.values()):
        blockers.append(dict(code='HISTORY_SCHEMA_REVIEW_REQUIRED', message='Часть реестров документов недоступна. Это не означает, что документов нет.'))
    if unresolved:
        blockers.append(dict(code='FILE_REFERENCE_REVIEW_REQUIRED', message='Для части основных файлов не подтверждена принадлежность этой компании.'))
    if any(value['undated'] for value in summary.values()):
        blockers.append(dict(code='UNDATED_DOCUMENTS', message='У части записей нет надёжной даты создания. Нельзя определить, появились ли они после подключения.'))
    if category not in queries:
        raise HTTPException(503, 'Для этого вида документов требуется обновление схемы')
    query, params = queries[category]
    cur.execute(sql.SQL('SELECT id,created_at >= %s AS after FROM ({query}) docs ORDER BY id LIMIT %s OFFSET %s').format(query=query),
                [row['decided_at']]+params+[limit+1, offset])
    rows = cur.fetchall()
    access = {}
    if row['current_owner']:
        for sid in (source_id, row['target_supplier_id']):
            access.update(live_access(cur, row['current_owner'], company['id'], sid, category, [r['id'] for r in rows[:limit]]))
    return dict(companyId=company['id'], companyName=row['company_name'], platformAccountId=company['platform_account_id'],
        requestId=str(row['id']), connectedAt=row['decided_at'], sourceId=source_id, targetId=row['target_supplier_id'],
        sourceName=row['source_name'], targetName=row['target_name'], sourceVersion=row['source_link_version'],
        targetVersion=row['target_link_version'], requestVersion=row['version'], summary=summary, category=category,
        items=[dict(id=r['id'], createdAfterConnection=r['after'], currentSupplierAccess=access.get(r['id'], 'unavailable')) for r in rows[:limit]],
        hasMore=len(rows)>limit, blockers=blockers, canApply=False, addressedAccessRequiresSeparateCorrection=True)


def register_correction_preview(app, deps, admin):
    @app.get('/system/companies/{company_id}/participants/{supplier_id}/connection-requests/{request_id}/correction-preview', response_model=CorrectionPreview)
    def preview(request_id: UUID, company_id: int=Path(...,ge=1,le=2147483647),
                supplier_id: int=Path(...,ge=1,le=2147483647), category: Category=Query('invoices'),
                offset: int=Query(0,ge=0), limit: int=Query(5,ge=1,le=100), user: dict=Depends(admin)):
        with admin_transaction(deps, user, company_id, snapshot=True) as (cur, company):
            if os.getenv('PARTICIPANT_CORRECTION_PREVIEW_ENABLED', '0') != '1':
                raise HTTPException(503, 'Проверка исправления подключения пока не включена')
            cur.execute("SELECT to_regclass('public.supplier_buyer_connection_requests') AS relation")
            if not cur.fetchone()['relation']:
                raise HTTPException(503, 'Проверка исправления требует обновления схемы')
            return review(cur, company, supplier_id, request_id, category, offset, limit, user['id'])
