"""Pure, exact line specification for new invoices, never historical repair.

Identity is the trimmed, case-sensitive (name, unit, package) tuple. There is
no unit conversion, default package/quantity, price inference, or duplicate
merging. Request order defines line numbers; original positions are retained.
Offer unit price is mandatory; an optional explicit line total must agree.
All exported numbers are fixed-scale strings. This module grants no authority.
"""
import json
import re
from decimal import Context, Decimal, DecimalException, localcontext


_ERROR = 'Invalid invoice line specification'
_MAX_JSON_BYTES = 1024 * 1024
_MAX_LINES = 2000
_LINE_LIMIT = Decimal('1e12')
# Match the ledger's NUMERIC(14,2), including computed line amounts and sum.
_MONEY_LIMIT = Decimal('1e12')
_NUMERIC = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')


def _require(condition):
    if not condition:
        raise ValueError(_ERROR)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(_ERROR)


def _rows(raw):
    _require(isinstance(raw, str) and len(raw) <= _MAX_JSON_BYTES)
    _require(len(raw.encode('utf-8')) <= _MAX_JSON_BYTES)
    rows = json.loads(raw, parse_int=Decimal, parse_float=Decimal,
                      parse_constant=_invalid_constant, object_pairs_hook=_object)
    _require(isinstance(rows, list) and 0 < len(rows) <= _MAX_LINES)
    _require(all(isinstance(row, dict) for row in rows))
    return rows


def _text(value):
    _require(isinstance(value, str))
    value = value.strip()
    _require(bool(value) and '\x00' not in value)
    value.encode('utf-8')
    return value


def _number(value, scale, *, limit=_MONEY_LIMIT, zero=False):
    _require(type(value) in (str, int, Decimal))
    if isinstance(value, str):
        _require(len(value) <= _MAX_JSON_BYTES and _NUMERIC.fullmatch(value) is not None)
    value = Decimal(value)
    _require(value.is_finite())
    _require((value >= 0 if zero else value > 0) and value < limit)
    exact = value.quantize(Decimal(scale))
    _require(value == exact)
    return exact


def _aliases(row, keys, normalize):
    values = [normalize(row[key]) for key in keys if key in row]
    _require(bool(values) and all(value == values[0] for value in values))
    return values[0]


def _index(rows, package):
    result = {}
    for position, row in enumerate(rows):
        key = (_aliases(row, ('materialName', 'material_name', 'name'), _text),
               _aliases(row, ('unit',), _text),
               _aliases(row, ('workPackage', 'work_package'), _text))
        _require(key[2] == package and key not in result)
        quantity = _aliases(row, ('quantity',),
                            lambda value: _number(value, '0.000001', limit=_LINE_LIMIT))
        result[key] = (position, row, quantity)
    return result


def build_invoice_line_spec(request_json, offer_json, *, invoice_amount, offer_amount,
                            vat_amount, vat_included, work_package):
    """Validate both complete arrays or raise a generic ValueError, with no I/O.

    Text identities are trimmed only, never case-folded or normalized by name.
    Price aliases: pricePerUnit/price_per_unit/unitPrice/unit_price. Optional
    amount aliases: totalPrice/total_price/amount. Present aliases must agree,
    including when one is empty, null, false or otherwise invalid.
    """
    try:
        # Do not inherit caller precision/rounding/traps or alter their context.
        with localcontext(Context(prec=64)):
            package = _text(work_package)
            _require(vat_included is False)
            _require(_number(vat_amount, '0.01', zero=True) == 0)
            amount = _number(invoice_amount, '0.01')
            _require(amount == _number(offer_amount, '0.01'))
            requested = _index(_rows(request_json), package)
            offered = _index(_rows(offer_json), package)
            _require(requested.keys() == offered.keys())
            lines, total = [], Decimal(0)
            for key, (request_position, _, quantity) in requested.items():
                offer_position, row, offer_quantity = offered[key]
                _require(quantity == offer_quantity)
                price = _aliases(row, ('pricePerUnit', 'price_per_unit', 'unitPrice', 'unit_price'),
                                 lambda value: _number(value, '0.000001', limit=_LINE_LIMIT))
                line_amount = _number(quantity * price, '0.01')
                amount_keys = ('totalPrice', 'total_price', 'amount')
                if any(name in row for name in amount_keys):
                    _require(line_amount == _aliases(row, amount_keys, lambda value: _number(value, '0.01')))
                total += line_amount
                _require(total < _MONEY_LIMIT)
                lines.append(dict(lineNo=request_position + 1, sourceRequestPosition=request_position,
                    sourceOfferPosition=offer_position, materialName=key[0], unit=key[1], workPackage=package,
                    quantity=format(quantity, '.6f'), unitPrice=format(price, '.6f'), amount=format(line_amount, '.2f')))
            _require(total == amount)
            return dict(amount=format(amount, '.2f'), workPackage=package, lines=lines)
    except (ValueError, TypeError, DecimalException, OverflowError, RecursionError):
        raise ValueError(_ERROR) from None
