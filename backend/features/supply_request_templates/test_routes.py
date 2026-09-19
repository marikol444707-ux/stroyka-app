"""Boundary validation and authenticated legacy guard; SQL policy is exercised in PG."""
import unittest
from fastapi import FastAPI, HTTPException
from backend.features.supply_request_templates.routes import register_supply_request_templates_module
from backend.features.supply_request_templates.service import validate


class SupplyRequestTemplatesValidationTest(unittest.TestCase):
    def payload(self, **changes):
        return {'name': '  Начальный   набор ', 'category': ' Стены ', 'items': [
            {'materialName': ' Цемент ', 'quantity': '1.000001', 'unit': ' кг ', 'workPackage': ' Основная '}], **changes}

    def test_normalizes_text_and_preserves_valid_fractional_quantity(self):
        name, category, items = validate(self.payload())
        self.assertEqual((name, category), ('Начальный набор', 'Стены'))
        self.assertEqual(items, [{'materialName': 'Цемент', 'quantity': 1.000001, 'unit': 'кг', 'workPackage': 'Основная'}])

    def test_invalid_row_rejects_whole_template_instead_of_dropping_material(self):
        payload = self.payload()
        payload['items'].append({'materialName': '', 'quantity': 3, 'unit': 'шт'})
        with self.assertRaises(HTTPException) as caught:
            validate(payload)
        self.assertEqual(caught.exception.status_code, 400)

    def test_malformed_fields_and_author_spoofing_are_rejected(self):
        for changes in ({'name': None}, {'name': 123}, {'category': []}, {'createdById': 1}, {'companyId': 2},
                        {'items': []}, {'items': {}}, {'items': [None]}, {'items': [True]}):
            with self.subTest(changes=changes), self.assertRaises(HTTPException) as caught:
                validate(self.payload(**changes))
            self.assertEqual(caught.exception.status_code, 400)

    def test_quantities_must_be_positive_finite_and_exact_to_six_places(self):
        for value in (None, True, [], {}, 'NaN', 'Infinity', '-Infinity', 0, -1, '0.0000001', 100000000):
            payload = self.payload()
            payload['items'][0]['quantity'] = value
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                validate(payload)
            self.assertEqual(caught.exception.status_code, 400)

    def test_deleted_legacy_endpoint_stays_authenticated_and_closed(self):
        app = FastAPI()
        def auth(): return {'id': 1}
        register_supply_request_templates_module(app, {'get_current_user': auth})
        route = next(r for r in app.routes if r.path == '/supply-request-templates/{id}' and 'DELETE' in r.methods)
        self.assertEqual(route.dependant.dependencies[0].call, auth)
        with self.assertRaises(HTTPException) as caught:
            route.endpoint(user={'id': 1})
        self.assertEqual(caught.exception.status_code, 409)
