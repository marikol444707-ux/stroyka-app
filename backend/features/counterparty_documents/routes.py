"""Read-only archive projection. Originals remain in their source records."""
import json
from typing import Literal, Optional

from .procurement_inventory import attachments

from fastapi import Depends, Header, HTTPException, Query


# Administrative archive only. Other cabinets retain their narrower existing APIs.
ROLES = {'директор', 'зам_директора'}
# Section, table, title SQL, type SQL, date SQL, active predicate, file columns.
SOURCES = {
    'company': ('company', 'company_documents', "COALESCE(d.name,'')", "COALESCE(d.doc_type,'')", 'd.created_at', 'TRUE', ('file_url',)),
    'supplier': ('supplier', 'supplier_documents', "COALESCE(d.title,'')", "COALESCE(d.doc_type,'')", 'd.created_at', 'd.archived_at IS NULL', ('file_url',)),
    'offer': ('supplier', 'supplier_offers', "'КП №' || d.id", "'КП'", 'd.requested_at', 'TRUE', ('pdf_url',)),
    'invoice': ('supplier', 'supplier_invoices', "'Счёт №' || COALESCE(NULLIF(d.invoice_number,''),d.id::text)", "'Счёт'", 'd.created_at', 'TRUE', ('file_url','photo_url')),
    'delivery': ('supplier', 'supply_deliveries', "'Отгрузка №' || COALESCE(NULLIF(d.waybill_number,''),d.id::text)", "'Отгрузка'", 'd.created_at', 'TRUE', ('document_url','photo_url')),
    'warehouse': ('supplier', 'warehouse_invoices', "'Накладная №' || COALESCE(NULLIF(d.number,''),d.id::text)", "'Накладная'", 'd.created_at', 'TRUE', ('photo_url','photo_urls')),
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
            for key, (group, table, title, kind, date, active, file_fields) in SOURCES.items():
                if section not in ('all', group):
                    continue
                fields = ','.join(f"'{field}',to_jsonb(d)->'{field}'" for field in file_fields)
                queries.append(f"""SELECT '{key}' AS source,d.id,d.company_id,
                    {title} AS title,{kind} AS kind,{date} AS created_at,
                    jsonb_build_object({fields}) AS files
                    FROM {table} d
                    WHERE d.company_id=%s AND {active}
                      AND (POSITION(LOWER(%s) IN LOWER({title}))>0
                           OR POSITION(LOWER(%s) IN LOWER({kind}))>0)""")
                params.extend((company_id, q.strip(), q.strip()))
            cur.execute('SELECT * FROM (' + ' UNION ALL '.join(queries) +
                        ') archive ORDER BY created_at DESC NULLS LAST,source,id DESC LIMIT %s OFFSET %s',
                        (*params, limit + 1, offset))
            rows = cur.fetchall()
            page_rows = rows[:limit]
            references = []
            parsed = []
            for row in page_rows:
                payload = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                urls, malformed = attachments(payload or {}, SOURCES[row[0]][6])
                parsed.append((row, urls, malformed))
                references.extend(urls)
            safe_files = {}
            if references:
                cur.execute("""SELECT id FROM file_ownership
                    WHERE company_id=%s AND project_id IS NULL
                      AND COALESCE(deletion_status,'active')='active'
                      AND '/tenant-files/' || id || '/content'=ANY(%s)""",
                            (company_id, list(set(references))))
                safe_files = {f'/tenant-files/{r[0]}/content': r[0] for r in cur.fetchall()}
            items = []
            for row, urls, malformed in parsed:
                source, source_id, owner, title, kind, created, _ = row
                files = [{'fileId': safe_files[url], 'fileUrl': url} for url in urls if url in safe_files]
                unresolved = malformed + sum(url not in safe_files for url in urls)
                items.append({'id': f'{source}:{source_id}', 'source': source, 'sourceId': source_id,
                              'companyId': owner, 'title': title, 'documentType': kind,
                              'createdAt': str(created) if created else None,
                              'attachments': files, 'unavailableAttachments': unresolved,
                              'fileUrl': files[0]['fileUrl'] if files else None,
                              'fileStatus': 'needs_review' if unresolved else 'available' if files else 'not_attached'})
            return {'items': items, 'companyId': company_id, 'requiresCompanySelection': False,
                    'hasMore': len(rows) > limit, 'nextOffset': offset + limit if len(rows) > limit else None}
        finally:
            cur.close()
            conn.close()
