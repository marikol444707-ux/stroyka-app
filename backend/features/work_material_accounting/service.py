"""Posting actual use: the caller owns authorization, stock lock and transaction."""
import json
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException

from .quantities import quantity, source_quantities, validate_items


def as_dict(row, names):
    return row if isinstance(row, dict) else dict(zip(names, row))


def prepare(cur, project, actor, items, *, material_key, personal_balance, norm_unit):
    company_id, project_name = project['companyId'], project['name']
    validate_items(items)
    grouped = {}
    for item in items:
        if not isinstance(item, dict) or not str(item.get('name') or '').strip():
            raise HTTPException(400, 'Укажите материал для расхода')
        total, personal, warehouse = source_quantities(item)
        unit = norm_unit(item.get('unit') or 'шт')
        package = str(item.get('workPackage') or 'Основная').strip()
        key = (material_key(cur, project_name, item['name'], unit, company_id=company_id), package)
        if norm_unit(key[0][1]) != unit:
            raise HTTPException(409, 'Единица материала не совпадает с единицей соответствия')
        stock_id = item.get('warehouseMaterialId') if warehouse else None
        if warehouse and (isinstance(stock_id, bool) or not isinstance(stock_id, int) or stock_id <= 0):
            raise HTTPException(400, 'Выберите точный материал на складе объекта')
        if key in grouped:
            prior = grouped[key]
            if prior['unit'] != unit:
                raise HTTPException(409, 'Нельзя суммировать разные единицы материала')
            if warehouse and prior['warehouseMaterialId'] not in (None, stock_id):
                raise HTTPException(409, 'Для одного материала выбран неоднозначный складской остаток')
            prior['quantity'] += total
            prior['personalQuantity'] += personal
            prior['warehouseQuantity'] += warehouse
            prior['warehouseMaterialId'] = prior['warehouseMaterialId'] or stock_id
        else:
            grouped[key] = {**item, 'unit': unit, 'workPackage': package,
                            'quantity': total, 'personalQuantity': personal,
                            'warehouseQuantity': warehouse, 'warehouseMaterialId': stock_id}
    result = []
    for (key, package), item in grouped.items():
        source_quantities(item)  # Bounds also apply to aggregate duplicates.
        # Never trust identity metadata supplied by a browser.
        item['identitySnapshot'] = {'key': list(key), 'sources': [
            {'name': item['name'], 'unit': item['unit']}]}
        if item['personalQuantity']:
            balance = personal_balance(cur, project_name, actor['id'], actor.get('name') or '',
                                       item['name'], package, item['unit'], company_id=company_id, include_identity=True)
            available = Decimal(str(balance['available']))
            if not available.is_finite() or available < item['personalQuantity']:
                raise HTTPException(400, 'Недостаточно подтверждённого материала у исполнителя')
            item['identitySnapshot']['sources'].extend(balance.get('identitySources', []))
        item['_stock'] = None
        if item['warehouseQuantity']:
            cur.execute('''SELECT id,name,unit,quantity,price,work_package FROM materials
                WHERE id=%s AND company_id=%s AND project=%s FOR UPDATE''',
                        (item['warehouseMaterialId'], company_id, project_name))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, 'Материал на складе выбранного объекта не найден')
            stock = as_dict(row, ('id', 'name', 'unit', 'quantity', 'price', 'work_package'))
            stock_key = material_key(cur, project_name, stock['name'], stock['unit'], company_id=company_id)
            if stock_key != key or norm_unit(stock['unit']) != item['unit'] or (stock['work_package'] or 'Основная') != package:
                raise HTTPException(409, 'Материал, единица или пакет не совпадают с выбранным остатком')
            available = quantity(stock['quantity'], zero=True)
            if available < item['warehouseQuantity']:
                raise HTTPException(400, 'Недостаточно материала на складе объекта')
            item['_stock'] = stock
        result.append(item)
    return result


def public_items(items):
    return [{key: float(value) if isinstance(value, Decimal) else value
             for key, value in item.items() if not key.startswith('_')} for item in items]


def post(cur, project, actor, journal_id, operation_id, items, work_date):
    company_id = project['companyId']
    cur.execute('''SELECT c.id FROM work_journal w
        JOIN brigade_contract_items i ON i.id=w.contract_item_id
        JOIN brigade_contracts c ON c.id=i.contract_id
        WHERE w.id=%s AND c.company_id=%s AND c.project_id=%s''',
                (journal_id, company_id, project['id']))
    contract = cur.fetchone()
    if not contract:
        raise HTTPException(409, 'Для учёта расхода требуется точный договор исполнителя по объекту')
    contract_id = contract['id'] if isinstance(contract, dict) else contract[0]
    from .settlement import CONTRACT_TYPES
    cur.execute('UPDATE brigade_contracts SET settlement_version=2 WHERE id=%s AND contractor_type=ANY(%s)',
                (contract_id, sorted(CONTRACT_TYPES)))
    cur.execute('UPDATE work_journal SET material_accounting_version=2,materials_used=%s WHERE id=%s',
                (json.dumps(public_items(items), ensure_ascii=False), journal_id))
    cur.execute('''INSERT INTO work_material_accounts
        (journal_id,company_id,project_id,actor_id,contract_id,operation_id)
        VALUES(%s,%s,%s,%s,%s,%s)''',
                (journal_id, company_id, project['id'], actor['id'], contract_id, operation_id))
    for item in items:
        stock = item['_stock']
        unit_price = None
        if stock:
            after = quantity(stock['quantity'], zero=True) - item['warehouseQuantity']
            cur.execute('UPDATE materials SET quantity=%s WHERE id=%s AND company_id=%s RETURNING quantity',
                        (after, stock['id'], company_id))
            row = cur.fetchone()
            actual = row['quantity'] if isinstance(row, dict) else row[0]
            if Decimal(str(actual)) != after:
                raise HTTPException(409, 'Склад не может сохранить количество с требуемой точностью')
            try:
                price = Decimal(str(stock['price']))
                if price.is_finite() and 0 < price < Decimal('100000000000000'):
                    unit_price = price.quantize(Decimal('0.0001'))
            except (InvalidOperation, ValueError, TypeError):
                pass
        for source, field in (('personal', 'personalQuantity'), ('warehouse', 'warehouseQuantity')):
            used = item[field]
            if not used:
                continue
            cur.execute('''INSERT INTO work_material_entries
                (company_id,journal_id,operation_id,source,warehouse_material_id,
                 material_name,unit,work_package,quantity,unit_price,reason,identity_snapshot)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                        (company_id, journal_id, operation_id, source,
                         stock['id'] if source == 'warehouse' else None, item['name'], item['unit'],
                         item['workPackage'], used, unit_price if source == 'warehouse' else None,
                         'Расход по выполненной работе', json.dumps(item['identitySnapshot'], ensure_ascii=False)))
            row = cur.fetchone()
            entry_id = row['id'] if isinstance(row, dict) else row[0]
            cur.execute('''INSERT INTO warehouse_history
                (company_id,material,type,quantity,unit,date,project,issued_to,issued_by,
                 work_package,source_type,source_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (company_id, item['name'], 'расход (работа мастера)', used,
                         item['unit'], work_date or None, project['name'], actor.get('name') or '',
                         actor.get('name') or '', item['workPackage'], 'work_material_entry', entry_id))
