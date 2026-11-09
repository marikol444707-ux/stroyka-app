import json
import unittest
from contextlib import contextmanager
from fastapi import HTTPException

from .routes import owned_snapshot, register_document_versions_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(handler):
            self.routes[path] = handler
            return handler
        return decorator


class Scope:
    def __init__(self, rows):
        self.rows, self.calls, self.closed = rows, [], False

    @contextmanager
    def transaction(self, user, request, roles):
        try:
            yield self, [dict(id=7, role='директор', companyId=2)]
        finally:
            self.closed = True

    def visible(self, actors, roles):
        return 'p.company_id=%s', [2]

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def __iter__(self):
        return iter(self.rows)


def build(rows=()):
    scope, app = Scope(rows), FakeApp()
    register_document_versions_module(app, dict(record_scope=scope, get_current_user=lambda: None,
        project_document_roles=('директор',), package_access_filter=lambda actor, column: ('', [])))
    return app.routes, scope


class DocumentVersionsRoutesTest(unittest.TestCase):
    def test_routes_filter_current_owner_and_typed_parent(self):
        snapshot=dict(id=9,company_id=2,project_name='P',work_journal_id=4,work_package='A',total=10)
        row=(1,'hidden_works_act',9,'v1',json.dumps(snapshot),'User','Reason','2026-11-09',2,'P',4,'A')
        routes,scope=build([row])
        result=routes['/document-versions'](document_type='hidden_works_act',document_id=9)
        self.assertEqual(result[0]['id'],1)
        self.assertNotIn('snapshot',result[0])
        query,params=scope.calls[0]
        self.assertIn('p.company_id=%s',query)
        self.assertIn("v.document_type='hidden_works_act'",query)
        self.assertEqual(params,[2,'hidden_works_act',9])
        self.assertTrue(scope.closed)
        self.assertEqual(routes['/document-versions/{vid}'](vid=1)['snapshot'],snapshot)

    def test_missing_version_is_404_and_connection_closes(self):
        routes,scope=build()
        with self.assertRaises(HTTPException) as error:
            routes['/document-versions/{vid}'](vid=99)
        self.assertEqual(error.exception.status_code,404)
        self.assertTrue(scope.closed)

    def test_legacy_malformed_and_moved_snapshots_have_no_inferred_owner(self):
        valid=dict(id=9,company_id=2,project_name='P',work_journal_id=4,work_package='A')
        for raw in ('broken', '[]', '{}', dict(valid,company_id=True), dict(valid,company_id=3),
                    dict(valid,id=10),dict(valid,project_name='Other'),dict(valid,work_journal_id=5),
                    dict(valid,work_package='B')):
            with self.subTest(raw=raw):
                self.assertIsNone(owned_snapshot(raw,9,2,'P',4,'A'))


if __name__ == '__main__':
    unittest.main()
