"""Check reviewed scan arithmetic before the physical receipt transaction writes."""
from decimal import Decimal, InvalidOperation


def amount(value):
    try:
        if isinstance(value, bool) or value is None or value == '':
            return None
        result = Decimal(str(value).replace('\u00a0', '').replace(' ', '').replace(',', '.'))
        return result if result.is_finite() and abs(result) <= Decimal('1000000000000000') else None
    except (InvalidOperation, ValueError):
        return None


def scan_amount_errors(payload):
    errors = []
    total = Decimal(0)
    items = payload.get('items') or []
    for index, item in enumerate(items, 1):
        quantity, price, line = (amount(item.get(k)) for k in ('quantity','price','lineTotal'))
        if quantity is None or quantity <= 0 or price is None or price < 0 or line is None or line < 0:
            errors.append(f'Строка {index}: проверьте количество, цену и сумму')
            continue
        # Printed unit price can be rounded; allow its half-unit rounding error.
        places = max(2, min(4, -price.as_tuple().exponent))
        tolerance = quantity * Decimal(10) ** -places / 2 + Decimal('.01')
        if abs(quantity * price - line) > tolerance:
            errors.append(f'Строка {index}: количество × цена не соответствует сумме')
        total += line
    declared = amount(payload.get('totalWithVat'))
    if declared is None or declared < 0 or abs(total - declared) > max(Decimal('.02'), len(items) * Decimal('.01')):
        errors.append('Сумма строк не соответствует итогу оригинала. Проверьте суммы')
    base, vat = amount(payload.get('totalBase')), amount(payload.get('totalVat'))
    if base is None or vat is None or base < 0 or vat < 0 or declared is None or abs(base + vat - declared) > Decimal('.02'):
        errors.append('Сумма без НДС и НДС не соответствуют итогу оригинала')
    return errors
