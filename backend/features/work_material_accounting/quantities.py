"""Exact boundary validation; never turn missing source evidence into a guess."""
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException


def _decimal(value, places, maximum, zero):
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or (result == 0 and not zero):
            raise ValueError()
        if result >= maximum or result != result.quantize(Decimal(1).scaleb(-places)):
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(400, 'Укажите корректное количество или сумму без лишнего округления')


def quantity(value, *, zero=False):
    return _decimal(value, 6, Decimal('100000000'), zero)


def money(value, *, zero=True):
    return _decimal(value, 2, Decimal('1000000000000'), zero)


def source_quantities(item):
    if not isinstance(item, dict):
        raise HTTPException(400, 'Строка расхода материала должна быть объектом')
    total = quantity(item.get('quantity'))
    personal = quantity(item.get('personalQuantity'), zero=True)
    warehouse = quantity(item.get('warehouseQuantity'), zero=True)
    if total != personal + warehouse:
        raise HTTPException(400, 'Сумма расхода со склада и у исполнителя должна совпадать с расходом материала')
    return total, personal, warehouse


def validate_items(items):
    if not isinstance(items, list):
        raise HTTPException(400, 'Материалы работы должны быть списком')
    for item in items:
        source_quantities(item)
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise HTTPException(400, 'Укажите наименование каждой строки расхода')
        for field in ('unit', 'workPackage'):
            if item.get(field) is not None and not isinstance(item[field], str):
                raise HTTPException(400, 'Некорректная единица или пакет материала')
