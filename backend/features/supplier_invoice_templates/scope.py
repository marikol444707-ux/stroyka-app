"""Company-scoped, read-only recognition. OCR never authorizes a supplier by name."""
import re
from fastapi import HTTPException
from backend.features.company_context.service import effective_company_actors


def resolve_scan_company(cur, user, resolve_context, roles, *, company_id=None,
                         x_company_id=None, x_company_mode=None):
    context = resolve_context(cur, user, company_id, 'write',
                              x_company_id=x_company_id, x_company_mode=x_company_mode)
    actors = effective_company_actors(user, context)
    owner = context.get('companyId')
    if not owner or len(actors) != 1:
        raise HTTPException(409, 'Выберите одну компанию для распознавания документа')
    if actors[0].get('role') not in roles:
        raise HTTPException(403, 'Роль в выбранной компании не позволяет распознавать документы')
    return int(owner)


def exact_supplier(cur, company_id, payload):
    # A model-provided ID/name is not an identity. Ambiguous INNs require review.
    inn = re.sub(r'\D', '', str(payload.get('supplierInn') or payload.get('supplier_inn') or payload.get('inn') or ''))
    if len(inn) not in (10, 12):
        return None
    cur.execute('''SELECT s.* FROM suppliers s
                   JOIN company_supplier_links l ON l.supplier_id=s.id
                   WHERE l.company_id=%s AND regexp_replace(COALESCE(s.inn,''),'[^0-9]','','g')=%s
                   ORDER BY s.id LIMIT 2''', (company_id, inn))
    rows = cur.fetchall()
    return rows[0] if len(rows) == 1 else None


def receipt_supplier(cur, company_id, payload):
    """A receipt may reuse an owned ID or exact owned INN, never a global name."""
    raw_id = payload.get('supplierId') or payload.get('supplier_id')
    if not raw_id:
        return exact_supplier(cur, company_id, payload)
    try:
        supplier_id = int(str(raw_id))
        if supplier_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise HTTPException(400, 'Некорректный идентификатор поставщика')
    cur.execute('''SELECT s.* FROM suppliers s JOIN company_supplier_links l ON l.supplier_id=s.id
                   WHERE s.id=%s AND l.company_id=%s FOR KEY SHARE OF l''', (supplier_id, company_id))
    supplier = cur.fetchone()
    if not supplier:
        raise HTTPException(403, 'Поставщик недоступен в выбранной компании')
    claimed_inn = re.sub(r'\D', '', str(payload.get('supplierInn') or payload.get('supplier_inn') or payload.get('inn') or ''))
    known_inn = re.sub(r'\D', '', str(supplier.get('inn') or ''))
    if claimed_inn and claimed_inn != known_inn:
        raise HTTPException(409, 'ИНН документа не совпадает с выбранным поставщиком. Проверьте оригинал и карточку поставщика')
    return supplier
