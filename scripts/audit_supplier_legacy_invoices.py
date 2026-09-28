#!/usr/bin/env python3
"""Operator-only, read-only inventory of invoice evidence; never grants admission.

Uses libpq PG* environment variables. Requires an explicit company, and exports
only that company's invoice IDs and evidence flags (no credentials or contacts).
"""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

# Also support direct execution from outside the repository.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.features.supplier_payments.legacy_reconciliation import reconciliation_preview
from backend.features.supplier_payments.documents import warehouse_payment_package
from fastapi import HTTPException

import psycopg2
from psycopg2.extras import RealDictCursor


def audit(connection, company_id):
    if type(company_id) is not int or company_id <= 0:
        raise ValueError('company_id must be a positive integer')
    # Own a fresh connection: never switch an active caller transaction's mode.
    if connection.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
        raise ValueError('audit requires an idle connection')
    connection.set_session(readonly=True, isolation_level='REPEATABLE READ', autocommit=False)
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute('''SELECT i.id, i.amount::text AS amount,
                i.paid_amount::text AS paid_amount, i.company_id, i.supplier_id,
                i.project_name, i.work_package, i.warehouse_invoice_id,
                EXISTS(SELECT 1 FROM supplier_invoice_line_specs s
                    WHERE s.company_id=i.company_id AND s.invoice_id=i.id) AS sealed_lines,
                EXISTS(SELECT 1 FROM supplier_payment_documents d
                    WHERE d.company_id=i.company_id AND d.document_kind='invoice'
                        AND d.document_id=i.id) AS registered,
                i.warehouse_invoice_id IS NOT NULL OR EXISTS(
                    SELECT 1 FROM warehouse_invoices w WHERE w.supplier_invoice_id=i.id
                ) AS legacy_receipt_link
                FROM supplier_invoices i WHERE i.company_id=%s ORDER BY i.id''', (company_id,))
            rows = cur.fetchall()
            cur.execute("""SELECT i.id AS root_invoice_id, w.id, w.company_id, w.supplier_id,
                w.project, w.location, w.items, w.supplier_invoice_id,
                COALESCE(NULLIF(w.total_with_vat,0),w.total_base)::text AS review_amount,
                w.paid_amount::text AS review_paid,
                EXISTS(SELECT 1 FROM supplier_payment_documents d WHERE
                    d.company_id=w.company_id AND d.document_kind='warehouse'
                    AND d.document_id=w.id) AS registered,
                EXISTS(SELECT 1 FROM supplier_invoices other WHERE
                    other.warehouse_invoice_id=w.id AND other.id<>i.id) AS other_invoice_links
                FROM supplier_invoices i JOIN warehouse_invoices w
                    ON w.id=i.warehouse_invoice_id OR w.supplier_invoice_id=i.id
                WHERE i.company_id=%s ORDER BY i.id,w.id""", (company_id,))
            groups = {}
            invalid_packages = set()
            ambiguous_groups = set()
            for warehouse in cur.fetchall():
                root = warehouse['root_invoice_id']
                if warehouse['other_invoice_links']:
                    ambiguous_groups.add(root)
                package = None
                if warehouse['company_id'] == company_id:
                    try:
                        package = warehouse_payment_package(cur, warehouse['items'])
                    except HTTPException:
                        invalid_packages.add(root)
                groups.setdefault(root, []).append(dict(id=warehouse['id'],
                    companyId=warehouse['company_id'], supplierId=warehouse['supplier_id'],
                    projectName=warehouse['project'] or warehouse['location'] or '',
                    workPackage=package, amount=warehouse['review_amount'],
                    paidAmount=warehouse['review_paid'], invoiceId=warehouse['supplier_invoice_id'],
                    registered=warehouse['registered']))
        counts = {'sealed': 0, 'requiresReconciliation': 0}
        invoices = []
        for row in rows:
            reasons = []
            if not row['sealed_lines']:
                reasons.append('missingOriginalLineEvidence')
            if row['legacy_receipt_link']:
                reasons.append('legacyReceiptLink')
            # A paid old invoice without ledger history cannot be registered by
            # the zero-opening flow; its historic payment needs reconciliation.
            try:
                paid = Decimal(row['paid_amount']) if row['paid_amount'] is not None else None
                if paid is None or not paid.is_finite() or paid < 0:
                    reasons.append('invalidOrMissingPaidAmount')
                elif paid != 0 and not row['registered']:
                    reasons.append('historicalPaymentWithoutLedger')
            except (InvalidOperation, TypeError):
                reasons.append('invalidOrMissingPaidAmount')
            preview = reconciliation_preview(dict(id=row['id'], companyId=company_id,
                supplierId=row['supplier_id'], projectName=row['project_name'],
                workPackage=row['work_package'] or '', amount=row['amount'],
                paidAmount=row['paid_amount'], warehouseId=row['warehouse_invoice_id'],
                registered=row['registered']), groups.get(row['id'], []))
            if row['id'] in invalid_packages or row['id'] in ambiguous_groups:
                preview = dict(scenario='blocked', admissionGranted=False,
                    reason='invalidReceiptPackage' if row['id'] in invalid_packages else 'ambiguousReceiptLinks')
            if preview['scenario'] == 'blocked':
                reasons.append(preview['reason'])
            category = 'requiresReconciliation' if reasons else 'sealed'
            counts[category] += 1
            invoices.append(dict(invoiceId=row['id'], amount=row['amount'],
                paidAmount=row['paid_amount'], ledgerRegistered=row['registered'],
                category=category, reasons=reasons, financialReview=preview))
        return dict(companyId=company_id, readOnly=True, admissionGranted=False,
                    counts=counts, invoices=invoices)
    finally:
        connection.rollback()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--company-id', type=int, required=True)
    args = parser.parse_args()
    if args.company_id <= 0:
        parser.error('--company-id must be positive')
    connection = psycopg2.connect('')
    try:
        print(json.dumps(audit(connection, args.company_id), ensure_ascii=False, indent=2))
    finally:
        connection.close()


if __name__ == '__main__':
    main()
