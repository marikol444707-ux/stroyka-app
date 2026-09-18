"""Default-off exact receipt-lot distribution; registration has no DB side effects."""
from .routes import register_warehouse_distribution_module

__all__ = ['register_warehouse_distribution_module']
