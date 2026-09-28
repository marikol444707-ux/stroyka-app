"""Read-only archive projection. Originals remain in their source records."""
import json
from typing import Literal, Optional

from .procurement_inventory import attachments
from ..project_access.service import resolve_project_parent, require_project_parent_access

from fastapi import Depends, Header, HTTPException, Query


# Administrative archive only. Other cabinets retain their narrower existing APIs.
ROLES = {'директор', 'зам_директора'}
ArchiveSource = Literal['company','supplier','offer','invoice','delivery','warehouse','contract','customer']
# Section, table, title SQL, type SQL, date SQL, active predicate, file columns.
SOURCES = {
    'company': ('company', 'company_documents', "COALESCE(d.name,'')", "COALESCE(d.doc_type,'')", 'd.created_at', 'TRUE', ('file_url',)),
    'supplier': ('supplier', 'supplier_documents', "COALESCE(d.title,'')", "COALESCE(d.doc_type,'')", 'd.created_at', 'd.archived_at IS NULL', ('file_url',)),
    'offer': ('supplier', 'supplier_offers', "'КП №' || d.id", "'КП'", 'd.requested_at', 'TRUE', ('pdf_url',)),
    'invoice': ('supplier', 'supplier_invoices', "'Счёт №' || COALESCE(NULLIF(d.invoice_number,''),d.id::text)", "'Счёт'", 'd.created_at', 'TRUE', ('file_url','photo_url')),
    'delivery': ('supplier', 'supply_deliveries', "'Отгрузка №' || COALESCE(NULLIF(d.waybill_number,''),d.id::text)", "'Отгрузка'", 'd.created_at', 'TRUE', ('document_url','photo_url')),
    'warehouse': ('supplier', 'warehouse_invoices', "'Накладная №' || COALESCE(NULLIF(d.number,''),d.id::text)", "'Накладная'", 'd.created_at', 'TRUE', ('photo_url','photo_urls')),
    'contract': ('supplier', 'supplier_contract_versions', "'Договор №' || COALESCE(d.snapshot_json->>'number',d.id::text) || ' · версия ' || d.version", "'Договор'", 'd.reviewed_at', 'EXISTS (SELECT 1 FROM supplier_offers o WHERE o.id=d.offer_id AND o.company_id=d.company_id)', ('file_url',)),
    'customer': ('customer', 'project_documents', "COALESCE(d.doc_type,'Документ') || ' №' || COALESCE(NULLIF(d.number,''),d.id::text)", "COALESCE(d.doc_type,'Документ')", 'd.created_at', "d.side='customer' AND EXISTS (SELECT 1 FROM projects p WHERE p.id=d.project_id AND p.company_id=d.company_id)", ('scan_url',)),
}



