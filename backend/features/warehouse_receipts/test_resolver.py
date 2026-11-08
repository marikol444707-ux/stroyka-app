import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, HTTPException

from backend.features.warehouse_receipts.resolver import (
    resolve_receipt, register_warehouse_receipt_resolver,
)


class Cursor:
    def __init__(self, *, owner=None, lines=None, batches=None, receipts=None, standalone=None, source=None,
                 contract=None, payment_sources=None, hidden_peers=None):
        self.owner = owner if owner is not None else {'company_id': 2, 'project_id': None}
        self.lines = lines or []
        self.batches = batches or []
        self.receipts = receipts or []
        self.standalone = standalone or []
        self.source = source
        self.contract = contract
        self.payment_sources = payment_sources or []
        self.hidden_peers = hidden_peers or []
        self.calls = []
        self.result = []
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if 'FROM file_ownership' in sql:
            self.result = [self.owner] if self.owner else []
        elif 'si.invoice_number,si.invoice_date' in sql:
            self.result = self.payment_sources
        elif 'SELECT d.id,d.waybill_number,d.waybill_date FROM supply_deliveries d' in sql:
            self.result = self.hidden_peers
        elif 'FROM supply_deliveries d JOIN' in sql:
            self.result = self.lines
        elif 'FROM supplier_shipment_batches' in sql:
            self.result = self.batches
        elif 'FROM warehouse_invoices wi' in sql:
            self.result = self.standalone
        elif 'FROM supplier_invoices si JOIN' in sql:
            self.result = [self.source] if self.source else []
        elif 'FROM supplier_contract_versions' in sql:
            self.result = [self.contract] if self.contract else []
        elif 'FROM warehouse_invoices' in sql:
            self.result = self.receipts
        else:
            self.result = []

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result

    def close(self):
        self.closed = True


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'companyId': 2, 'company_id': 2, 'role': 'кладовщик'}
        self.deps = {
            'resolve_work_company_context': Mock(return_value={'mode': 'company', 'companyId': 2}),
            'effective_company_actors': Mock(return_value=[self.actor]),
            'warehouse_roles': ('директор', 'кладовщик'),
            'fulfilment_visibility': Mock(return_value=(
                'd.company_id=%s AND d.project=ANY(%s) AND d.work_package=ANY(%s)',
                [2, ['School'], ['Main']])),
            'require_project_or_warehouse_access': Mock(),
        }
        self.document = {'documentType': 'waybill', 'waybillNumber': 'A-12',
                         'waybillDate': '2026-10-17', 'supplierInn': '1234567890',
                         'buyerInn': '9876543210',
                         'lines': [{'materialName': 'Brick', 'unit': 'шт', 'quantity': 10}]}
        self.data = {'document': self.document, 'originalUrls': ['/tenant-files/77/content']}
        self.line = {'id': 31, 'companyId': 2, 'supplierId': 7, 'offerId': 8, 'requestId': 9,
                     'sourceInvoiceValid': True, 'project': 'School', 'materialName': 'Brick', 'unit': 'шт',
                     'shippedQuantity': 10, 'receivedQuantity': 0, 'receivedAt': None,
                     'qualityStatus': None, 'status': 'В пути', 'waybillNumber': 'A-12',
                     'waybillDate': '2026-10-17'}
        self.batch = {'id': 4, 'company_id': 2, 'offer_id': 8, 'delivery_ids': [31]}
        self.passport = {'companyId': 2, 'supplierId': 7, 'reviewRequired': False,
                         'buyer': {'companyId': 2, 'inn': '9876543210'},
                         'supplier': {'supplierId': 7, 'inn': '1234567890'}}

    def resolve(self, cur, data=None):
        return resolve_receipt(cur, data or self.data, {'id': 1},
                               {'x_company_id': '2', 'x_company_mode': 'company'}, self.deps)

    def test_exact_scope_and_complete_batch(self):
        cur = Cursor(lines=[self.line], batches=[self.batch])
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: self.passport}) as loader:
            result = self.resolve(cur)
        self.assertEqual(result['status'], 'match')
        self.assertFalse(result['postingAllowed'])
        self.assertEqual(result['matchedBatch']['lines'][0]['id'], 31)
        loader.assert_called_once_with(cur, [31], strict=True)
        sql, params = next(call for call in cur.calls if 'FROM supply_deliveries d JOIN' in call[0])
        self.assertIn('d.company_id=%s AND (', sql)
        self.assertIn('d.project=ANY(%s)', sql)
        self.assertIn('d.work_package=ANY(%s)', sql)
        self.assertEqual(params, [2, 2, ['School'], ['Main']])
        self.assertTrue(all(sql.lstrip().startswith('SELECT') for sql, _ in cur.calls))

    def test_inaccessible_batch_line_never_disclosed(self):
        batch = {**self.batch, 'delivery_ids': [31, 99999]}
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections') as loader:
            result = self.resolve(Cursor(lines=[self.line], batches=[batch]))
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('99999', str(result))
        self.assertNotIn('matchedBatch', result)
        loader.assert_not_called()

    def test_legacy_no_batch_requires_review(self):
        self.assertEqual(self.resolve(Cursor(lines=[self.line]))['status'], 'review')

    def test_missing_snapshot_never_matches(self):
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: {'reviewRequired': True}}):
            self.assertEqual(self.resolve(Cursor(lines=[self.line], batches=[self.batch]))['status'], 'review')

    def test_rejected_effective_role_even_if_account_director(self):
        self.actor['role'] = 'главный_инженер'
        cur = Cursor()
        with self.assertRaises(HTTPException) as caught:
            self.resolve(cur)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(cur.calls, [])

    def test_aggregate_company_rejected(self):
        self.deps['resolve_work_company_context'].return_value = {'mode': 'all_companies'}
        with self.assertRaises(HTTPException) as caught:
            self.resolve(Cursor())
        self.assertEqual(caught.exception.status_code, 409)

    def test_cross_company_original_rejected_before_delivery_lookup(self):
        cur = Cursor(owner={'company_id': 3, 'project_id': None})
        with self.assertRaises(HTTPException) as caught:
            self.resolve(cur)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertFalse(any('FROM supply_deliveries' in sql for sql, _ in cur.calls))

    def test_ocr_company_is_only_assertion(self):
        self.document['companyId'] = 3
        with self.assertRaises(HTTPException) as caught:
            self.resolve(Cursor())
        self.assertEqual(caught.exception.status_code, 409)

    def test_original_required_and_untrusted_url_rejected(self):
        for urls in ([], ['https://other.test/invoice.pdf']):
            with self.subTest(urls=urls), self.assertRaises(HTTPException):
                self.resolve(Cursor(), {**self.data, 'originalUrls': urls})

    def test_source_invoice_filter_has_full_chain_and_status(self):
        cur = Cursor()
        result = self.resolve(cur, {**self.data, 'sourceSupplierInvoiceId': 6})
        self.assertEqual(result['status'], 'review')
        sql, params = next(call for call in cur.calls if 'FROM supply_deliveries d JOIN' in call[0])
        for fragment in ('si.company_id=d.company_id', 'si.supplier_id=d.supplier_id',
                         'si.offer_id=d.offer_id', 'si.request_id=d.request_id',
                         'source_supplier_invoice_id', 'contract_version_id', "si.status IS DISTINCT FROM 'Аннулирован'"):
            self.assertIn(fragment, sql)
        # Search all same-document peers before narrowing to the selected invoice;
        # an already received other source must not be hidden by the filter.
        self.assertEqual(params, [2, 2, ['School'], ['Main']])

    def test_unrelated_legacy_does_not_block_current_batch(self):
        unrelated = {**self.line, 'id': 66, 'waybillNumber': 'OLD', 'sourceInvoiceValid': False}
        cur = Cursor(lines=[unrelated, self.line], batches=[self.batch])
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: self.passport}):
            result = self.resolve(cur)
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['originalUrls'], self.data['originalUrls'])

    def two_batches(self):
        return [self.line, {**self.line, 'id': 32}], [self.batch, {**self.batch, 'id': 5, 'delivery_ids': [32]}]

    def test_ambiguous_response_exposes_only_complete_frozen_header_eligible_batches(self):
        lines, batches = self.two_batches()
        lines.append({**self.line, 'id': 33, 'supplierId': 99})
        batches.append({**self.batch, 'id': 6, 'delivery_ids': [33]})
        foreign = {**self.passport, 'supplierId': 99,
                   'supplier': {'supplierId': 99, 'inn': '1111111111'}}
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: self.passport, 32: self.passport, 33: foreign}):
            result = self.resolve(Cursor(lines=lines, batches=batches))
        self.assertEqual(result['status'], 'ambiguous')
        self.assertEqual([b['id'] for b in result['candidateBatches']], [4, 5])
        self.assertTrue(all(b['companyId'] == 2 and b['project'] == 'School' for b in result['candidateBatches']))
        self.assertNotIn('candidateBatchIds', result)
        self.assertNotIn('1111111111', str(result))
        self.assertFalse(result['postingAllowed'])

    def test_selected_candidate_is_revalidated_with_full_document(self):
        lines, batches = self.two_batches()
        selected = {**self.data, 'selectedBatchId': 5, 'explicitSelectionConfirmed': True}
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: self.passport, 32: self.passport}):
            result = self.resolve(Cursor(lines=lines, batches=batches), selected)
            self.assertEqual(result['matchedBatch']['id'], 5)
            for change in ({'selectedBatchId': 999}, {'explicitSelectionConfirmed': 'true'},
                           {'sourceSupplierInvoiceId': 71},
                           {'document': {**self.document, 'lines': [{'materialName': 'Brick', 'unit': 'шт', 'quantity': 9}]}}):
                with self.subTest(change=change):
                    result = self.resolve(Cursor(lines=lines, batches=batches), {**selected, **change})
                    self.assertEqual(result['status'], 'review')
                    self.assertNotIn('matchedBatch', result)
                    self.assertNotIn('candidateBatches', result)

    def test_source_filter_cannot_hide_another_received_batch(self):
        lines, batches = self.two_batches()
        lines[0] = {**lines[0], 'sourceSupplierInvoiceId': 70, 'receivedQuantity': 10, 'status': 'Принято'}
        lines[1] = {**lines[1], 'sourceSupplierInvoiceId': 71}
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: {**self.passport, 'sourceInvoiceId': 70},
                                 32: {**self.passport, 'sourceInvoiceId': 71}}):
            result = self.resolve(Cursor(lines=lines, batches=batches), {**self.data,
                'selectedBatchId': 5, 'explicitSelectionConfirmed': True, 'sourceSupplierInvoiceId': 71})
        self.assertEqual(result['reasons'], ['another_batch_already_received'])
        self.assertNotIn('matchedBatch', result)

    def test_hidden_company_peer_conflict_is_generic_and_ignores_visibility_and_source(self):
        hidden = {'id': 99999, 'waybill_number': 'A-12', 'waybill_date': '2026-10-17'}
        for passport in (self.passport, {'reviewRequired': True}):
            cur = Cursor(lines=[self.line], batches=[self.batch], hidden_peers=[hidden])
            with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                       return_value={31: self.passport, 99999: passport}):
                result = self.resolve(cur)
            self.assertEqual(result['status'], 'review')
            self.assertNotIn('99999', str(result))
            self.assertNotIn('matchedBatch', result)
            sql, values = next(call for call in cur.calls if 'SELECT d.id,d.waybill_number' in call[0])
            self.assertIn('d.company_id=%s', sql)
            self.assertNotIn('d.project', sql)
            self.assertNotIn('d.work_package', sql)
            self.assertNotIn('source_supplier_invoice_id', sql)
            self.assertEqual(values[0], 2)
            self.assertEqual(values[-1], [31])

    def test_other_frozen_supplier_peer_does_not_block(self):
        hidden = {'id': 99999, 'waybill_number': 'A-12', 'waybill_date': '2026-10-17'}
        other = {**self.passport, 'supplier': {'supplierId': 99, 'inn': '1111111111'}}
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: self.passport, 99999: other}):
            result = self.resolve(Cursor(lines=[self.line], batches=[self.batch], hidden_peers=[hidden]))
        self.assertEqual(result['status'], 'match')

    def test_hidden_peer_uses_same_unicode_number_canonicalization_as_matcher(self):
        for incoming, saved in (('Е1', 'Ё-1'), ('A12', 'Ａ-12')):
            hidden = {'id': 99999, 'waybill_number': saved, 'waybill_date': '2026-10-17'}
            data = {**self.data, 'document': {**self.document, 'waybillNumber': incoming}}
            cur = Cursor(lines=[{**self.line, 'waybillNumber': incoming}], batches=[self.batch], hidden_peers=[hidden])
            with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                       return_value={31: self.passport, 99999: self.passport}):
                result = self.resolve(cur, data)
            self.assertEqual(result['status'], 'review')
            sql, params = next(call for call in cur.calls if 'SELECT d.id,d.waybill_number' in call[0])
            # PostgreSQL upper/regex cannot implement NFKC/Ё canonicalization;
            # no approximate SQL filter may remove peers before the Python check.
            self.assertNotIn('regexp_replace', sql)
            self.assertNotIn('upper(', sql)
            self.assertEqual(params, (2, '2026-10-17', [31]))

    def test_hidden_peer_missing_projection_fails_closed_without_leaking_error(self):
        hidden = {'id': 99999, 'waybill_number': 'A-12', 'waybill_date': '2026-10-17'}
        def projections(_cur, ids, strict):
            if ids == [99999]:
                raise HTTPException(409, 'Internal hidden receipt details')
            return {31: self.passport}
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   side_effect=projections):
            result = self.resolve(Cursor(lines=[self.line], batches=[self.batch], hidden_peers=[hidden]))
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('Internal', str(result))
        self.assertNotIn('99999', str(result))

    def test_hidden_unreceived_shipment_blocks_standalone_admission(self):
        hidden = {'id': 99999, 'waybill_number': 'A-12', 'waybill_date': '2026-10-17'}
        cur = Cursor(hidden_peers=[hidden])
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={99999: self.passport}):
            result = self.resolve(cur)
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('99999', str(result))
        sql = next(sql for sql, _ in cur.calls if 'SELECT d.id,d.waybill_number' in sql)
        self.assertNotIn('received_quantity', sql)

    def test_invalid_saved_invoice_requires_review_without_client_filter(self):
        cur = Cursor(lines=[{**self.line, 'sourceInvoiceValid': False}], batches=[self.batch])
        result = self.resolve(cur)
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('matchedBatch', result)

    def standalone(self, **changes):
        return {'id': 81, 'company_id': 2, 'supplier_id': 7, 'supplier_invoice_id': 71,
                'number': 'A-12', 'date': '2026-10-17', 'project': 'School',
                'items': json.dumps([{'name': 'Brick', 'quantity': 10, 'unit': 'шт',
                                      'workPackage': 'Main'}]), **changes}

    def source(self):
        from backend.features.supplier_access.offer_party_snapshot import build_offer_party_snapshot
        return {'id': 71, 'offer_id': 8, 'request_id': 9, 'contract_version_id': None,
                'party_snapshot_json': build_offer_party_snapshot(
                    offer_id=8, request_id=9, company_id=2, supplier_id=7,
                    buyer={'fullName': 'Saved Buyer', 'inn': '9876543210'},
                    supplier={'fullName': 'Saved Supplier', 'inn': '1234567890'},
                    actor={'id': 10}, frozen_at='2026-10-17T10:00:00Z')}

    def test_standalone_existing_has_receipts_and_no_shipment(self):
        cur = Cursor(standalone=[self.standalone()], source=self.source())
        result = self.resolve(cur)
        self.assertEqual(result['status'], 'existing_receipt')
        self.assertEqual(result['warehouseInvoiceIds'], [81])
        self.assertEqual(result['receipts'][0]['lines'][0]['quantity'], 10)
        self.assertNotIn('matchedBatch', result)
        self.assertNotIn('lineIds', result)
        self.assertFalse(result['postingAllowed'])
        self.assertTrue(all(sql.lstrip().startswith('SELECT') for sql, _ in cur.calls))

    def test_standalone_query_requires_whole_company_project_package_scope(self):
        cur = Cursor()
        self.resolve(cur, {**self.data, 'project': 'School'})
        sql, params = next(call for call in cur.calls if 'FROM warehouse_invoices wi' in call[0])
        for fragment in ('wi.company_id=%s', 'wi.project=%s', 'AND NOT EXISTS',
                         'jsonb_array_elements', 'd.project=ANY(%s)', 'd.work_package=ANY(%s)',
                         'WHERE NOT COALESCE', 'wi.supply_delivery_id IS NULL'):
            self.assertIn(fragment, sql)
        self.assertEqual(params, [2, 'School', 2, ['School'], ['Main']])

    def test_standalone_wrong_company_header_or_project_is_not_exposed(self):
        for changed in ({'company_id': 3}, {'date': '2026-10-16'}, {'number': 'A-13'},
                        {'project': 'Private'}):
            with self.subTest(changed=changed):
                result = self.resolve(Cursor(standalone=[self.standalone(**changed)], source=self.source()),
                                      {**self.data, 'project': 'School'})
                self.assertEqual(result['status'], 'review' if changed.get('project') == 'Private' else 'no_match')
                self.assertNotIn('warehouseInvoiceIds', result)

    def test_standalone_missing_legal_proof_requires_review_without_ids(self):
        for source, changes in ((None, {}), (self.source(), {'supplier_invoice_id': None}),
                                ({**self.source(), 'party_snapshot_json': {}}, {})):
            with self.subTest(source=source):
                result = self.resolve(Cursor(standalone=[self.standalone(**changes)], source=source))
                self.assertEqual(result['status'], 'review')
                self.assertNotIn('warehouseInvoiceIds', result)
                self.assertIn('existing_receipt_missing_frozen_legal_identity', result['reasons'])

    def test_standalone_frozen_party_mismatch_never_uses_names(self):
        source = self.source()
        source['party_snapshot_json']['buyer']['inn'] = '1111111111'
        result = self.resolve(Cursor(standalone=[self.standalone()], source=source))
        self.assertEqual(result['status'], 'no_match')

    def test_standalone_ambiguous_before_line_disambiguation(self):
        result = self.resolve(Cursor(standalone=[self.standalone(), self.standalone(id=82, items='[]')],
                                     source=self.source()))
        self.assertEqual(result['status'], 'ambiguous')
        self.assertNotIn('warehouseInvoiceIds', result)

    def test_standalone_contract_proof_and_tamper(self):
        snapshot = {'buyer': {'companyId': 2, 'inn': '9876543210'},
                    'supplier': {'supplierId': 7, 'inn': '1234567890'}}
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                          separators=(',', ':')).encode()).hexdigest()
        for tamper in (False, True):
            with self.subTest(tamper=tamper):
                cur = Cursor(standalone=[self.standalone()],
                    source={**self.source(), 'contract_version_id': 6},
                    contract={'snapshot_json': snapshot, 'snapshot_hash': '0' * 64 if tamper else digest})
                result = self.resolve(cur)
                self.assertEqual(result['status'], 'review' if tamper else 'existing_receipt')
                sql, params = next(call for call in cur.calls if 'FROM supplier_contract_versions' in call[0])
                self.assertIn('company_id=%s AND offer_id=%s', sql)
                self.assertEqual(params, (6, 2, 8))

    def test_standalone_complete_lines_units_and_quantity_required(self):
        for items in ([{'name': 'Brick', 'quantity': 9, 'unit': 'шт'}],
                      [{'name': 'Brick', 'quantity': 10, 'unit': 'kg'}],
                      [{'name': 'Other', 'quantity': 10, 'unit': 'шт'}],
                      [{'name': 'Brick', 'quantity': 10, 'unit': 'шт'}] * 2,
                      [], 'broken'):
            with self.subTest(items=items):
                result = self.resolve(Cursor(standalone=[self.standalone(items=items)], source=self.source()))
                self.assertEqual(result['status'], 'review')
                self.assertNotIn('warehouseInvoiceIds', result)

    def test_existing_standalone_shortage_blocks_matching_shipment_without_exposing_receipt(self):
        cur = Cursor(lines=[self.line], batches=[self.batch],
                     standalone=[self.standalone(project='Private', items=[{'name': 'Brick', 'unit': 'шт', 'quantity': 4}])],
                     source=self.source())
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: self.passport}):
            result = self.resolve(cur, {**self.data, 'project': 'School'})
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('warehouseInvoiceIds', result)
        self.assertNotIn('matchedBatch', result)
        self.assertNotIn('Private', str(result))

    def payment_fixture(self):
        document = {'documentType': 'payment_invoice', 'invoiceNumber': 'INV-99',
                    'invoiceDate': '2026-10-15', 'supplierInn': '1234567890', 'buyerInn': '9876543210'}
        source = {**self.source(), 'company_id': 2, 'supplier_id': 7, 'invoice_number': 'INV/99',
                  'invoice_date': '2026-10-15', 'status': 'Оплачен', 'project': 'School', 'contract_version_id': 6}
        snapshot = {'buyer': {'companyId': 2, 'inn': '9876543210'},
                    'supplier': {'supplierId': 7, 'inn': '1234567890'}}
        contract = {'snapshot_json': snapshot, 'snapshot_hash': hashlib.sha256(json.dumps(
            snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()}
        line = {**self.line, 'sourceSupplierInvoiceId': 71}
        passport = {**self.passport, 'sourceInvoiceId': 71}
        return {**self.data, 'document': document}, source, contract, line, passport

    def test_payment_invoice_discovers_real_sources_and_requires_an_actual_waybill(self):
        data, source, contract, line, passport = self.payment_fixture()
        cur = Cursor(lines=[line], batches=[self.batch], payment_sources=[source], contract=contract)
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: passport}):
            result = self.resolve(cur, {**data, 'selectedBatchId': 4, 'explicitSelectionConfirmed': True})
        self.assertEqual(result['status'], 'source_selection')
        self.assertTrue(result['requiresWaybill'])
        self.assertFalse(result['postingAllowed'])
        self.assertNotIn('matchedBatch', result)
        choice = result['candidateBatches'][0]
        self.assertEqual(choice['sourceSupplierInvoiceId'], 71)
        self.assertEqual(choice['companyId'], 2)
        self.assertEqual(choice['sourceInvoice']['invoiceNumber'], 'INV/99')
        self.assertEqual(choice['waybillNumber'], 'A-12')
        self.assertEqual(choice['waybillDate'], '2026-10-17')
        sql, params = next(call for call in cur.calls if 'si.invoice_number,si.invoice_date' in call[0])
        for fragment in ('si.company_id=%s', 'si.invoice_date=%s', 'si.invoice_number',
                         'si.supplier_id', 'o.party_snapshot_json', 'source_supplier_invoice_id',
                         'd.project=ANY(%s)', 'd.work_package=ANY(%s)'):
            self.assertIn(fragment, sql)
        self.assertNotIn('JOIN companies', sql)
        self.assertNotIn('JOIN suppliers', sql)
        self.assertEqual(params[:2], [2, '2026-10-15'])
        self.assertTrue(all(sql.lstrip().startswith('SELECT') for sql, _ in cur.calls))

    def test_payment_invoice_identity_never_falls_back_to_waybill_or_offer(self):
        data, source, contract, line, passport = self.payment_fixture()
        for changes in ({'invoiceNumber': None, 'waybillNumber': 'INV-99'},
                        {'invoiceDate': None, 'waybillDate': '2026-10-15'},
                        {'supplierInn': ''}, {'buyerInn': ''}):
            cur = Cursor(payment_sources=[source])
            result = self.resolve(cur, {**data, 'document': {**data['document'], **changes}})
            self.assertEqual(result['status'], 'review')
            self.assertNotIn('candidateBatches', result)
            self.assertFalse(any('FROM supply_deliveries d JOIN' in sql for sql, _ in cur.calls))
        # A shipment from the same offer without the exact immutable invoice link
        # is deliberately not returned as a source choice.
        result = self.resolve(Cursor(lines=[self.line], batches=[self.batch], payment_sources=[source],
                                     contract=contract), data)
        self.assertEqual(result['status'], 'review')
        self.assertNotIn('candidateBatches', result)

    def test_payment_source_wrong_scope_header_and_frozen_parties_never_exposed(self):
        data, source, contract, line, passport = self.payment_fixture()
        for changes in ({'company_id': 3}, {'invoice_number': 'INV-98'}, {'invoice_date': '2026-10-16'},
                        {'status': 'Аннулирован'}):
            with self.subTest(changes=changes):
                result = self.resolve(Cursor(payment_sources=[{**source, **changes}], contract=contract), data)
                self.assertEqual(result['status'], 'no_match')
                self.assertNotIn('candidateBatches', result)
        for document in ({**data['document'], 'supplierInn': '1111111111'},
                         {**data['document'], 'buyerInn': '1111111111'}):
            result = self.resolve(Cursor(payment_sources=[source], contract=contract), {**data, 'document': document})
            self.assertEqual(result['status'], 'no_match')
        for proof in (None, {**contract, 'snapshot_hash': '0' * 64}):
            result = self.resolve(Cursor(payment_sources=[source], contract=proof), data)
            self.assertEqual(result['status'], 'review')
            self.assertNotIn('candidateBatches', result)

    def test_payment_source_uses_unicode_canonicalization_without_approximate_sql_filter(self):
        data, source, contract, line, passport = self.payment_fixture()
        for incoming, saved in (('Е1', 'Ё-1'), ('A12', 'Ａ-12')):
            cur = Cursor(lines=[line], batches=[self.batch], payment_sources=[{**source, 'invoice_number': saved}], contract=contract)
            with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                       return_value={31: passport}):
                result = self.resolve(cur, {**data, 'document': {**data['document'], 'invoiceNumber': incoming}})
            self.assertEqual(result['status'], 'source_selection')
            sql = next(sql for sql, _ in cur.calls if 'si.invoice_number,si.invoice_date' in sql)
            self.assertNotIn('regexp_replace', sql)

    def test_payment_source_hidden_or_partial_batch_never_disclosed(self):
        data, source, contract, line, passport = self.payment_fixture()
        for batch in ({**self.batch, 'delivery_ids': [31, 99999]}, {**self.batch, 'company_id': 3}):
            with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections') as loader:
                result = self.resolve(Cursor(lines=[line], batches=[batch], payment_sources=[source], contract=contract), data)
            self.assertEqual(result['status'], 'review')
            self.assertNotIn('candidateBatches', result)
            self.assertNotIn('99999', str(result))
            loader.assert_not_called()

    def test_payment_source_selected_invoice_is_exact_and_fully_scoped(self):
        data, source, contract, line, passport = self.payment_fixture()
        cur = Cursor(lines=[line], batches=[self.batch], payment_sources=[source], contract=contract)
        with patch('backend.features.warehouse_receipts.resolver.load_delivery_document_projections',
                   return_value={31: passport}):
            result = self.resolve(cur, {**data, 'sourceSupplierInvoiceId': 71, 'project': 'School'})
        self.assertEqual(result['status'], 'source_selection')
        sql, params = next(call for call in cur.calls if 'si.invoice_number,si.invoice_date' in call[0])
        self.assertIn('AND si.id=%s', sql)
        self.assertIn('AND r.project=%s', sql)
        self.assertEqual(params[-2:], ['School', 71])
        result = self.resolve(Cursor(payment_sources=[source], contract=contract), {**data, 'sourceSupplierInvoiceId': 999})
        self.assertEqual(result['status'], 'no_match')

    def test_route_readonly_and_cleanup_on_success_and_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                cur = Cursor()
                conn = Mock()
                conn.cursor.return_value = cur
                app = FastAPI()
                deps = {**self.deps, 'get_db': lambda: conn, 'get_current_user': lambda: {}}
                register_warehouse_receipt_resolver(app, deps)
                endpoint = next(r.endpoint for r in app.routes if r.path == '/warehouse-receipts/resolve')
                with patch('backend.features.warehouse_receipts.resolver.resolve_receipt',
                           side_effect=HTTPException(403, 'blocked') if failure else None,
                           return_value={'status': 'no_match', 'postingAllowed': False}):
                    if failure:
                        with self.assertRaises(HTTPException):
                            endpoint(self.data, {}, '2', 'company')
                    else:
                        endpoint(self.data, {}, '2', 'company')
                self.assertEqual(cur.calls[0][0], 'SET TRANSACTION READ ONLY')
                self.assertIn('statement_timeout', cur.calls[1][0])
                conn.commit.assert_not_called()
                conn.rollback.assert_called_once()
                conn.close.assert_called_once()
                self.assertTrue(cur.closed)


if __name__ == '__main__':
    unittest.main()
