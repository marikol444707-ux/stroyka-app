"""Financial review preview only: no historical line reconstruction or writes."""
from decimal import Context, DecimalException, localcontext
from .invoice_line_spec import _number


def reconciliation_preview(invoice, warehouses):
    """Consume the complete direct/reverse group from one consistent DB snapshot.

    Caller validates warehouse item packages using the existing SQL validator.
    A matched pair represents ONE obligation, never two additive paid balances.
    This does not validate contracts, payment evidence, roles or tax allocation.
    """
    return _reconciliation_preview(invoice, warehouses, compare_package=True)


def _reconciliation_preview(invoice, warehouses, *, compare_package):
    """Shared money/link checks; mixed-package caller supplies separate evidence."""
    def blocked(reason):
        return dict(scenario='blocked', admissionGranted=False, reason=reason)

    if invoice['registered']:
        return dict(scenario='alreadyRegistered', admissionGranted=False)
    linked = invoice['warehouseId'] is not None or bool(warehouses)
    if linked:
        if len(warehouses) != 1:
            return blocked('ambiguousOrMissingReceipt')
        warehouse = warehouses[0]
        if (invoice['warehouseId'] != warehouse['id'] or
                warehouse['invoiceId'] != invoice['id']):
            return blocked('nonReciprocalReceiptLink')
        if warehouse['registered']:
            return blocked('receiptAlreadyRegistered')
        keys = ('companyId','supplierId','projectName') + (('workPackage',) if compare_package else ())
        if any(invoice[key] != warehouse[key] for key in keys):
            return blocked('receiptIdentityMismatch')
    try:
        with localcontext(Context(prec=64)):
            amount = _number(invoice['amount'], '0.01')
            paid = _number(invoice['paidAmount'], '0.01', zero=True)
            if paid > amount:
                return blocked('paidExceedsOriginalAmount')
            if linked and (amount != _number(warehouse['amount'], '0.01') or
                           paid != _number(warehouse['paidAmount'], '0.01', zero=True)):
                return blocked('receiptBalanceMismatch')
            return dict(scenario='matchedLegacyPair' if linked else 'standaloneInvoice',
                        admissionGranted=False, amount=format(amount,'.2f'),
                        openingPaid=format(paid,'.2f'), remainingAmount=format(amount-paid,'.2f'),
                        newCashAmount='0.00')
    except (ValueError, TypeError, DecimalException):
        return blocked('invalidOriginalAmounts')
