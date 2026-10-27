"""Native PDF seller evidence and conservative, read-only template eligibility."""
import re


def native_pdf_seller(parts):
    found = set()
    for part in parts:
        if getattr(part, 'kind', '') != 'text':
            continue
        text = str(getattr(part, 'value', '') or '')
        name = re.search(r'^\s*Продавец\s*:?\s+([^\n]+)', text, re.M | re.I)
        tax = re.search(r'^\s*ИНН\s*/\s*КПП\s+продавца\s*:?\s*(\d{10}|\d{12})\s*/\s*(\d{9})', text, re.M | re.I)
        if name and tax and 0 < tax.start() - name.start() < 1500:
            title = re.sub(r'\s+\(2\)\s*$', '', name[1]).strip()
            found.add((title, tax[1], tax[2]))
    if len(found) != 1:
        return {}
    title, inn, kpp = found.pop()
    return {'supplier': title, 'supplierInn': inn, 'supplierKpp': kpp}


def template_matches_supplier(payload, supplier, template):
    if not supplier or str(template.get('supplierId') or '') != str(supplier.get('id') or ''):
        return False
    digits = lambda value: re.sub(r'\D', '', str(value or ''))
    inn = digits(payload.get('supplierInn') or payload.get('supplier_inn'))
    expected = digits(supplier.get('inn'))
    return len(inn) in (10, 12) and inn == expected
