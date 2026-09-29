"""Exact declared tax per invoice line and cumulative partial receipt amounts.

Amounts include tax. Rates and exemptions must come from the source document;
this module neither infers them nor distributes invoice tax between unrelated
lines. Caller must serialize receipts and provide their complete prior amount.
It grants no authority and writes no data; the flagged runtime adapter owns I/O.
"""
from decimal import Context, Decimal, DecimalException, ROUND_HALF_UP, localcontext

from .invoice_line_spec import _number


def _require(condition):
    if not condition:
        raise ValueError('Суммы НДС и поступлений требуют сверки')


def invoice_tax_lines(lines, *, invoice_amount, invoice_vat_amount):
    """Validate explicit line taxes against both invoice totals, without guessing."""
    try:
        with localcontext(Context(prec=64, rounding=ROUND_HALF_UP)):
            _require(isinstance(lines,list) and 0<len(lines)<=2000)
            gross=_number(invoice_amount,'0.01')
            tax=_number(invoice_vat_amount,'0.01',zero=True)
            result=[];seen=set()
            for line in lines:
                _require(isinstance(line,dict))
                number=line['lineNo']
                _require(type(number) is int and 1<=number<=2000 and number not in seen)
                seen.add(number)
                amount=_number(line['amount'],'0.01')
                vat=_number(line['vatAmount'],'0.01',zero=True)
                _require(vat<=amount)
                result.append(dict(lineNo=number,amount=format(amount,'.2f'),
                    vatAmount=format(vat,'.2f'),baseAmount=format(amount-vat,'.2f')))
            _require(sum(Decimal(row['amount']) for row in result)==gross)
            _require(sum(Decimal(row['vatAmount']) for row in result)==tax)
            return result
    except (KeyError,ValueError,TypeError,DecimalException,OverflowError):
        raise ValueError('НДС по строкам не совпадает со счётом') from None


def receipt_tax_slice(*, line_amount, line_vat_amount, previous_amount, received_amount):
    """Difference of rounded cumulative tax, keeping every final penny.

    Example: a 1.00 line with 0.17 tax received as .33/.33/.34 produces
    .06/.05/.06 tax. Rejected quantities must not consume accepted amounts;
    replacement and return policy belongs to the transaction layer.
    """
    try:
        with localcontext(Context(prec=64, rounding=ROUND_HALF_UP)):
            total=_number(line_amount,'0.01')
            tax=_number(line_vat_amount,'0.01',zero=True)
            before=_number(previous_amount,'0.01',zero=True)
            amount=_number(received_amount,'0.01')
            _require(tax<=total and before+amount<=total)
            cumulative=lambda value:(tax*value/total).quantize(Decimal('0.01'))
            vat=cumulative(before+amount)-cumulative(before)
            _require(0<=vat<=amount)
            return dict(amount=format(amount,'.2f'),vatAmount=format(vat,'.2f'),
                        baseAmount=format(amount-vat,'.2f'))
    except (ValueError,TypeError,DecimalException,OverflowError):
        raise ValueError('НДС частичного поступления требует сверки') from None
