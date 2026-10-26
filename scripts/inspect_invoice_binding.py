#!/usr/bin/env python3
"""Read one operator-selected invoice and its links in the exact service runtime.

Does not import backend.main, create records, repair links, or print credentials
or document URLs. The child transaction is explicitly read-only and rolled back.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys

BASE = '57023611c6090c1bdf63a107a28eefadd1afb492'


def inspect_record(cur, invoice_id, expected_number, expected_total):
    cur.execute("""SELECT w.id,w.number,w.company_id,
            COALESCE(to_jsonb(c)->>'name','') AS company_name,
            w.supplier_id,w.supplier_name,w.supplier_invoice_id,
            to_jsonb(w)->>'accounting_status' AS accounting_status,
            w.total_with_vat,w.status,
            to_jsonb(w)->>'photo_url' AS warehouse_photo,
            to_jsonb(w)->>'photo_urls' AS warehouse_photos,
            si.id AS linked_invoice_id,si.supplier_id AS linked_supplier_id,
            si.supplier_name AS linked_supplier_name,si.warehouse_invoice_id,
            si.status AS linked_status,
            to_jsonb(si)->>'file_url' AS linked_file,
            to_jsonb(si)->>'photo_url' AS linked_photo,
            EXISTS(SELECT 1 FROM company_supplier_links l
                   WHERE l.company_id=w.company_id AND l.supplier_id=w.supplier_id) AS supplier_in_company
        FROM warehouse_invoices w
        LEFT JOIN companies c ON c.id=w.company_id
        LEFT JOIN supplier_invoices si ON si.id=w.supplier_invoice_id AND si.company_id=w.company_id
        WHERE w.id=%s""", (invoice_id,))
    row = cur.fetchone()
    if row is None:
        return {'state': 'not_found', 'invoiceId': invoice_id, 'readOnly': True}
    normalize = lambda value: re.sub(r'[^0-9a-zа-я]', '', str(value or '').lower())
    if normalize(row['number']) != normalize(expected_number) or abs(float(row['total_with_vat'] or 0)-expected_total) > .01:
        return {'state': 'candidate_does_not_match_requested_upd', 'invoiceId': invoice_id, 'readOnly': True}
    try:
        photos = json.loads(row.get('warehouse_photos') or '[]')
    except (ValueError, TypeError):
        photos = []
    linked = row.get('linked_invoice_id') is not None
    return {
        'state': 'inspected', 'readOnly': True, 'changesMade': False,
        'warehouseInvoice': {'id': row['id'], 'number': row['number'], 'total': str(row['total_with_vat']),
            'companyId': row['company_id'], 'companyName': row['company_name'],
            'supplierId': row['supplier_id'], 'supplierName': row['supplier_name'],
            'status': row['status'], 'accountingStatus': row['accounting_status'],
            'hasOriginal': bool(row.get('warehouse_photo') or (isinstance(photos, list) and photos)),
            'supplierInCompanyCatalog': bool(row['supplier_in_company'])},
        'accountingInvoice': {'id': row.get('supplier_invoice_id'), 'foundInSameCompany': linked,
            'supplierId': row.get('linked_supplier_id'), 'supplierName': row.get('linked_supplier_name'),
            'status': row.get('linked_status'),
            'backLinkMatches': linked and row.get('warehouse_invoice_id') == invoice_id,
            'hasOwnOriginal': bool(row.get('linked_file') or row.get('linked_photo'))},
    }


def child_main(arguments):
    from backend.db import get_db
    from psycopg2.extras import RealDictCursor
    connection = get_db()
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='5s'")
            result = inspect_record(cur, *arguments)
        return result
    finally:
        connection.rollback()
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', type=Path, default=Path('/var/www/stroyka-app'))
    parser.add_argument('--invoice-id', type=int, required=True)
    parser.add_argument('--expect-number', required=True)
    parser.add_argument('--expect-total', type=float, required=True)
    parser.add_argument('--runtime-child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.invoice_id <= 0 or not math.isfinite(args.expect_total) or args.expect_total < 0:
            raise ValueError('invalid_invoice')
        arguments = (args.invoice_id, args.expect_number, args.expect_total)
        if args.runtime_child:
            sys.path.insert(0, str(args.app_root.resolve()))
            print(json.dumps(child_main(arguments), ensure_ascii=False))
            return
        root = args.app_root.resolve()
        git = lambda *values: subprocess.check_output(['git', '-C', str(root), *values])
        if git('rev-parse', 'HEAD').decode().strip() != BASE:
            raise ValueError('installed_head_changed')
        helper_path = root / 'scripts/unified_release.py'
        if helper_path.is_symlink() or helper_path.read_bytes() != git('show', 'HEAD:scripts/unified_release.py'):
            raise ValueError('runtime_helper_changed')
        spec = importlib.util.spec_from_file_location('_invoice_inspection_runtime', helper_path)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        environment = helper.runtime_environment(root, 'stroyka')
        launcher = Path('/usr/local/bin/uvicorn').read_text().splitlines()[0]
        interpreter = launcher[2:].strip()
        if not launcher.startswith('#!/') or ' ' in interpreter or not Path(interpreter).is_file():
            raise ValueError('runtime_interpreter_unavailable')
        result = subprocess.run([interpreter, '-B', str(Path(__file__).resolve()), '--runtime-child',
            '--app-root', str(root),
            '--invoice-id', str(args.invoice_id), '--expect-number', args.expect_number,
            '--expect-total', str(args.expect_total)], cwd=root, env=environment,
            capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise ValueError('read_only_inspection_failed')
        output = json.loads(result.stdout)
        print(json.dumps(output, ensure_ascii=False))
    except Exception as error:
        allowed = {'invalid_invoice', 'installed_head_changed', 'runtime_helper_changed',
                   'runtime_interpreter_unavailable', 'read_only_inspection_failed'}
        code = str(error) if isinstance(error, ValueError) and str(error) in allowed else 'inspection_unavailable'
        print(json.dumps({'error': code, 'changesMade': False}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
