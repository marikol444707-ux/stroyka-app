import asyncio
import io
import os
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from backend.features.public_site.routes import (
    _public_attachment_tokens,
    _public_lead_notes,
    _public_site_project,
    register_public_site_routes,
)


class _FakeApp:
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


class _FakeCursor:
    def __init__(self, statements):
        self.statements = statements
        self.last_query = ""
        self.last_params = None
        self.rowcount = 0

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query).split())
        self.last_params = params
        self.statements.append((self.last_query, params))
        self.rowcount = 1 if self.last_query.startswith("UPDATE public_lead_uploads") else 0

    def fetchone(self):
        if self.last_query.startswith("SELECT COUNT(*) FROM public_lead_uploads"):
            return (0,)
        if self.last_query.startswith("INSERT INTO file_ownership"):
            return (71,)
        if self.last_query.startswith("INSERT INTO crm_leads"):
            return (501,)
        return None

    def fetchall(self):
        if self.last_query.startswith("SELECT u.token"):
            token = self.last_params[0][0]
            return [(token, 71, "plan.pdf", "application/pdf", 16)]
        return []

    def close(self):
        pass


class _FakeConnection:
    def __init__(self, statements):
        self.cursor_instance = _FakeCursor(statements)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class PublicLeadNotesTests(unittest.TestCase):
    def test_public_project_exposes_only_explicit_public_fields(self):
        project = _public_site_project({
            "id": 17,
            "name": "ул. Частная, заказчик Иванов",
            "status": "В работе",
            "publicTitle": "Дом с террасой",
            "publicCategory": "house",
            "publicImages": ["https://cdn.example.test/house.webp"],
            "publicStage": "Тёплый контур",
            "publicAiNotes": "скрыть лицо заказчика",
            "publicAiStatus": "Проверено директором",
        })

        self.assertEqual(project["title"], "Дом с террасой")
        self.assertEqual(project["images"], ["https://cdn.example.test/house.webp"])
        self.assertNotIn("projectName", project)
        self.assertNotIn("projectId", project)
        self.assertNotIn("aiNotes", project)
        self.assertNotIn("aiStatus", project)
        self.assertNotIn("ул. Частная", str(project))

    def test_public_project_requires_public_title_and_real_image(self):
        self.assertIsNone(_public_site_project({
            "id": 17,
            "name": "Внутреннее название",
            "publicTitle": "",
            "publicImages": ["https://cdn.example.test/house.webp"],
        }))
        self.assertIsNone(_public_site_project({
            "id": 18,
            "publicTitle": "Дом с террасой",
            "publicImages": [],
        }))

    def test_includes_selected_project_in_crm_notes(self):
        notes = _public_lead_notes({
            "comment": "Нужна консультация",
            "selectedProject": {
                "directionTitle": "Одноэтажный современный дом",
                "projectCode": "H1-01",
                "projectTitle": "Одноэтажный кирпичный дом 110 м2",
                "projectArea": "110 м2",
                "projectFloors": "1 этаж",
                "estimateRange": "9,6-11,2 млн ₽",
                "projectUrl": "https://stroyka26.pro/?project=H1-01#projects",
                "media": [{"src": "/private-or-large-media.png"}],
            },
        })

        self.assertIn("Комментарий: Нужна консультация", notes)
        self.assertIn("код: H1-01", notes)
        self.assertIn("проект: Одноэтажный кирпичный дом 110 м2", notes)
        self.assertIn("площадь: 110 м2", notes)
        self.assertIn("ориентир: 9,6-11,2 млн ₽", notes)
        self.assertIn("карточка: https://stroyka26.pro/?project=H1-01#projects", notes)
        self.assertNotIn("private-or-large-media", notes)

    def test_includes_plot_check_in_crm_notes(self):
        notes = _public_lead_notes({
            "selectedProject": {
                "projectTitle": "Дом 110 м2",
                "plotCheck": {
                    "statusLabel": "Участок уже есть",
                    "accessLabel": "Подъезд ограничен",
                    "reliefLabel": "Есть уклон",
                    "utilitiesLabel": "Нужно подключение",
                    "geologyReady": False,
                    "geodesyReady": True,
                    "reviewItems": ["подъезд техники", "перепад высот", "геология"],
                },
            },
        })

        self.assertIn("Участок: Участок уже есть", notes)
        self.assertIn("подъезд: Подъезд ограничен", notes)
        self.assertIn("геология: нет", notes)
        self.assertIn("геодезия: есть", notes)
        self.assertIn("проверить: подъезд техники, перепад высот, геология", notes)

    def test_includes_selected_financing_scenario_in_crm_notes(self):
        notes = _public_lead_notes({
            "selectedProject": {
                "projectTitle": "Дом 110 м2",
                "financing": {
                    "status": "indicative",
                    "modeLabel": "Ипотека на строительство",
                    "downPaymentPercent": 20,
                    "downPaymentRange": "2-2,4 млн ₽",
                    "termLabel": "20 лет",
                    "annualRate": 12,
                    "monthlyRange": "88-106 тыс. ₽/мес.",
                },
            },
        })

        self.assertIn("Финансирование: Ипотека на строительство", notes)
        self.assertIn("первый взнос: 20% (2-2,4 млн ₽)", notes)
        self.assertIn("срок: 20 лет", notes)
        self.assertIn("примерная ставка: 12%", notes)
        self.assertIn("платёж: 88-106 тыс. ₽/мес.", notes)
        self.assertIn("предварительный сценарий, не банковское предложение", notes)

    def test_includes_compared_project_shortlist_in_crm_notes(self):
        notes = _public_lead_notes({
            "selectedProject": {
                "projectCode": "H1-02",
                "projectTitle": "Дом 116 м2",
                "comparison": {
                    "status": "customer_shortlist",
                    "selectedCode": "H1-02",
                    "comparisonUrl": "https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects",
                    "items": [
                        {"code": "H1-01", "title": "Дом 110 м2", "estimateRange": "9-11 млн ₽"},
                        {"code": "H1-02", "title": "Дом 116 м2", "estimateRange": "10-12 млн ₽"},
                        {"code": "H1-01", "title": "Дубль", "estimateRange": "1 ₽"},
                        {"code": "H1-03", "title": "Дом 132 м2", "estimateRange": "11-14 млн ₽"},
                        {"code": "H1-04", "title": "Лишний", "estimateRange": "15 млн ₽"},
                    ],
                },
            },
        })

        self.assertIn("Сравнение клиента:", notes)
        self.assertIn("H1-01 — Дом 110 м2 — 9-11 млн ₽", notes)
        self.assertIn("H1-02 — Дом 116 м2 — 10-12 млн ₽ — выбран", notes)
        self.assertIn("H1-03 — Дом 132 м2 — 11-14 млн ₽", notes)
        self.assertIn(
            "Ссылка на сравнение: https://stroyka26.pro/?project=H1-02&compare=H1-01%2CH1-02#projects",
            notes,
        )
        self.assertNotIn("Дубль", notes)
        self.assertNotIn("H1-04", notes)

    def test_ignores_external_comparison_url_in_crm_notes(self):
        notes = _public_lead_notes({
            "selectedProject": {
                "comparison": {
                    "status": "customer_shortlist",
                    "selectedCode": "H1-01",
                    "comparisonUrl": "https://evil.example/phishing",
                    "items": [{"code": "H1-01", "title": "Дом 110 м2"}],
                },
            },
        })

        self.assertIn("Сравнение клиента:", notes)
        self.assertNotIn("evil.example", notes)

    def test_ignores_invalid_selected_project(self):
        self.assertEqual(
            _public_lead_notes({"selectedProject": "H1-01", "page": "public-site"}),
            "Страница: public-site",
        )

    def test_public_file_upload_is_disabled_by_default(self):
        app = _FakeApp()
        register_public_site_routes(app, {
            "get_db": lambda: self.fail("database must not be opened"),
            "require_roles": lambda *_roles: lambda: {},
            "leadership_roles": ("директор",),
            "require_project_access": lambda *_args: None,
            "project_public_select": "",
            "system_project_name": "Система",
        })

        with self.assertRaises(HTTPException) as error:
            asyncio.run(app.routes[("POST", "/site/lead-files")](None, None))

        self.assertEqual(error.exception.status_code, 404)

    def test_normalizes_unique_attachment_tokens(self):
        first = "a" * 32
        second = "b" * 32
        self.assertEqual(
            _public_attachment_tokens({"attachmentTokens": [first, first, second]}),
            [first, second],
        )

    def test_rejects_more_than_five_attachment_tokens(self):
        with self.assertRaises(HTTPException) as error:
            _public_attachment_tokens({
                "attachmentTokens": [str(index).zfill(32) for index in range(6)],
            })

        self.assertEqual(error.exception.status_code, 422)

    def test_rejects_invalid_attachment_token(self):
        with self.assertRaises(HTTPException) as error:
            _public_attachment_tokens({"attachmentTokens": ["not-a-token"]})

        self.assertEqual(error.exception.status_code, 422)

    def test_upload_token_is_attached_to_new_crm_lead(self):
        app = _FakeApp()
        statements = []
        connections = []

        def get_db():
            connection = _FakeConnection(statements)
            connections.append(connection)
            return connection

        register_public_site_routes(app, {
            "get_db": get_db,
            "require_roles": lambda *_roles: lambda: {},
            "leadership_roles": ("директор",),
            "require_project_access": lambda *_args: None,
            "project_public_select": "",
            "system_project_name": "Система",
            "public_site_lead_uploads_enabled": True,
            "public_site_company_id": 1,
            "save_upload_bytes": lambda *_args: {
                "url": "/uploads/quarantine/file.pdf",
                "key": "uploads/quarantine/file.pdf",
            },
        })
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        upload = UploadFile(
            filename="plan.pdf",
            file=io.BytesIO(b"%PDF-1.7\nplan"),
            headers=Headers({"content-type": "application/pdf"}),
        )

        uploaded = asyncio.run(app.routes[("POST", "/site/lead-files")](request, upload))
        created = app.routes[("POST", "/site/leads")](
            {
                "name": "Тест",
                "phone": "+70000000000",
                "consentAccepted": True,
                "attachmentTokens": [uploaded["token"]],
            },
            request,
        )

        self.assertEqual(created, {"ok": True, "id": 501, "attachments": 1})
        lead_query, lead_insert = next(
            (query, params) for query, params in statements
            if query.startswith("INSERT INTO crm_leads")
        )
        document_query, document_insert = next(
            (query, params) for query, params in statements
            if query.startswith("INSERT INTO crm_lead_documents")
        )
        task_query, task_insert = next(
            (query, params) for query, params in statements
            if query.startswith("INSERT INTO crm_lead_tasks")
        )
        self.assertEqual(lead_query.count("%s"), len(lead_insert))
        self.assertEqual(document_query.count("%s"), len(document_insert))
        self.assertEqual(task_query.count("%s"), len(task_insert))
        self.assertEqual(lead_insert[0], 1)
        self.assertEqual(document_insert[0:2], (1, 501))
        self.assertEqual(document_insert[3], "/tenant-files/71/content")
        self.assertEqual(task_insert[0:2], (1, 501))
        self.assertFalse(any(query.startswith("INSERT INTO ai_tasks") for query, _params in statements))
        self.assertTrue(all(connection.rollbacks == 0 for connection in connections))

    def test_public_lead_rejects_missing_site_company_before_database_write(self):
        app = _FakeApp()
        database_calls = []
        register_public_site_routes(app, {
            "get_db": lambda: database_calls.append(True),
            "require_roles": lambda *_roles: lambda: {},
            "leadership_roles": ("директор",),
            "require_project_access": lambda *_args: None,
            "project_public_select": "",
            "system_project_name": "Система",
            "public_site_company_id": None,
        })
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/site/leads")](
                {"phone": "+70000000000", "consentAccepted": True},
                request,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(database_calls, [])


