import asyncio
import io
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
        document_insert = next(
            params for query, params in statements
            if query.startswith("INSERT INTO crm_lead_documents")
        )
        self.assertEqual(document_insert[0], 501)
        self.assertEqual(document_insert[2], "/tenant-files/71/content")
        self.assertTrue(all(connection.rollbacks == 0 for connection in connections))


if __name__ == "__main__":
    unittest.main()
