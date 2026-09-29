"""Fail-closed policy for a reviewed, unpaid legacy invoice transition.

No database writes or authority decisions. Caller must hold the company/offer/
invoice locks, authorize all parties and check the frozen contract snapshot.
"""
import datetime as dt
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException


def _document_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _display_date(value):
    return value.strftime('%d.%m.%Y')


def legacy_binding_warnings(invoice, contract):
    """Return facts requiring human review without deciding legal validity."""
    snapshot = contract.get('snapshot_json') if isinstance(contract, dict) else None
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    invoice_date = _document_date(invoice.get('invoice_date'))
    contract_date = _document_date(snapshot.get('date'))
    warnings = []
    if invoice_date is None or contract_date is None:
        warnings.append({
            'code': 'document_dates_require_review',
            'message': 'Дата счёта или договора не распознана. Сверьте обе даты по оригиналам.',
        })
    elif invoice_date < contract_date:
        warnings.append({
            'code': 'invoice_predates_contract',
            'message': (
                f'Счёт от {_display_date(invoice_date)} выставлен раньше договора '
                f'от {_display_date(contract_date)}. Подтвердите, что договор относится к этому счёту.'
            ),
        })
    if snapshot.get('signatureStatus') != 'verified':
        warnings.append({
            'code': 'contract_signature_not_verified',
            'message': 'Подписи в оригинале договора нужно проверить перед привязкой счёта.',
        })
    return warnings


def validate_legacy_binding(invoice, offer, contract, evidence):
    def require(condition, message):
        if not condition:
            raise HTTPException(409, message)

    require(invoice.get('contract_version_id') is None,
            'Счёт уже связан с договором. Замена версии этим действием запрещена')
    require(invoice.get('status') in ('На утверждении', 'Утверждён')
            and offer.get('status') == 'Утверждено',
            'Привязка доступна для неоплаченного счёта по утверждённому КП')
    require(invoice.get('warehouse_invoice_id') is None,
            'Счёт уже связан с накладной. Требуется отдельная сверка')
    require(all(evidence.get(key) is False for key in ('ledger', 'receipts', 'deliveries', 'sealed_lines')),
            'По счёту есть учётные данные или поставки. Требуется отдельная сверка')
    require(all(type(invoice.get(key)) is int and invoice[key] > 0 and invoice[key] == offer.get(other)
                for key, other in (('company_id', 'company_id'), ('supplier_id', 'supplier_id'),
                                   ('request_id', 'request_id'), ('offer_id', 'id'))),
            'Компания, поставщик или заявка счёта не совпадают с КП')
    require(bool(invoice.get('project_name')) and invoice['project_name'] == offer.get('project')
            and isinstance(invoice.get('work_package'), str)
            and invoice['work_package'] == offer.get('work_package'),
            'Объект или раздел счёта не совпадает с КП')
    require(contract.get('company_id') == invoice['company_id']
            and contract.get('offer_id') == invoice['offer_id']
            and contract.get('reviewed_at') and contract.get('reviewed_by')
            and type(contract.get('party_version')) is int
            and contract['party_version'] == contract.get('current_party_version'),
            'Выберите проверенную версию договора с актуальными сторонами сделки')
    try:
        amount, paid = Decimal(str(invoice['amount'])), Decimal(str(invoice['paid_amount']))
        valid = (amount.is_finite() and paid.is_finite() and amount > 0 and paid == 0
                 and amount == amount.quantize(Decimal('0.01')))
    except (KeyError, ValueError, InvalidOperation):
        valid = False
    require(valid, 'Счёт должен иметь корректную сумму и подтверждённое нулевое поле оплаты')
