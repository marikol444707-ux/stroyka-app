"""Explicit original-document review, separate from new-invoice birth evidence.

Pure validation only: this grants no authority and performs no historical writes.
The caller must authorize/lock sources and require an unused, bound invoice.
"""
from decimal import Context, DecimalException, localcontext

from .invoice_line_spec import (_LINE_LIMIT, _MONEY_LIMIT, _aliases, _index,
                                _number, _rows, _text)
from .receipt_tax import invoice_tax_lines

_FIELDS = frozenset(('sourceRequestPosition', 'sourceOfferPosition', 'materialName',
                     'unit', 'workPackage', 'quantity', 'unitPrice', 'amount', 'vatAmount'))
_ERROR = 'Состав и НДС старого счёта не совпадают с проверенными исходными данными'


def _source_lines(request_json, offer_json, *, invoice_amount, offer_amount, work_package):
    package = _text(work_package)
    amount = _number(invoice_amount, '0.01')
    full_amount = _number(offer_amount, '0.01')
    if amount > full_amount:
        raise ValueError(_ERROR)
    requested = _index(_rows(request_json), package)
    offered = _index(_rows(offer_json), package)
    if requested.keys() != offered.keys():
        raise ValueError(_ERROR)
    lines = []
    source_total = 0
    for key, (request_position, request_row, request_quantity) in requested.items():
        offer_position, offer_row, offer_quantity = offered[key]
        if request_quantity != offer_quantity:
            raise ValueError(_ERROR)
        price = _aliases(offer_row, ('pricePerUnit', 'price_per_unit', 'unitPrice', 'unit_price'),
                         lambda value: _number(value, '0.000001', limit=_LINE_LIMIT))
        line_amount = _number(offer_quantity * price, '0.01')
        amount_keys = ('totalPrice', 'total_price', 'amount')
        if any(name in offer_row for name in amount_keys):
            declared = _aliases(offer_row, amount_keys, lambda value: _number(value, '0.01'))
            if declared != line_amount:
                raise ValueError(_ERROR)
        request_source = int(_number(request_row['requestPosition'], '1', limit=2000, zero=True)) if 'requestPosition' in request_row else request_position
        offer_source = int(_number(offer_row['quotePosition'], '1', limit=2000, zero=True)) if 'quotePosition' in offer_row else offer_position
        lines.append(dict(sourceRequestPosition=request_source, sourceOfferPosition=offer_source,
                          materialName=key[0], unit=key[1], workPackage=package,
                          maxQuantity=format(offer_quantity, '.6f'), unitPrice=format(price, '.6f')))
        source_total += line_amount
        if source_total >= _MONEY_LIMIT:
            raise ValueError(_ERROR)
    if source_total != full_amount:
        raise ValueError(_ERROR)
    if len({row['sourceRequestPosition'] for row in lines}) != len(lines):
        raise ValueError(_ERROR)
    if len({row['sourceOfferPosition'] for row in lines}) != len(lines):
        raise ValueError(_ERROR)
    return amount, full_amount, lines


def build_legacy_line_candidates(request_json, offer_json, *, invoice_amount, offer_amount,
                                 work_package):
    """Return KP-bounded rows and only exact proportional suggestions.

    A suggestion is convenience for human review, never source evidence. If the
    invoice total cannot be distributed proportionally without exact quantities
    and kopecks, quantities and amounts stay blank.
    """
    try:
        with localcontext(Context(prec=64)):
            amount, full_amount, source = _source_lines(
                request_json, offer_json, invoice_amount=invoice_amount,
                offer_amount=offer_amount, work_package=work_package)
            ratio = amount / full_amount
            suggested, suggested_total = [], 0
            try:
                for row in source:
                    quantity = _number(_number(row['maxQuantity'], '0.000001', limit=_LINE_LIMIT) * ratio,
                                       '0.000001', limit=_LINE_LIMIT)
                    line_amount = _number(quantity * _number(row['unitPrice'], '0.000001', limit=_LINE_LIMIT),
                                          '0.01')
                    suggested.append((quantity, line_amount))
                    suggested_total += line_amount
                if suggested_total != amount:
                    raise ValueError(_ERROR)
            except (ValueError, DecimalException):
                suggested = []
            lines = []
            for index, row in enumerate(source):
                suggestion = suggested[index] if suggested else None
                lines.append(dict(lineNo=index + 1, **row,
                    quantity=format(suggestion[0], '.6f') if suggestion else '',
                    amount=format(suggestion[1], '.2f') if suggestion else ''))
            return dict(amount=format(amount, '.2f'), workPackage=_text(work_package), lines=lines)
    except (ValueError, TypeError, KeyError, DecimalException, OverflowError, RecursionError):
        raise ValueError(_ERROR) from None


