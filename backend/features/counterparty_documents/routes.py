"""Read-only archive projection. Originals remain in their source records."""
from typing import Literal, Optional

from fastapi import Depends, Header, HTTPException, Query


# Administrative archive only. Other cabinets retain their narrower existing APIs.
ROLES = {'директор', 'зам_директора'}
SOURCES = {
    'company': ('company_documents', 'name', 'file_url', 'doc_type', 'TRUE'),
    'supplier': ('supplier_documents', 'title', 'file_url', 'doc_type', 'archived_at IS NULL'),
}


def register_counterparty_document_archive(app, deps):
    @app.get('/company-document-archive')
    def list_archive(
        section: Literal['all', 'company', 'supplier'] = 'all',
        q: str = Query('', max_length=200),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
    ):
        conn = deps['get_db']()
        cur = conn.cursor()
        try:
            context = deps['resolve_work_company_context'](
                cur, current_user, None, 'read',
                x_company_id=x_company_id, x_company_mode=x_company_mode)
            if context.get('mode') != 'company':
                return {'items': [], 'requiresCompanySelection': True, 'hasMore': False}
            actors = deps['effective_company_actors'](current_user, context)
            if len(actors) != 1 or actors[0].get('role') not in ROLES:
                raise HTTPException(403, 'Общий архив доступен руководству выбранной компании')
            company_id = actors[0].get('companyId')
            if not company_id or company_id != context.get('companyId'):
                raise HTTPException(403, 'Компания архива не определена')
            queries, params = [], []
            for key, (table, title, url, kind, active) in SOURCES.items():
                if section not in ('all', key):
                    continue
                queries.append(f"""SELECT '{key}' AS source,d.id,d.company_id,
                    COALESCE(d.{title},'') AS title,COALESCE(d.{kind},'') AS kind,
                    d.created_at, COALESCE(d.{url},'') AS original_url,
                    f.id AS file_id
                    FROM {table} d LEFT JOIN file_ownership f
                      ON d.{url}='/tenant-files/' || f.id || '/content'
                     AND f.company_id=d.company_id AND f.project_id IS NULL
                     AND COALESCE(f.deletion_status,'active')='active'
                    WHERE d.company_id=%s AND {active}
                      AND (POSITION(LOWER(%s) IN LOWER(COALESCE(d.{title},'')))>0
                           OR POSITION(LOWER(%s) IN LOWER(COALESCE(d.{kind},'')))>0)""")
                params.extend((company_id, q.strip(), q.strip()))
            cur.execute('SELECT * FROM (' + ' UNION ALL '.join(queries) +
                        ') archive ORDER BY created_at DESC NULLS LAST,source,id DESC LIMIT %s OFFSET %s',
                        (*params, limit + 1, offset))
            rows = cur.fetchall()
            items = []
            for source, source_id, owner, title, kind, created, original_url, file_id in rows[:limit]:
                items.append({'id': f'{source}:{source_id}', 'source': source, 'sourceId': source_id,
                              'companyId': owner, 'title': title, 'documentType': kind,
                              'createdAt': str(created) if created else None,
                              'fileUrl': f'/tenant-files/{file_id}/content' if file_id else None,
                              'fileStatus': 'available' if file_id else 'needs_review' if original_url else 'not_attached'})
            return {'items': items, 'companyId': company_id, 'requiresCompanySelection': False,
                    'hasMore': len(rows) > limit, 'nextOffset': offset + limit if len(rows) > limit else None}
        finally:
            cur.close()
            conn.close()
