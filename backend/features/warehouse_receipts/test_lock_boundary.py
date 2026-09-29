"""Receipt compatibility lock must precede schema/parent reads in its transaction."""
import unittest
from unittest.mock import Mock

import psycopg2.extras
from fastapi import HTTPException

from backend.features.material_traceability.test_transfer_lock_boundary import load_route


class ReceiptLockBoundaryTests(unittest.TestCase):
    def invoke(self, route_name, present=True, fail_lock=False, continue_schema=False):
        conn, cur = Mock(), Mock()
        conn.autocommit = True
        conn.closed = cur.closed = False
        conn.cursor.return_value = cur
        events = []
        cur.fetchone.return_value = {'present': present}

        def execute(sql, params=()):
            self.assertFalse(conn.autocommit)
            if sql.startswith('LOCK TABLE'):
                events.append('lock')
                if fail_lock:
                    raise HTTPException(409, 'Synthetic lock failure')
            if sql.startswith('SELECT * FROM supply_deliveries'):
                events.append('delivery')
                conn.commit.assert_not_called()
                raise HTTPException(409, 'Stop before delivery access')

        def schema(cursor):
            events.append('schema')
            if not continue_schema:
                raise HTTPException(409, 'Stop before runtime DDL')

        cur.execute.side_effect = execute
        namespace = dict(get_db=lambda: conn, psycopg2=psycopg2,
                         HTTPException=HTTPException,
                         _payment_ledger_available=lambda cursor: False,
                         _ensure_supply_runtime_columns=schema,
                         _ensure_invoice_document_link_columns=schema)
        route = load_route(route_name, namespace)
        with self.assertRaises(HTTPException):
            if route_name == 'receive_supply_delivery':
                route(1, {}, _current_user={'role': 'директор'})
            else:
                route({}, current_user={'role': 'директор'})
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
        return events

    def test_lock_precedes_receipt_schema_preparation(self):
        for name in ('receive_supply_delivery', '_create_warehouse_invoice_record'):
            with self.subTest(route=name):
                self.assertEqual(self.invoke(name), ['lock', 'schema'])

    def test_acceptance_keeps_lock_after_schema_preparation(self):
        self.assertEqual(self.invoke('receive_supply_delivery', continue_schema=True),
                         ['lock', 'schema', 'delivery'])

    def test_schema_absent_keeps_legacy_behavior(self):
        for name in ('receive_supply_delivery', '_create_warehouse_invoice_record'):
            with self.subTest(route=name):
                self.assertEqual(self.invoke(name, present=False), ['schema'])

    def test_lock_failure_rolls_back_before_schema_changes(self):
        for name in ('receive_supply_delivery', '_create_warehouse_invoice_record'):
            with self.subTest(route=name):
                self.assertEqual(self.invoke(name, fail_lock=True), ['lock'])
