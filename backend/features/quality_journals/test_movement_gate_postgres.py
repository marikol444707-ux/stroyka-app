import os
from unittest.mock import patch

from .test_owner_stock_postgres import OwnerStockPostgresTests


class QualityMovementGateTests(OwnerStockPostgresTests):
    def test_legacy_movement_cannot_bypass_owned_quality(self):
        with patch.dict(os.environ, {'OWNED_DISTRIBUTION_QUALITY_ENABLED': '1'}):
            with patch.object(self.main, '_apply_warehouse_movement') as movement:
                self.api('director', 'POST', '/warehouse-movements', {
                    'materialName': 'Material', 'quantity': 1, 'unit': 'шт',
                    'fromLocation': 'Основной склад', 'toLocation': self.f['project'],
                }, expected=409)
                movement.assert_not_called()
