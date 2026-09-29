"""Capture exact stock identities without attributing historical ownership."""
from decimal import Decimal

from fastapi import HTTPException

from . import policy
from ..warehouse_distribution.models import MAIN
from ..warehouse_distribution.service import lock_projects, normalized_unit_sql
from ..work_material_accounting.quantities import quantity


def project(cur, project_id, actor, deps):
    if project_id is None:
        if actor['role'] == 'прораб':
            raise HTTPException(403, 'Прораб проводит сверку только на назначенном объекте')
        return MAIN
    if isinstance(project_id, bool) or not isinstance(project_id, int) or not 0 < project_id <= 2147483647:
        raise HTTPException(400, 'Выберите точный объект')
    name = lock_projects(cur, actor['companyId'], [project_id])[project_id]
    if actor['role'] == 'прораб' and name not in deps['user_project_names'](actor):
        raise HTTPException(403, 'Нет доступа к объекту')
    return name


def lot_snapshot(cur, company_id, row):
    lot_unit_sql = normalized_unit_sql().replace('coalesce(unit,', 'coalesce(l.unit,')
    cur.execute(f'''SELECT l.id,l.warehouse_invoice_id,l.invoice_line_index,l.material_name,l.unit,
        l.available_quantity,l.received_quantity,l.document_quantity,l.document_unit,l.status,
        i.items,i.status AS invoice_status,i.company_id AS invoice_company,i.project,i.location
        FROM warehouse_receipt_lots l LEFT JOIN warehouse_invoices i ON i.id=l.warehouse_invoice_id
        WHERE l.company_id=%s AND l.warehouse_target='main' AND l.warehouse_location=%s
        AND lower(l.material_name)=lower(%s) AND {lot_unit_sql}={normalized_unit_sql('%s')}
        AND l.status='active' ORDER BY l.id''', (company_id, MAIN, row['name'], row['unit']))
    result = []
    for lot in cur.fetchall():
        available = quantity(lot['available_quantity'], zero=True)
        if lot['invoice_company'] != company_id or lot['invoice_status'] == 'Аннулирована':
            raise HTTPException(409, 'Источник партии требует проверки перед инвентаризацией')
        result.append({'lotId': lot['id'], 'invoiceId': lot['warehouse_invoice_id'],
                       'lineIndex': lot['invoice_line_index'], 'quantity': policy.decimal_text(available),
                       'fingerprint': policy.fingerprint(dict(lot))})
    return result


def capture(cur, actor, project_id, deps):
    name = project(cur, project_id, actor, deps)
    company_id = actor['companyId']
    table = 'materials' if project_id else 'warehouse_main'
    package = "coalesce(nullif(work_package,''),'Основная')" if project_id else "''"
    extra, args = (' AND project=%s', [name]) if project_id else ('', [])
    cur.execute(f'''SELECT id,name,unit,quantity,{package} AS package FROM {table}
        WHERE company_id=%s {extra} ORDER BY id FOR UPDATE''', [company_id, *args])
    stock = [dict(r) for r in cur.fetchall()]
    if len(stock) > 3000:
        raise HTTPException(409, 'Склад превышает размер одной сверки; требуется разделить учёт')
    rows = []
    for material in stock:
        q = quantity(material['quantity'], zero=True)
        row = {'key': f'{table}:{material["id"]}', 'kind': 'material', 'stockTable': table,
               'stockId': material['id'], 'name': material['name'], 'unit': material['unit'],
               'package': material['package'], 'expected': policy.decimal_text(q)}
        lots = lot_snapshot(cur, company_id, material) if not project_id else []
        # Ambiguous aggregate keys cannot truthfully allocate the same lot twice.
        if lots:
            cur.execute(f'''SELECT count(*) AS n FROM warehouse_main WHERE company_id=%s
                AND lower(name)=lower(%s) AND {normalized_unit_sql()}={normalized_unit_sql('%s')}''',
                        (company_id, material['name'], material['unit']))
            if cur.fetchone()['n'] != 1:
                raise HTTPException(409, 'Один материал повторяется в карточках основного склада; нужна сверка карточек')
        untracked = q - sum((Decimal(l['quantity']) for l in lots), Decimal(0))
        if untracked < 0:
            raise HTTPException(409, 'Сумма партий превышает складской остаток; сначала требуется сверка происхождения')
        rows.append({**row, 'lots': lots, 'untrackedQuantity': policy.decimal_text(untracked)})
    cur.execute('''SELECT id,name,inventory_number,status,location,master_id,master_name,project_id,
        project,custody_version,custody_contract_id FROM tools
        WHERE company_id=%s AND project_id IS NOT DISTINCT FROM %s AND status<>'В архиве'
        ORDER BY id FOR UPDATE''', (company_id, project_id))
    for tool in cur.fetchall():
        rows.append({'key': f'tool:{tool["id"]}', 'kind': 'tool', 'toolId': tool['id'],
                     'name': tool['name'], 'inventoryNumber': tool['inventory_number'],
                     'status': tool['status'], 'holderName': tool['master_name'],
                     'fingerprint': policy.fingerprint(dict(tool))})
    if not rows:
        raise HTTPException(409, 'В выбранном месте нет материалов или инструмента для сверки')
    return {'projectId': project_id, 'project': name, 'rows': rows}
