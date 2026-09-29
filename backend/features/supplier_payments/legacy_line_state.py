"""State gate for the one-time review of an existing invoice's lines."""


def legacy_line_review_allowed(invoice, used):
    return (
        used is False
        and invoice.get('status') in ('На утверждении', 'Утверждён')
        and invoice.get('paid_amount') == 0
        and invoice.get('warehouse_invoice_id') is None
    )
