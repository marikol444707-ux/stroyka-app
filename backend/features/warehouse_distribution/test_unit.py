from decimal import Decimal
from uuid import uuid4

from unittest import TestCase
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from .models import DistributionInput, payload_hash, validate_source
from .routes import register_warehouse_distribution_module


def payload():
    return dict(companyId=2, requestId=str(uuid4()), reason='issue',
                rows=[dict(lotId=1, projectId=3, quantity='1.000001')])


def source():
    lot = dict(material_name='Cement', unit='кг', received_quantity=Decimal('10'),
               available_quantity=Decimal('10'), document_quantity=Decimal('10'), document_unit='кг',
               invoice_line_index=0, warehouse_target='main', warehouse_location='Основной склад', status='active')
    receipt = dict(items=[dict(name='Cement', quantity=10, unit='кг')],
                   status='Принята', project='', location='Основной склад')
    return lot, receipt


class ContractTests(TestCase):
    def test_ids_are_strict(self):
        for key in ('companyId', 'lotId', 'projectId'):
            for value in (True, '2', 2.0, 0, -1, 2147483648):
                with self.subTest(key=key, value=value):
                    data = payload()
                    (data if key == 'companyId' else data['rows'][0])[key] = value
                    with self.assertRaises(ValidationError):
                        DistributionInput(**data)

    def test_quantity_bounds(self):
        for value in ('NaN', 'Infinity', '0', '-1', '100000000', '100000001', '0.0000001', True):
            with self.subTest(value=value):
                data = payload()
                data['rows'][0]['quantity'] = value
                with self.assertRaises(ValidationError):
                    DistributionInput(**data)

    def test_bounded_rows_and_reason(self):
        for update in (dict(rows=[]), dict(rows=payload()['rows'] * 51), dict(reason=' '),
                       dict(reason='x' * 1001), dict(requestId='not-a-uuid'), dict(extra='forbidden')):
            with self.subTest(update=update):
                with self.assertRaises(ValidationError):
                    DistributionInput(**{**payload(), **update})

    def test_hash_canonicalizes_decimals_but_includes_operation_target(self):
        data = payload()
        data['rows'][0]['quantity'] = '1.0'
        first = DistributionInput(**data)
        data['rows'][0]['quantity'] = '1.000000'
        second = DistributionInput(**data)
        self.assertEqual(payload_hash(first, 'issue'), payload_hash(second, 'issue'))
        self.assertNotEqual(payload_hash(first, 'issue'), payload_hash(first, 'return:1'))
        self.assertNotEqual(payload_hash(first, 'return:1'), payload_hash(first, 'return:2'))

    def test_default_off_precedes_auth_and_database(self):
        def forbidden():
            raise AssertionError('must not open DB or authenticate')
        app = FastAPI()
        register_warehouse_distribution_module(app, {'get_db': forbidden, 'get_current_user': forbidden})
        for flag in ('', 'true', '0'):
            with patch.dict('os.environ', {'WAREHOUSE_DISTRIBUTION_ENABLED': flag}), TestClient(app) as client:
                for method, path in [('get', ''), ('get', '/sources'), ('post', ''), ('post', '/1/returns')]:
                    self.assertEqual(getattr(client, method)('/warehouse-distributions' + path).status_code, 404)

    def test_source_requires_exact_normalized_evidence(self):
        from fastapi import HTTPException
        lot, receipt = source()
        validate_source(lot, receipt)
        receipt['items'][0]['quantity'] = 11
        with self.assertRaises(HTTPException) as error:
            validate_source(lot, receipt)
        self.assertEqual(error.exception.status_code, 409)

    def test_invalid_receipt_evidence(self):
        from fastapi import HTTPException
        changes = [dict(document_unit='меш', document_quantity=Decimal('1')),
                   dict(status='cancelled'), dict(warehouse_target='object'),
                   dict(invoice_line_index=-1), dict(available_quantity=Decimal('11'))]
        for change in changes:
            with self.subTest(change=change):
                lot, receipt = source()
                lot.update(change)
                with self.assertRaises(HTTPException):
                    validate_source(lot, receipt)

    def test_annulled_or_other_location_receipt(self):
        from fastapi import HTTPException
        for change in (dict(status='Аннулирована'), dict(project='Other'), dict(items=[])):
            lot, receipt = source()
            receipt.update(change)
            with self.assertRaises(HTTPException):
                validate_source(lot, receipt)