def _inserted_values(sql, params):
    compact = " ".join(sql.split())
    columns = [name.strip() for name in compact.split("(", 1)[1].split(")", 1)[0].split(",")]
    value_sql = compact.split("VALUES", 1)[1].split("(", 1)[1].rsplit(")", 1)[0]
    tokens = [token.strip() for token in value_sql.split(",")]
    values = list(params or [])
    mapped = {}
    for name, token in zip(columns, tokens, strict=True):
        mapped[name] = values.pop(0) if token == "%s" else token
    if values:
        raise AssertionError("unused insert values")
    return mapped


class _NotifyCursor(_FakeCursor):
    def execute(self, query, params=None):
        if "INSERT INTO messenger_outbox" in " ".join(str(query).split()):
            raise RuntimeError("outbox unavailable")
        super().execute(query, params)


class PublicLeadSourceTests(unittest.TestCase):
    def setUp(self):
        self._env = unittest.mock.patch.dict(os.environ, {
            "LEAD_NOTIFY_TELEGRAM_CHAT_ID": "",
            "LEAD_NOTIFY_MAX_CHAT_ID": "",
            "LEAD_NOTIFY_COMPANY_ID": "",
        }, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def _app(self, statements, cursor_cls=_FakeCursor):
        connections = []

        def get_db():
            connection = _FakeConnection(statements)
            connection.cursor_instance = cursor_cls(statements)
            connections.append(connection)
            return connection

        app = _FakeApp()
        register_public_site_routes(app, {
            "get_db": get_db,
            "require_roles": lambda *_roles: lambda: {},
            "leadership_roles": ("директор",),
            "require_project_access": lambda *_args: None,
            "project_public_select": "",
            "system_project_name": "Система",
            "public_site_company_id": 7,
        })
        return app, connections

    def _post(self, app, payload):
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.10"))
        return app.routes[("POST", "/site/leads")](payload, request)

    def test_known_ad_source_is_stored_without_changing_utm_notes(self):
        statements = []
        app, connections = self._app(statements)
        created = self._post(app, {
            "name": "Иван",
            "phone": "+79990000000",
            "consentAccepted": True,
            "source": "Сайт",
            "address": "Ставрополь, ул. Мира, 1",
            "calculation": {"typeLabel": "Дом"},
            "utm": {
                "utm_source": "netip",
                "utm_medium": "telegram",
                "utm_campaign": "ads",
                "utm_content": "post-1",
            },
        })

        self.assertEqual(created["ok"], True)
        lead_sql, lead_params = next(
            item for item in statements if item[0].startswith("INSERT INTO crm_leads")
        )
        saved = _inserted_values(lead_sql, lead_params)
        self.assertEqual(saved["company_id"], 7)
        self.assertEqual(saved["source"], "Сайт / Нетипичный Ставрополь")
        self.assertEqual(saved["utm_source"], "netip")
        self.assertEqual(saved["utm_medium"], "telegram")
        self.assertEqual(saved["utm_campaign"], "ads")
        self.assertEqual(saved["work_type"], "Дом")
        self.assertEqual(saved["address"], "Ставрополь, ул. Мира, 1")
        self.assertIn("UTM: utm_source=netip · utm_medium=telegram · utm_campaign=ads · utm_content=post-1", saved["notes"])
        self.assertEqual(connections[0].commits, 1)
        self.assertEqual(connections[0].rollbacks, 0)

    def test_partner_form_keeps_channel_and_unknown_code(self):
        statements = []
        app, _connections = self._app(statements)
        self._post(app, {
            "name": "Поставщик",
            "phone": "+79990000001",
            "consentAccepted": True,
            "partnerType": "supplier",
            "source": "Сайт: партнерская заявка",
            "utm": {"utm_source": "new_channel", "utm_medium": "telegram", "utm_campaign": "ads"},
        })
        lead_sql, lead_params = next(
            item for item in statements if item[0].startswith("INSERT INTO crm_leads")
        )
        saved = _inserted_values(lead_sql, lead_params)
        self.assertEqual(saved["source"], "Сайт: партнерская заявка / new_channel")
        self.assertEqual(saved["utm_source"], "new_channel")
        self.assertEqual(saved["work_type"], "Поставщик")
        self.assertIn("UTM: utm_source=new_channel · utm_medium=telegram · utm_campaign=ads", saved["notes"])

    def test_notification_failure_still_saves_the_lead(self):
        statements = []
        app, connections = self._app(statements, _NotifyCursor)
        with unittest.mock.patch.dict("os.environ", {"LEAD_NOTIFY_TELEGRAM_CHAT_ID": "1001"}, clear=False):
            created = self._post(app, {
                "name": "Мария",
                "phone": "+79990000002",
                "consentAccepted": True,
                "utm": {"utm_source": "bloknot"},
            })
        self.assertEqual(created["id"], 501)
        self.assertEqual(connections[0].commits, 1)
        self.assertEqual(connections[0].rollbacks, 0)
        self.assertTrue(any(sql.startswith("ROLLBACK TO SAVEPOINT crm_lead_notify") for sql, _params in statements))


if __name__ == "__main__":
    unittest.main()
