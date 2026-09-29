import os
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException

from .distribution_receipt import distribution_quality_enabled, quality_spec, create_distribution_quality


def allocation(**updates):
    return dict(id=11, company_id=2, project_id=7, project_name='Object', material_name='Material',
                quantity='1.23', unit='шт', work_package='Основная', **updates)


class DistributionQualityTests(TestCase):
    def test_only_exact_one_enables_writer(self):
        for value in ('', '0', 'true', '1'):
            with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': value}):
                self.assertEqual(distribution_quality_enabled(), value == '1')

    def test_disabled_writer_does_not_touch_db_or_dependencies(self):
        cur = Mock()
        with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '0'}):
            self.assertIsNone(create_distribution_quality(cur, {}, {}))
        self.assertEqual(cur.mock_calls, [])

    def test_strict_owner_and_inspection_precision(self):
        deps = {'detect_cable_info': lambda name: {'isCable': False}}
        for updates in ({'company_id': True}, {'project_id': '7'}, {'id': 0},
                        {'quantity': '1.00001'}, {'quantity': 'NaN'}, {'quantity': '-1'}):
            with self.subTest(updates=updates), self.assertRaises(HTTPException):
                quality_spec({**allocation(), **updates}, deps)

    def test_cable_precision_and_meter_normalization(self):
        deps = {'detect_cable_info': lambda name: {'isCable': True},
                'normalize_unit': lambda unit: 'м' if unit == 'пог.м' else unit}
        spec = quality_spec({**allocation(), 'unit': 'пог.м'}, deps)
        self.assertEqual(spec['unit'], 'м')
        for updates in ({'quantity': '1.234'}, {'unit': 'кг'}):
            with self.assertRaises(HTTPException):
                quality_spec({**allocation(), 'unit': 'м', **updates}, deps)

    def test_missing_detector_fails_closed(self):
        with self.assertRaises(HTTPException):
            quality_spec(allocation(), {})
