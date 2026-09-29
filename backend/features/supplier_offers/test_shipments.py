"""Batch quantities and completion are per order line, never per receipt row."""
import unittest
from fastapi import HTTPException
from backend.features.supplier_offers.shipments import order_lines, shipment_lines, flow_status, quote_lines


class ShipmentTests(unittest.TestCase):
    def setUp(self):
        self.offer = dict(material_name='Кабель', quantity=10, unit='м', work_package='Основная')
        self.lines = order_lines(self.offer)

    def test_remainder_counts_transit_and_accepted_batches(self):
        previous = [dict(material_name='Кабель', unit='м', work_package='Основная', shipped_quantity=6)]
        self.assertEqual(shipment_lines(self.lines, previous, {'shippedQuantity': 4})[0]['shippedQuantity'], 4)
        with self.assertRaises(HTTPException):
            shipment_lines(self.lines, previous, {'shippedQuantity': 5})

    def test_two_batches_do_not_double_ordered_quantity(self):
        rows = [dict(material_name='Кабель', unit='м', work_package='Основная', planned_quantity=10,
                     received_quantity=q, status='Принято') for q in (6, 4)]
        self.assertEqual(flow_status(self.lines, rows), 'Поставлено')
        self.assertEqual(flow_status(self.lines, rows[:1]), 'Частично поставлено')

    def test_invalid_quantities_and_unknown_duplicate_lines(self):
        for quantity in ('NaN', 'Infinity', -1, 0, '0.0000001'):
            with self.subTest(quantity=quantity), self.assertRaises(HTTPException):
                shipment_lines(self.lines, [], {'shippedQuantity': quantity})
        line = dict(materialName='Кабель', unit='м', workPackage='Основная', shippedQuantity=1)
        for items in ([line, line], [dict(line, unit='шт')]):
            with self.assertRaises(HTTPException):
                shipment_lines(self.lines, [], {'shippedItems': items})

    def test_partial_multiline_and_different_units(self):
        lines = order_lines(dict(items_json=[dict(materialName='Кабель', quantity=10, unit='м'),
                                           dict(materialName='Кабель', quantity=2, unit='шт')]))
        chosen = shipment_lines(lines, [], {'shippedItems': [dict(materialName='Кабель', unit='м', shippedQuantity=10)]})
        self.assertEqual(len(chosen), 1)
        self.assertEqual(flow_status(lines, [dict(material_name='Кабель', unit='м', received_quantity=12, status='Принято')]), 'Частично поставлено')

    def test_repeated_quote_lines_keep_weighted_cost(self):
        result = quote_lines([dict(materialName='Кабель',unit='м',quantity=2,pricePerUnit=10),
                              dict(materialName='Кабель',unit='м',quantity=3,pricePerUnit=20)])
        line = next(iter(result.values()))
        self.assertEqual(line['totalPrice'], 80)
        self.assertEqual(line['pricePerUnit'], 16)

    def test_historical_json_plan_uses_database_quantity_precision(self):
        lines = order_lines(dict(self.offer, quantity='1.12345'))
        self.assertEqual(flow_status(lines, [dict(material_name='Кабель',unit='м',received_quantity='1.1235',status='Принято')]), 'Поставлено')