def register_counterparty_document_archive(app, deps):
    @app.get('/company-document-archive')
    def list_archive(
        section: Literal['all', 'company', 'supplier', 'customer'] = 'all',
        q: str = Query('', max_length=200),
        source: Optional[ArchiveSource] = None,
        category: Optional[ArchiveSource] = None,
        contractId: Optional[int] = Query(None, gt=0, le=2147483647),
        recordId: Optional[int] = Query(None, gt=0, le=2147483647),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Optional[str] = Header(None, alias='X-Company-Id'),
        x_company_mode: Optional[str] = Header(None, alias='X-Company-Mode'),
    ):
        if (source is None) != (recordId is None):
            raise HTTPException(422, 'Укажите документ для перехода')
        if contractId is not None and (source is not None or section not in ('all','supplier')):
            raise HTTPException(422, 'Выберите счета по договору отдельно от других документов')
        if category is not None and (source is not None or contractId is not None
                                     or section not in ('all', SOURCES[category][0])):
            raise HTTPException(422, 'Выберите вид документа в соответствующем разделе архива')
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
                if (category is not None and key != category) or (contractId is not None and key != 'invoice') or section not in ('all', group):
                    continue
                fields = ','.join(f"'{field}',to_jsonb(d)->'{field}'" for field in (*file_fields, 'project_id', 'project_name', 'sign_status'))
                if key == 'contract':
                    fields = "'file_url','/tenant-files/' || d.source_file_id || '/content','offer_id',d.offer_id,'version',d.version"
                    fields += ", 'applicability',d.snapshot_json->'applicability','scope_project_name',(SELECT p.name FROM projects p WHERE p.company_id=d.company_id AND p.id::text=d.snapshot_json #>> '{applicability,projectId}')"
                    fields += """, 'origin_contract_id',(SELECT c.id FROM supplier_contract_versions c
                        WHERE c.id::text=d.snapshot_json #>> '{reusedFrom,contractId}'
                          AND c.company_id=d.company_id AND c.id<>d.id
                          AND c.source_file_id=d.source_file_id
                          AND c.snapshot_hash=d.snapshot_json #>> '{reusedFrom,snapshotHash}'
                          AND c.offer_id::text=d.snapshot_json #>> '{reusedFrom,offerId}'
                          AND c.version::text=d.snapshot_json #>> '{reusedFrom,version}'
                          AND EXISTS (SELECT 1 FROM supplier_offers o WHERE o.id=c.offer_id AND o.company_id=c.company_id))"""
                elif key == 'invoice':
                    fields += ", 'offer_id',(SELECT o.id FROM supplier_offers o WHERE o.id=d.offer_id AND o.company_id=d.company_id)"
                    fields += ", 'contract_number',(SELECT c.snapshot_json->>'number' FROM supplier_contract_versions c WHERE c.id=d.contract_version_id AND c.company_id=d.company_id AND c.offer_id=d.offer_id)"
                    fields += ", 'contract_version',(SELECT c.version FROM supplier_contract_versions c WHERE c.id=d.contract_version_id AND c.company_id=d.company_id AND c.offer_id=d.offer_id)"
                    fields += ", 'contract_id',(SELECT c.id FROM supplier_contract_versions c WHERE c.id=d.contract_version_id AND c.company_id=d.company_id AND c.offer_id=d.offer_id)"
                relation = ''
                if contractId is not None:
                    relation = ' AND EXISTS (SELECT 1 FROM supplier_contract_versions c WHERE c.id=%s AND c.id=d.contract_version_id AND c.company_id=d.company_id AND c.offer_id=d.offer_id)'
                queries.append(f"""SELECT '{key}' AS source,d.id,d.company_id,
                    {title} AS title,{kind} AS kind,{date} AS created_at,
                    jsonb_build_object({fields}) AS files
                    FROM {table} d
                    WHERE d.company_id=%s AND {active}
                      AND (POSITION(LOWER(%s) IN LOWER({title}))>0
                           OR POSITION(LOWER(%s) IN LOWER({kind}))>0){relation}""")
                params.extend((company_id, q.strip(), q.strip()))
                if contractId is not None:
                    params.append(contractId)
            selection = ''
            if source is not None:
                selection = ' WHERE source=%s AND id=%s'
                params.extend((source, recordId))
            cur.execute('SELECT * FROM (' + ' UNION ALL '.join(queries) +
                        ') archive' + selection + ' ORDER BY created_at DESC NULLS LAST,source,id DESC LIMIT %s OFFSET %s',
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
                cur.execute("""SELECT id,project_id FROM file_ownership
                    WHERE company_id=%s
                      AND COALESCE(deletion_status,'active')='active'
                      AND '/tenant-files/' || id || '/content'=ANY(%s)""",
                            (company_id, list(set(references))))
                candidates = cur.fetchall()
                project_access = {}
                for file_id, project_id in candidates:
                    if project_id is not None and project_id not in project_access:
                        try:
                            project = resolve_project_parent(cur, actors[0], project_id=project_id)
                            require_project_parent_access(cur, actors[0], project, deps.get('project_full_view_roles', ()))
                            project_access[project_id] = True
                        except HTTPException as error:
                            if error.status_code not in (400, 403, 404, 409):
                                raise
                            project_access[project_id] = False
                    if project_id is None or project_access[project_id]:
                        safe_files[f'/tenant-files/{file_id}/content'] = (file_id, project_id)
            items = []
            for row, urls, malformed in parsed:
                source, source_id, owner, title, kind, created, _ = row
                payload = json.loads(row[6]) if isinstance(row[6], str) else (row[6] or {})
                def eligible(url):
                    return url in safe_files and (source != 'customer' or safe_files[url][1] == payload.get('project_id'))
                files = [{'fileId': safe_files[url][0], 'fileUrl': url} for url in urls if eligible(url)]
                unresolved = malformed + sum(not eligible(url) for url in urls)
                items.append({'id': f'{source}:{source_id}', 'source': source, 'sourceId': source_id,
                              'companyId': owner, 'title': title, 'documentType': kind,
                              'createdAt': str(created) if created else None,
                              'projectId': payload.get('project_id') if source == 'customer' else None,
                              'projectName': payload.get('project_name') if source == 'customer' else None,
                              'offerId': payload.get('offer_id') if source in ('contract', 'invoice') else None,
                              'contractId': payload.get('contract_id') if source == 'invoice' else None,
                              'applicability': payload.get('applicability') if source == 'contract' else None,
                              'scopeProjectName': payload.get('scope_project_name') if source == 'contract' else None,
                              'originContractId': payload.get('origin_contract_id') if source == 'contract' else None,
                              'contractNumber': payload.get('contract_number') if source == 'invoice' else None,
                              'contractVersion': payload.get('contract_version') if source == 'invoice' else None,
                              'status': payload.get('sign_status') if source == 'customer' else None,
                              'attachments': files, 'unavailableAttachments': unresolved,
                              'fileUrl': files[0]['fileUrl'] if files else None,
                              'fileStatus': 'needs_review' if unresolved else 'available' if files else 'not_attached'})
            return {'items': items, 'companyId': company_id, 'requiresCompanySelection': False,
                    'hasMore': len(rows) > limit, 'nextOffset': offset + limit if len(rows) > limit else None}
        finally:
            cur.close()
            conn.close()
