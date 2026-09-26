"""Pure projection for the deferred-allocation model, NOT the 0018 mirror.

Caller must supply a complete, authorized, consistent invoice snapshot, including
only current confirmed allocation rows (superseded corrections excluded). This
function is neither an authorization boundary nor a transaction service. It has
no database, stock, expense or payment writes. Suggestions are never confirmation.
Opening paid is shown separately until a reviewed historical allocation exists.
"""
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..supplier_deal_parties.payment_schedule import schedule_paid_amount


@dataclass(frozen=True)
class Scope:
    company_id: int
    payer_company_id: int
    supplier_id: int
    invoice_id: int


@dataclass(frozen=True)
class Payment:
    scope: Scope
    id: int
    amount: str
    reversed: bool = False


@dataclass(frozen=True)
class Receipt:
    scope: Scope
    id: int
    amount: str
    due_date: Optional[dt.date] = None


@dataclass(frozen=True)
class Allocation:
    scope: Scope
    id: int
    payment_id: int
    receipt_id: int
    amount: str


def _require(condition):
    if not condition:
        raise ValueError('Распределение оплат требует сверки')


def _id(value):
    _require(type(value) is int and 0 < value <= 9223372036854775807)


def _money(value, *, positive=False):
    _require(isinstance(value, (str, Decimal, int)) and not isinstance(value, bool))
    result = schedule_paid_amount(value)
    _require(not positive or result > 0)
    return result


def _scope(scope):
    _require(isinstance(scope, Scope))
    for value in (scope.company_id, scope.payer_company_id, scope.supplier_id, scope.invoice_id):
        _id(value)


def _rows(rows, scope, row_type):
    indexed = {}
    for row in rows:
        _require(isinstance(row, row_type) and row.scope == scope)
        _scope(row.scope)
        _id(row.id)
        _require(row.id not in indexed)
        indexed[row.id] = row
    return indexed


def allocation_projection(*, scope, invoice_amount, opening_paid, payments, receipts, allocations):
    """Return exact decimal strings; receipt balances are NOT additional debt.

Reversed payments retain their historical designations but contribute no money
and no receipt coverage. No remaining payment is moved to fill the resulting gap.
The transaction layer must serialize allocations with payment reversals.
"""
    _scope(scope)
    total, opening = _money(invoice_amount, positive=True), _money(opening_paid)
    payments = _rows(payments, scope, Payment)
    receipts = _rows(receipts, scope, Receipt)
    allocations = _rows(allocations, scope, Allocation)
    payment_amounts = {key: _money(row.amount, positive=True) for key, row in payments.items()}
    receipt_amounts = {key: _money(row.amount, positive=True) for key, row in receipts.items()}
    for row in payments.values():
        _require(type(row.reversed) is bool)
    for row in receipts.values():
        _require(row.due_date is None or type(row.due_date) is dt.date)
    _require(sum(receipt_amounts.values(), Decimal(0)) <= total)
    paid = opening + sum((payment_amounts[key] for key, row in payments.items() if not row.reversed), Decimal(0))
    _require(paid <= total)
    per_payment = dict.fromkeys(payments, Decimal(0))
    per_receipt = dict.fromkeys(receipts, Decimal(0))
    for row in allocations.values():
        _id(row.payment_id)
        _id(row.receipt_id)
        _require(row.payment_id in payments and row.receipt_id in receipts)
        amount = _money(row.amount, positive=True)
        _require(amount <= receipt_amounts[row.receipt_id])
        # Also validate a reversed payment's retained designations: reversal must
        # not conceal corrupt historical allocation sums.
        per_payment[row.payment_id] += amount
        _require(per_payment[row.payment_id] <= payment_amounts[row.payment_id])
        if not payments[row.payment_id].reversed:
            per_receipt[row.receipt_id] += amount
            _require(per_receipt[row.receipt_id] <= receipt_amounts[row.receipt_id])
    allocated = sum(per_receipt.values(), Decimal(0))
    free = paid - opening - allocated
    remaining = {key: receipt_amounts[key] - per_receipt[key] for key in receipts}
    ordered = sorted(receipts, key=lambda key: (
        receipts[key].due_date is None, receipts[key].due_date or dt.date.max, key))
    # Local scratch balances only; neither the returned confirmed projection nor
    # input rows are altered by building this optional suggestion.
    suggestion_capacity = remaining.copy()
    suggestions = []
    for key in sorted(payments):
        if payments[key].reversed:
            continue
        available = payment_amounts[key] - per_payment[key]
        for receipt_id in ordered:
            if available == 0:
                break
            amount = min(available, suggestion_capacity[receipt_id])
            if amount > 0:
                suggestions.append(dict(paymentId=key, receiptId=receipt_id, amount=format(amount, '.2f')))
                available -= amount
                suggestion_capacity[receipt_id] -= amount
    return dict(
        invoiceRemaining=format(total - paid, '.2f'), paid=format(paid, '.2f'),
        allocated=format(allocated, '.2f'), unallocatedPayments=format(free, '.2f'),
        openingPaidUnallocated=format(opening, '.2f'), needsAllocation=free + opening > 0,
        receipts=[dict(receiptId=key, amount=format(receipt_amounts[key], '.2f'),
                       allocated=format(per_receipt[key], '.2f'), remaining=format(remaining[key], '.2f'),
                       dueDate=receipts[key].due_date.isoformat() if receipts[key].due_date else None)
                  for key in sorted(receipts)],
        suggestions=suggestions,
    )
