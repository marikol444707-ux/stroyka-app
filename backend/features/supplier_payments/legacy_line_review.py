"""Explicit original-document review, separate from new-invoice birth evidence.

Pure validation only: this grants no authority and performs no historical writes.
The caller must authorize/lock sources and require an unused, bound invoice.
"""
from decimal import Context, DecimalException, localcontext

from .invoice_line_spec import build_invoice_line_spec, _number, _text
from .receipt_tax import invoice_tax_lines

_FIELDS = frozenset(('sourceRequestPosition', 'sourceOfferPosition', 'materialName',
                     'unit', 'workPackage', 'quantity', 'unitPrice', 'amount', 'vatAmount'))
_ERROR = 'Состав и НДС старого счёта не совпадают с проверенными исходными данными'


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
            # Reuse exact quantity/price/source matching, not its birth writer.
            spec = build_invoice_line_spec(request_json, offer_json,
                invoice_amount=invoice_amount, offer_amount=offer_amount,
                vat_amount=0, vat_included=False, work_package=work_package)
            if not isinstance(reviewed_lines, list) or len(reviewed_lines) != len(spec['lines']):
                raise ValueError(_ERROR)
            normalized = []
            for declared, expected in zip(reviewed_lines, spec['lines']):
                if not isinstance(declared, dict) or declared.keys() != _FIELDS:
                    raise ValueError(_ERROR)
                line = dict(lineNo=expected['lineNo'])
                for key in ('sourceRequestPosition', 'sourceOfferPosition'):
                    if type(declared[key]) is not int or declared[key] != expected[key]:
                        raise ValueError(_ERROR)
                    line[key] = declared[key]
                for key in ('materialName', 'unit', 'workPackage'):
                    line[key] = _text(declared[key])
                for key in ('quantity', 'unitPrice', 'amount'):
                    scale = '0.01' if key == 'amount' else '0.000001'
                    line[key] = format(_number(declared[key], scale), 'f')
                if any(line[key] != value for key, value in expected.items()):
                    raise ValueError(_ERROR)
                line['vatAmount'] = format(_number(declared['vatAmount'], '0.01', zero=True), '.2f')
                normalized.append(line)
            invoice_tax_lines(normalized, invoice_amount=spec['amount'], invoice_vat_amount=tax)
            return dict(provenance='legacy_original_review', amount=spec['amount'],
                        vatAmount=format(tax, '.2f'), workPackage=spec['workPackage'], lines=normalized)
    except (ValueError, TypeError, KeyError, DecimalException, OverflowError):
        raise ValueError(_ERROR) from None
