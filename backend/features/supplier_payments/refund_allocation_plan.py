"""Pure refund plans for complete authorized snapshots; no financial writes.

Not wired into settlement routes. A future transaction must persist the source
payment link and allocation revision together before runtime guards can change.
"""
from dataclasses import dataclass, replace
from decimal import Decimal

from .allocation_projection import (
    Scope, Payment, Allocation, allocation_projection,
    _scope, _rows, _id, _money, _require,
)


@dataclass(frozen=True)
class Refund:
    scope: Scope
    id: int
    payment_id: int
    amount: str
    reversed: bool = False


@dataclass(frozen=True)
class Release:
    receipt_id: int
    amount: str


def _net_payments(scope, payments, refunds):
    _scope(scope)
    indexed = _rows(payments, scope, Payment)
    amounts = {}
    for key, row in indexed.items():
        _require(type(row.reversed) is bool)
        amounts[key] = _money(row.amount, positive=True)
    returned = dict.fromkeys(indexed, Decimal(0))
    for row in _rows(refunds, scope, Refund).values():
        _id(row.payment_id)
        _require(row.id not in indexed and row.payment_id in indexed)
        _require(type(row.reversed) is bool)
        amount = _money(row.amount, positive=True)
        _require(amount <= amounts[row.payment_id])
        if not row.reversed:
            _require(not indexed[row.payment_id].reversed)
            returned[row.payment_id] += amount
            _require(returned[row.payment_id] <= amounts[row.payment_id])
    return [replace(row, amount=format(amounts[key] - returned[key], '.2f'))
            for key, row in indexed.items() if amounts[key] > returned[key]]


def refund_projection(*, scope, invoice_amount, opening_paid, payments,
                      receipts, allocations, refunds):
    """Project already-adjusted allocations; refund reversal restores free cash."""
    return allocation_projection(
        scope=scope, invoice_amount=invoice_amount, opening_paid=opening_paid,
        payments=_net_payments(scope, payments, refunds),
        receipts=receipts, allocations=allocations,
    )


def plan_refund(*, scope, invoice_amount, opening_paid, payments, receipts,
                allocations, refunds, refund, releases, unallocated_amount):
    """Release only explicitly selected coverage of the explicit source payment."""
    payments, receipts = list(payments), list(receipts)
    allocations, refunds = list(allocations), list(refunds)
    snapshot = dict(scope=scope, invoice_amount=invoice_amount,
                    opening_paid=opening_paid, payments=payments, receipts=receipts)
    before = refund_projection(**snapshot, allocations=allocations, refunds=refunds)
    _require(isinstance(refund, Refund) and refund.reversed is False)
    net = {row.id: row for row in _net_payments(scope, payments, refunds + [refund])}
    # Validate the proposed refund before interpreting its release instructions.
    source = {row.id: row for row in _net_payments(scope, payments, refunds)}
    _require(refund.payment_id in source and not source[refund.payment_id].reversed)
    pairs = {}
    for row in _rows(allocations, scope, Allocation).values():
        key = (row.payment_id, row.receipt_id)
        _require(key not in pairs)
        pairs[key] = _money(row.amount, positive=True)
    reductions = {}
    for release in releases:
        _require(isinstance(release, Release))
        _id(release.receipt_id)
        _require(release.receipt_id not in reductions)
        amount = _money(release.amount, positive=True)
        key = (refund.payment_id, release.receipt_id)
        _require(key in pairs and amount <= pairs[key])
        reductions[release.receipt_id] = amount
    free = _money(unallocated_amount)
    covered = sum((amount for (payment_id, _), amount in pairs.items()
                   if payment_id == refund.payment_id), Decimal(0))
    _require(free <= _money(source[refund.payment_id].amount) - covered)
    _require(free + sum(reductions.values(), Decimal(0)) == _money(refund.amount, positive=True))
    updated = []
    for row in allocations:
        amount = _money(row.amount) - (reductions.get(row.receipt_id, Decimal(0))
                                      if row.payment_id == refund.payment_id else Decimal(0))
        if amount > 0 and row.payment_id in net and not net[row.payment_id].reversed:
            updated.append(replace(row, amount=format(amount, '.2f')))
    after = refund_projection(**snapshot, allocations=updated, refunds=refunds + [refund])
    return dict(before=before, after=after,
                refundId=refund.id, paymentId=refund.payment_id,
                amount=format(_money(refund.amount), '.2f'),
                unallocatedAmount=format(free, '.2f'),
                releases=[dict(receiptId=key, amount=format(value, '.2f'))
                          for key, value in sorted(reductions.items())],
                rows=[dict(paymentId=row.payment_id, receiptId=row.receipt_id, amount=row.amount)
                      for row in updated])
