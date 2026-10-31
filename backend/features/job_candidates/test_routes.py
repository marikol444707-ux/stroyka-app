import unittest

from fastapi import HTTPException

from .routes import _matches_search_terms, register_job_candidates_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)


class FakeCursor:
    def __init__(self, result=None, rows=()):
        self.result = result
        self.rows = list(rows)
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.value = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class JobCandidateRouteTests(unittest.TestCase):
    def build(self, cursor, *, context=None, roles=None, jev_ingest_key="", jev_company_id=0,
              is_jev_enabled=None):
        app = FakeApp()
        conn = FakeConnection(cursor)
        resolve_calls = []

        def resolve(_cur, _user, _requested, action, **kwargs):
            resolve_calls.append((action, kwargs))
            return context or {"mode": "company", "companyId": 8}

        register_job_candidates_module(app, {
            "get_db": lambda: conn,
            "get_current_user": lambda: {"id": 9},
            "resolve_work_company_context": resolve,
            "effective_company_actors": lambda _user, ctx: [
                {"companyId": ctx.get("companyId", 8), "role": role}
                for role in (roles or ["директор"])
            ],
            "allowed_roles": ("директор", "менеджер_crm"),
            "jev_ingest_key": jev_ingest_key,
            "jev_company_id": jev_company_id,
            "is_jev_enabled": is_jev_enabled or (lambda _cur, _company_id: True),
        })
        return app, conn, resolve_calls

    def test_ingest_is_scoped_and_upserts_idempotently(self):
        cursor = FakeCursor({"id": 41, "inserted": False, "status": "Подходит"})
        app, conn, calls = self.build(cursor)
        response = app.routes[("POST", "/crm/job-candidates")](
            {"source": "eis", "sourceItemId": "EIS-1", "url": "https://example.org/1", "title": "Ремонт"},
            current_user={"name": "Директор"}, x_company_id="8", x_company_mode="company",
        )

        self.assertEqual(response, {"ok": True, "id": 41, "inserted": False, "status": "Подходит"})
        sql, params = cursor.calls[0]
        self.assertIn("ON CONFLICT (company_id, source, identity_key) DO UPDATE", sql)
        self.assertEqual(params[0], 8)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(conn.commits, 1)
        self.assertEqual(calls[0][0], "write")

    def test_rejects_all_company_scope(self):
        cursor = FakeCursor()
        app, _conn, _calls = self.build(cursor, context={"mode": "all_companies"})
        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/crm/job-candidates")](current_user={"id": 9})
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_rejects_user_without_allowed_company_role(self):
        cursor = FakeCursor()
        app, _conn, _calls = self.build(cursor, roles=["наблюдатель"])
        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/crm/job-candidates")](current_user={"id": 9})
        self.assertEqual(raised.exception.status_code, 403)

    def test_candidate_listing_is_blocked_when_company_has_not_enabled_jev(self):
        cursor = FakeCursor()
        app, conn, _ = self.build(cursor, is_jev_enabled=lambda _cur, _company_id: False)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/crm/job-candidates")](current_user={"id": 9})

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(conn.commits, 0)
        self.assertEqual(cursor.calls, [])

    def test_import_report_is_one_company_scoped_transaction(self):
        cursor = FakeCursor({"id": 41, "inserted": True})
        app, conn, calls = self.build(cursor)
        response = app.routes[("POST", "/crm/job-candidates/import-report")](
            {"items": [{
                "source": "browser_agent", "sourceName": "B2B-Center", "sourceItemId": "B2B-Center:12",
                "url": "https://example.org/tender/12", "title": "Строительство школы",
            }]},
            current_user={"name": "Директор"}, x_company_id="8", x_company_mode="company",
        )

        self.assertEqual({key: value for key, value in response.items() if key != "runId"},
                         {"ok": True, "received": 1, "created": 1, "updated": 0})
        sql, params = cursor.calls[0]
        self.assertIn("source_name", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[0], 8)
        self.assertEqual(conn.commits, 1)
        self.assertEqual(calls[0][0], "write")

    def test_jev_ingest_requires_key_and_fans_out_only_to_enabled_company_targets(self):
        cursor = FakeCursor({"inserted": True}, rows=[
            {"company_id": 8, "settings": {"searchTerms": []}},
            {"company_id": 12, "settings": {"searchTerms": []}},
        ])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40, jev_company_id=8)
        payload = {"run_id": "5a0e8400-e29b-41d4-a716-446655440000", "region": "Ставропольский край", "sources": [
            {"provider": "B2B-Center", "query": "ремонт", "ok": True, "status": "observed_first_page", "rows": 1},
            {"provider": "Росэлторг", "query": "ремонт", "ok": False, "status": "source_unavailable", "rows": 0, "error": "do not persist"},
        ], "confirmed": [{
            "source": "B2B-Center", "id": "B2B-8", "url": "https://example.org/b2b-8", "title": "Ремонт кровли",
        }], "review": [], "excluded": []}

        with self.assertRaises(HTTPException) as bad_key:
            app.routes[("POST", "/internal/jev/job-candidates")](payload, x_jev_ingest_key="wrong")
        self.assertEqual(bad_key.exception.status_code, 401)
        self.assertEqual(cursor.calls, [])

        response = app.routes[("POST", "/internal/jev/job-candidates")](payload, x_jev_ingest_key="k" * 40)
        self.assertEqual({key: value for key, value in response.items() if key != "runId"}, {
            "ok": True, "targetCompanies": [
                {"companyId": 8, "created": 1, "updated": 0, "skippedByProfile": 0},
                {"companyId": 12, "created": 1, "updated": 0, "skippedByProfile": 0},
            ], "received": 1, "created": 2, "updated": 0,
            "sourcesChecked": 2, "sourcesUnavailable": 1,
        })
        self.assertEqual(response["runId"], "5a0e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(conn.commits, 1)
        self.assertIn("platform_company_features", cursor.calls[0][0])
        self.assertEqual(cursor.calls[1][1][0], 8)
        self.assertEqual(cursor.calls[2][1][0], 12)
        self.assertEqual(cursor.calls[1][1][-1], "JEV")
        run_writes = [call for call in cursor.calls if "crm_job_candidate_search_runs" in call[0]]
        self.assertEqual(len(run_writes), 2)
        self.assertEqual(run_writes[0][1][0:2], (8, "5a0e8400-e29b-41d4-a716-446655440000"))
        self.assertNotIn("do not persist", str(run_writes[0][1]))

    def test_internal_jev_search_records_empty_source_results(self):
        cursor = FakeCursor(rows=[{"company_id": 8, "settings": {"searchTerms": []}}])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)

        response = app.routes[("POST", "/internal/jev/job-candidates")](
            {"run_id": "5a0e8400-e29b-41d4-a716-446655440000", "companyId": 8,
             "targetCompanyId": 8, "region": "Ставропольский край", "confirmed": [],
             "review": [], "sources": [{"provider": "B2B-Center", "query": "ремонт",
                                          "ok": True, "status": "observed_first_page", "rows": 0}]},
            x_jev_ingest_key="k" * 40,
        )

        self.assertEqual(response["received"], 0)
        self.assertEqual(response["sourcesChecked"], 1)
        self.assertEqual(conn.commits, 1)
        self.assertTrue(any("crm_job_candidate_search_runs" in sql for sql, _ in cursor.calls))

    def test_search_history_is_limited_to_selected_company(self):
        cursor = FakeCursor(rows=[{"id": 5, "runId": "run-a", "sources": []}])
        app, _conn, calls = self.build(cursor, context={"mode": "company", "companyId": 12})

        response = app.routes[("GET", "/crm/job-candidates/search-runs")](
            limit=7, current_user={"id": 9}, x_company_id="12", x_company_mode="company",
        )

        self.assertEqual(response, [{"id": 5, "runId": "run-a", "sources": []}])
        self.assertEqual(cursor.calls[0][1], (12, 7))
        self.assertIn("WHERE company_id=%s", cursor.calls[0][0])
        self.assertEqual(calls[0][0], "read")

    def test_internal_search_targets_exposes_only_enabled_company_profiles(self):
        cursor = FakeCursor(rows=[
            {"company_id": 8, "settings": {"region": "Ставропольский край",
                                             "searchTerms": ["школа"],
                                             "sourceProviders": ["B2B-Center"]}},
            {"company_id": 12, "settings": {"searchTerms": ["кровля"],
                                              "sourceProviders": ["Росэлторг", "not-a-provider"]}},
        ])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        route = app.routes[("GET", "/internal/jev/job-candidates")]

        with self.assertRaises(HTTPException) as bad_key:
            route(x_jev_ingest_key="wrong")
        self.assertEqual(bad_key.exception.status_code, 401)

        response = route(x_jev_ingest_key="k" * 40)
        self.assertEqual(response, {"targets": [
            {"companyId": 8, "region": "Ставропольский край", "searchTerms": ["школа"],
             "sourceProviders": ["B2B-Center"]},
            {"companyId": 12, "region": "Ставропольский край", "searchTerms": ["кровля"],
             "sourceProviders": ["Росэлторг"]},
        ]})
        self.assertIn("enabled=TRUE", cursor.calls[0][0])
        self.assertIn("COALESCE(c.active, TRUE)=TRUE", cursor.calls[0][0])
        self.assertEqual(conn.commits, 0)

    def test_internal_report_can_target_only_one_enabled_company(self):
        cursor = FakeCursor({"inserted": True}, rows=[
            {"company_id": 8, "settings": {"searchTerms": []}},
        ])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        payload = {"companyId": 8, "targetCompanyId": 8, "confirmed": [{
            "source": "B2B-Center", "id": "B2B-8", "url": "https://example.org/b2b-8", "title": "Ремонт кровли",
        }]}

        response = app.routes[("POST", "/internal/jev/job-candidates")](payload, x_jev_ingest_key="k" * 40)

        self.assertEqual(response["targetCompanies"], [
            {"companyId": 8, "created": 1, "updated": 0, "skippedByProfile": 0},
        ])
        self.assertIn("AND f.company_id=%s", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (8,))
        self.assertEqual(cursor.calls[1][1][0], 8)
        self.assertEqual(conn.commits, 1)

    def test_internal_report_rejects_invalid_target_company_id(self):
        cursor = FakeCursor()
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/internal/jev/job-candidates")](
                {"targetCompanyId": "8", "confirmed": []}, x_jev_ingest_key="k" * 40,
            )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(conn.commits, 0)

    def test_internal_report_rejects_company_identity_mismatch(self):
        cursor = FakeCursor()
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/internal/jev/job-candidates")](
                {"companyId": 8, "targetCompanyId": 12, "confirmed": []},
                x_jev_ingest_key="k" * 40,
            )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(conn.commits, 0)

    def test_jev_ingest_filters_candidates_by_each_company_search_profile(self):
        cursor = FakeCursor({"inserted": True}, rows=[
            {"company_id": 8, "settings": {"searchTerms": ["школа"]}},
            {"company_id": 12, "settings": {"searchTerms": ["кровля"]}},
        ])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        payload = {"confirmed": [
            {"source": "B2B-Center", "id": "1", "url": "https://example.org/1", "title": "Капремонт школы"},
            {"source": "B2B-Center", "id": "2", "url": "https://example.org/2", "title": "Ремонт кровли"},
        ]}

        response = app.routes[("POST", "/internal/jev/job-candidates")](
            payload, x_jev_ingest_key="k" * 40,
        )

        self.assertEqual(response["targetCompanies"], [
            {"companyId": 8, "created": 1, "updated": 0, "skippedByProfile": 1},
            {"companyId": 12, "created": 1, "updated": 0, "skippedByProfile": 1},
        ])
        self.assertEqual(conn.commits, 1)
        self.assertEqual(cursor.calls[1][1][0], 8)
        self.assertEqual(cursor.calls[1][1][6], "Капремонт школы")
        self.assertEqual(cursor.calls[2][1][0], 12)
        self.assertEqual(cursor.calls[2][1][6], "Ремонт кровли")

    def test_jev_ingest_filters_sources_independently_per_company(self):
        cursor = FakeCursor({"inserted": True}, rows=[
            {"company_id": 8, "settings": {"sourceProviders": ["Торги Федерации"], "searchTerms": []}},
            {"company_id": 12, "settings": {"sourceProviders": ["B2B-Center"], "searchTerms": []}},
        ])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        payload = {"confirmed": [
            {"source": "B2B-Center", "id": "1", "url": "https://example.org/1", "title": "Ремонт школы"},
            {"source": "Торги Федерации · коммерческие", "id": "2", "url": "https://example.org/2", "title": "Строительство школы"},
        ]}

        response = app.routes[("POST", "/internal/jev/job-candidates")](
            payload, x_jev_ingest_key="k" * 40,
        )

        self.assertEqual(response["targetCompanies"], [
            {"companyId": 8, "created": 1, "updated": 0, "skippedByProfile": 1},
            {"companyId": 12, "created": 1, "updated": 0, "skippedByProfile": 1},
        ])
        self.assertEqual(cursor.calls[1][1][0], 8)
        self.assertEqual(cursor.calls[1][1][6], "Строительство школы")
        self.assertEqual(cursor.calls[2][1][0], 12)
        self.assertEqual(cursor.calls[2][1][6], "Ремонт школы")
        self.assertEqual(conn.commits, 1)

    def test_provider_aliases_match_all_active_server_adapters(self):
        sources = {
            "B2B-Center": "B2B-Center",
            "Росэлторг": "Росэлторг",
            "Фабрикант": "Фабрикант",
            "ЭТП ГПБ": "ЭТП ГПБ",
            "Сбер А": "Сбер А",
            "ТЭК-Торг": "ТЭК-Торг · 223-ФЗ и коммерческие",
            "Торги Федерации": "Торги Федерации · коммерческие",
            "Р-ТЕНДЕР": "Р-ТЕНДЕР · коммерческие",
        }
        for selected, source_name in sources.items():
            with self.subTest(provider=selected):
                self.assertTrue(_matches_search_terms(
                    {"source_name": source_name}, {"sourceProviders": [selected], "searchTerms": []},
                ))
                self.assertFalse(_matches_search_terms(
                    {"source_name": source_name}, {"sourceProviders": ["B2B-Center" if selected != "B2B-Center" else "Росэлторг"], "searchTerms": []},
                ))

    def test_jev_ingest_rejects_reports_when_no_company_has_enabled_the_feature(self):
        cursor = FakeCursor(rows=[])
        app, conn, _ = self.build(cursor, jev_ingest_key="k" * 40)
        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/internal/jev/job-candidates")](
                {"confirmed": [{"url": "https://example.org/x", "title": "Ремонт"}]},
                x_jev_ingest_key="k" * 40,
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(conn.commits, 0)

    def test_jev_ingest_is_disabled_without_secret(self):
        app, _conn, _ = self.build(FakeCursor(), jev_company_id=8)
        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/internal/jev/job-candidates")](
                {"confirmed": [{"url": "https://example.org/x", "title": "Ремонт"}]},
                x_jev_ingest_key="anything",
            )
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
