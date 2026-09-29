"""Invalid transfer quantities must be rejected before any database access."""
import math
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from .test_transfer_lock_boundary import load_route


class TransferQuantityTests(unittest.TestCase):
    def invoke(self, name, quantity, get_db):
        route = load_route(name, dict(
            math=math, HTTPException=HTTPException, get_db=get_db,
            _norm_base_unit=lambda value: value,
        ))
        return route(dict(materialName='Cement', quantity=quantity, unit='кг',
                          projectName='Alpha', fromLocation='Alpha',
                          workPackage='Основная', toPersonRole='мастер'))

    def test_invalid_quantities_fail_before_stock_access(self):
        for name in ('create_material_transfer', 'return_material_from_master'):
            for quantity in ('NaN', 'Infinity', '-Infinity', '1e9999', 'bad', {}, [],
                             {'value': 1}, [1], 10 ** 400,
                             True, False, None, 0, -1, '0', '-1'):
                with self.subTest(route=name, quantity=quantity):
                    get_db = Mock(side_effect=AssertionError('Invalid input reached database'))
                    with self.assertRaises(HTTPException) as error:
                        self.invoke(name, quantity, get_db)
                    self.assertEqual(error.exception.status_code, 400)
                    get_db.assert_not_called()

    def test_existing_positive_number_formats_reach_database_boundary(self):
        for name in ('create_material_transfer', 'return_material_from_master'):
            for quantity in (1, 0.5, '1', ' 0.5 ', '1e-3'):
                with self.subTest(route=name, quantity=quantity):
                    get_db = Mock(side_effect=RuntimeError('Valid input reached boundary'))
                    with self.assertRaisesRegex(RuntimeError, 'Valid input reached boundary'):
                        self.invoke(name, quantity, get_db)
                    get_db.assert_called_once()
