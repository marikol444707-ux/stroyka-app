import unittest
from fastapi import HTTPException

from backend.features.supplier_offers.routes import register_supplier_offers_module


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self._last = None
        self.rowcount = 0
    def execute(self, sql, params=None):
        self._last = sql.strip()
    def fetchone(self):
        # offer select first, invoice select second
        if 'FROM supplier_offers' in (self._last or ''):
            return self._rows.get('offer')
        if 'FROM supplier_invoices' in (self._last or ''):
            return self._rows.get('invoice')
        return None
    def fetchall(self):
        return []
    def close(self):
        pass


class FakeConn:
    def __init__(self, rows):
        self._rows = rows
    def cursor(self, cursor_factory=None):
        return FakeCursor(self._rows)
    def commit(self):
        pass
    def close(self):
        pass


def build(deps_overrides=None):
    app = type('A', (), {'routes': {}})()
    def reg(method, path):
        def dec(fn):
            app.routes[(method, path)] = fn
            return fn
        return dec
    fake_app = type('App', (), {'get': lambda self,p: reg('GET',p), 'post': lambda self,p: reg('POST',p), 'put': lambda self,p: reg('PUT',p)})()
    deps = {
        '_require_supplier_offer_visibility': lambda *a, **k: None,
        '_log_supplier_offer_event': lambda *a, **k: None,
        '_ensure_supplier_offer_events_table': lambda cur: None,
        '_ensure_supply_request_recipients_table': lambda cur: None,
        '_ensure_supply_runtime_columns': lambda cur: None,
        '_find_existing_supplier_invoice_duplicate': lambda *a, **k: (None,),
        '_find_supply_request_recipient': lambda *a, **k: None,
        '_float_or_zero': lambda v: float(v or 0),
        '_json_list_or_empty': lambda v: (v and [] ) or [],
        '_norm_base_unit': lambda v: v,
        '_norm_key_text': lambda v: v,
        '_normalize_supplier_ids': lambda v: v or [],
        '_positive_int_or_none': lambda v: v,
        '_resolve_work_company_context': lambda *a, **k: ({'companyId':1}, None),
        '_supply_work_package': lambda v: (v or ''),
        'current_supplier_ids': lambda cur,u: [],
        'has_package_access': lambda u,p: True,
        'package_access_filter': lambda u: ('',[]),
        'require_project_or_warehouse_access': lambda u,p: None,
        'user_project_names': lambda u: [],
        'get_db': lambda: None,
        'get_current_user': lambda: None,
        'require_roles': lambda *r: (lambda: None),
        'SUPPLY_ROLES': (),
        'SUPPLY_INTERNAL_ROLES': ('директор',),
        'LEADERSHIP_ROLES': (),
        'WORKER_EXECUTION_ROLES': (),
        'PACKAGE_LIMIT_ROLES': (),
        'PLATFORM_STAFF_ROLES': (),
        'CLIENT_ACCOUNT_ROLES': (),
        '_ensure_supply_runtime_columns': lambda cur: None,
        '_find_supply_request_recipient': lambda *a, **k: None,
        '_float_or_zero': lambda v: float(v or 0),
        '_json_list_or_empty': lambda v: (v and [] ) or [],
        '_supply_work_package': lambda v: (v or ''),
        'current_supplier_ids': lambda cur,u: [],
        'current_supplier_ids': lambda cur, u: [],
        'require_project_or_warehouse_access': lambda u,p: None,
        'supplier_group_scope_ids': lambda cur, ids: [],
        '_ensure_supply_request_recipients_table': lambda cur: None,
        'OFFERS_SELECT': 'SELECT 1',
        'DELIVERY_SELECT': 'SELECT 1',
    }
    if deps_overrides:
        deps.update(deps_overrides)
    register_supplier_offers_module(fake_app, deps)
    return app, deps


class ShipTenantIsolationTests(unittest.TestCase):
    def test_internal_user_cannot_ship_other_company_offer(self):
        # offer belongs to company 2, user resolved to company 1 -> should raise
        rows = {'offer': {'id': 10, 'request_id': 100, 'supplier_id': 5, 'company_id': 2, 'request_company_id': 2, 'status': 'Утверждено'}}
        conn = FakeConn(rows)
        def get_db():
            return conn
        def resolve_resource_company_actor(cur, user, company_id, action, **k):
            # resolve to company 1 (user's effective company)
            return ({'companyId': 1}, user)
        def assert_rows_company_scope(rows, company_id, name):
            # if row company differs -> raise
            for r in rows:
                if (r.get('company_id') or 0) != company_id:
                    raise HTTPException(status_code=403, detail='company mismatch')
        app, deps = build({'get_db': get_db, 'resolve_resource_company_actor': resolve_resource_company_actor, 'assert_rows_company_scope': assert_rows_company_scope, 'current_supplier_ids': lambda cur,u: []})
        handler = app.routes[('POST', '/supplier-offers/{id}/ship')]
        with self.assertRaises(HTTPException):
            handler(10, {}, {'role':'директор'})

    def test_legacy_offer_without_company_does_not_become_company_1(self):
        rows = {'offer': {'id': 11, 'request_id': 101, 'supplier_id': 5, 'company_id': None, 'request_company_id': None, 'status': 'Утверждено'}}
        conn = FakeConn(rows)
        def get_db():
            return conn
        def resolve_resource_company_actor(cur, user, company_id, action, **k):
            # if company_id is None we should fail
            if not company_id:
                raise HTTPException(status_code=403, detail='missing company')
            return ({'companyId': company_id}, user)
        app, deps = build({'get_db': get_db, 'resolve_resource_company_actor': resolve_resource_company_actor, 'assert_rows_company_scope': lambda *a, **k: None})
        handler = app.routes[('POST', '/supplier-offers/{id}/ship')]
        with self.assertRaises(HTTPException):
            handler(11, {}, {'role':'директор'})

    def test_correct_offer_of_own_company_continues(self):
        rows = {'offer': {'id': 12, 'request_id': 102, 'supplier_id': 5, 'company_id': 1, 'request_company_id': 1, 'payment_terms': '', 'items_json': '[]', 'total_price': 100.0, 'status':'Утверждено'}, 'invoice': None}
        conn = FakeConn(rows)
        def get_db():
            return conn
        def resolve_resource_company_actor(cur, user, company_id, action, **k):
            return ({'companyId': int(company_id or 1)}, user)
        def assert_rows_company_scope(rows, company_id, name):
            for r in rows:
                if (r.get('company_id') or company_id) != company_id:
                    raise HTTPException(status_code=403)
        app, deps = build({'get_db': get_db, 'resolve_resource_company_actor': resolve_resource_company_actor, 'assert_rows_company_scope': assert_rows_company_scope})
        handler = app.routes[('POST', '/supplier-offers/{id}/ship')]
        # Call handler and do NOT swallow HTTPException — ownership checks must succeed without raising.
        handler(12, {}, {'role':'директор'})


if __name__ == '__main__':
    unittest.main()