def build_legacy_line_review(*, invoice_amount, invoice_vat, offer_amount,
                             work_package, request_json, offer_json,
                             reviewed_lines, reviewed_vat):
    """Require every reviewed field, exact KP/request mapping and explicit tax.

    Total amounts include tax. Zero tax is explicit, never a missing-value default.
    Current KP/request rows are a cross-check, not proof of the original document;
    the transaction layer must retain that original and the human review event.
    """
    try:
        with localcontext(Context(prec=64)):
            tax = _number(invoice_vat, '0.01', zero=True)
            if tax != _number(reviewed_vat, '0.01', zero=True):
                raise ValueError(_ERROR)
            amount, _, candidates = _source_lines(
                request_json, offer_json, invoice_amount=invoice_amount,
                offer_amount=offer_amount, work_package=work_package)
            if (not isinstance(reviewed_lines, list) or not reviewed_lines
                    or len(reviewed_lines) > len(candidates)):
                raise ValueError(_ERROR)
            by_source = {(row['sourceRequestPosition'], row['sourceOfferPosition']): (index, row)
                         for index, row in enumerate(candidates)}
            normalized = []
            previous_index = -1
            total = 0
            for declared in reviewed_lines:
                if not isinstance(declared, dict) or declared.keys() != _FIELDS:
                    raise ValueError(_ERROR)
                if type(declared['sourceRequestPosition']) is not int or type(declared['sourceOfferPosition']) is not int:
                    raise ValueError(_ERROR)
                source_key = (declared['sourceRequestPosition'], declared['sourceOfferPosition'])
                if source_key not in by_source:
                    raise ValueError(_ERROR)
                source_index, expected = by_source[source_key]
                if source_index <= previous_index:
                    raise ValueError(_ERROR)
                previous_index = source_index
                line = dict(lineNo=len(normalized) + 1,
                            sourceRequestPosition=source_key[0], sourceOfferPosition=source_key[1])
                for key in ('materialName', 'unit', 'workPackage'):
                    line[key] = _text(declared[key])
                    if line[key] != expected[key]:
                        raise ValueError(_ERROR)
                quantity = _number(declared['quantity'], '0.000001', limit=_LINE_LIMIT)
                max_quantity = _number(expected['maxQuantity'], '0.000001', limit=_LINE_LIMIT)
                price = _number(declared['unitPrice'], '0.000001', limit=_LINE_LIMIT)
                expected_price = _number(expected['unitPrice'], '0.000001', limit=_LINE_LIMIT)
                declared_amount = _number(declared['amount'], '0.01')
                if quantity > max_quantity or price != expected_price or _number(quantity * price, '0.01') != declared_amount:
                    raise ValueError(_ERROR)
                line.update(quantity=format(quantity, '.6f'), unitPrice=format(price, '.6f'),
                            amount=format(declared_amount, '.2f'))
                line['vatAmount'] = format(_number(declared['vatAmount'], '0.01', zero=True), '.2f')
                normalized.append(line)
                total += declared_amount
            if total != amount:
                raise ValueError(_ERROR)
            invoice_tax_lines(normalized, invoice_amount=amount, invoice_vat_amount=tax)
            return dict(provenance='legacy_original_review', amount=format(amount, '.2f'),
                        vatAmount=format(tax, '.2f'), workPackage=_text(work_package), lines=normalized)
    except (ValueError, TypeError, KeyError, DecimalException, OverflowError, RecursionError):
        raise ValueError(_ERROR) from None
