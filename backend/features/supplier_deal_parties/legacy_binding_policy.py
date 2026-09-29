"""Fail-closed policy for a reviewed, unpaid legacy invoice transition.

No database writes or authority decisions. Caller must hold the company/offer/
invoice locks, authorize all parties and check the frozen contract snapshot.
"""
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException


def validate_legacy_binding(invoice, offer, contract, evidence):
    def require(condition, message):
        if not condition:
            raise HTTPException(409, message)

    require(invoice.get('contract_version_id') is None,
            'Счёт уже связан с договором. Замена версии этим действием запрещена')
    require(invoice.get('status') == 'На утверждении' and offer.get('status') == 'Утверждено',
            'Привязка доступна для счёта на утверждении по утверждённому КП')
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
