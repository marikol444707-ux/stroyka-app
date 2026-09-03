import asyncio
import io
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from backend.features.platform_admin import client_contract_routes, routes
from backend.features.platform_admin.client_contracts import normalize_legal_party


class FakeApp:
    def __init__(self):
        self.handlers = {}

    def _decorator(self, method, path):
        def register(function):
            self.handlers[(method, path)] = function
            return function

        return register

    def get(self, path, **_kwargs):
        return self._decorator("GET", path)

    def post(self, path, **_kwargs):
        return self._decorator("POST", path)

    def put(self, path, **_kwargs):
        return self._decorator("PUT", path)


class FakeCursor:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.current = None
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.results.pop(0) if self.results else None

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current.pop(0) if self.current else None
        value = self.current
        self.current = None
        return value

    def fetchall(self):
        if self.current is None:
            return []
        if isinstance(self.current, list):
            value = self.current
        else:
            value = [self.current]
        self.current = None
        return value

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, results=None):
        self.cursor_instance = FakeCursor(results)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def company_row(**overrides):
    row = {
        "id": 42,
        "platform_account_id": 3,
        "active": True,
        "legal_name": "ООО Клиент",
        "short_name": "ООО Клиент",
        "inn": "2635000000",
        "kpp": "263501001",
        "ogrn": "1022600000000",
        "legal_address": "г. Ставрополь",
        "phone": "+79000000000",
        "email": "director@example.test",
        "settlement_account": "40702810000000000001",
        "bank_name": "Банк клиента",
        "bank_bik": "040000002",
        "correspondent_account": "30101810000000000002",
        "signatory_name": "Иванов Иван Иванович",
        "signatory_basis": "Устав",
        "plan": "pro",
        "monthly_fee": None,
        "max_projects": None,
        "max_users": None,
    }
    row.update(overrides)
    return row


def licensor_row(**overrides):
    row = {
        "id": 7,
        "platform_account_id": 3,
        "active": True,
        "legal_form": "individual_entrepreneur",
        "legal_name": "ИП Буцькин Николай Сергеевич",
        "short_name": "ИП Буцькин",
        "inn": "261103507630",
        "kpp": "",
        "ogrn": "",
        "ogrnip": "309264413800022",
        "legal_address": "Ставропольский край",
        "phone": "+79097638505",
        "email": "owner@example.test",
        "settlement_account": "40802810000000000001",
        "bank_name": "Тестовый банк",
        "bank_bik": "040000001",
        "correspondent_account": "30101810000000000001",
        "signatory_name": "Буцькин Николай Сергеевич",
        "signatory_basis": "записи в ЕГРИП",
    }
    row.update(overrides)
    return row


def contract_row(**overrides):
    row = {
        "id": 101,
        "platform_account_id": 3,
        "company_id": 42,
        "licensor_profile_id": 7,
        "idempotency_key": "contract-42-2026",
        "request_fingerprint": "a" * 64,
        "contract_type": "platform_license",
        "number": "STK-2026-0101",
        "contract_date": "2026-09-02",
        "starts_on": "2026-09-02",
        "ends_on": None,
        "plan": "pro",
        "monthly_fee": "49900.00",
        "currency": "RUB",
        "max_projects": 10,
        "max_users": 40,
        "status": "draft",
        "terms_version": "platform-license-v1",
        "licensor_snapshot_json": normalize_legal_party(licensor_row()),
        "client_snapshot_json": normalize_legal_party(company_row()),
        "terms_snapshot_json": {
            "plan": "pro",
            "monthlyFee": "49900.00",
            "currency": "RUB",
            "maxProjects": 10,
            "maxUsers": 40,
            "startsOn": "2026-09-02",
            "endsOn": None,
        },
        "generated_file_url": None,
        "signed_file_url": None,
        "notes": None,
        "issued_at": None,
        "activated_at": None,
        "terminated_at": None,
        "created_at": "2026-09-02T00:00:00",
        "updated_at": "2026-09-02T00:00:00",
    }
    row.update(overrides)
    return row


def payload(**overrides):
    value = {
        "companyId": 42,
        "idempotencyKey": "contract-42-2026",
        "contractDate": "2026-09-02",
        "startsOn": "2026-09-02",
    }
    value.update(overrides)
    return value


def register_handlers(connection, save_upload_bytes=None):
    app = FakeApp()
    role_requests = []

    def require_roles(*roles):
        role_requests.append(roles)
        return lambda: {}

    client_contract_routes.register_client_contract_routes(app, {
        "get_db": lambda: connection,
        "require_roles": require_roles,
        "view_roles": routes.PLATFORM_VIEW_ROLES,
        "manage_roles": routes.PLATFORM_MANAGE_ROLES,
        "tariff_for_plan": lambda _plan: {
            "id": "pro",
            "monthlyFee": 49900,
            "maxProjects": 10,
            "maxUsers": 40,
        },
        "write_audit": lambda *args, **kwargs: routes._system_write_audit(
            *args, **kwargs
        ),
        "save_upload_bytes": save_upload_bytes,
    })
    return app.handlers, role_requests


class ClientContractRoutesTests(unittest.TestCase):
    def test_contract_response_never_exposes_direct_storage_urls(self):
        response = client_contract_routes._contract_response(contract_row(
            generated_file_url="https://storage.example/private/generated.pdf",
            signed_file_url="https://storage.example/private/signed.pdf",
        ))

        self.assertIsNone(response["generatedFileUrl"])
        self.assertIsNone(response["signedFileUrl"])

    def test_list_returns_only_contracts_owned_by_company_account(self):
        connection = FakeConnection([
            company_row(),
            [contract_row()],
        ])
        handlers, role_requests = register_handlers(connection)

        result = handlers[("GET", "/system/client-contracts")](
            companyId=42,
            _current_user={"id": 1, "role": "platform_support"},
        )

        self.assertEqual(result["companyId"], 42)
        self.assertEqual(result["platformAccountId"], 3)
        self.assertEqual(result["items"][0]["number"], "STK-2026-0101")
        self.assertIn(routes.PLATFORM_VIEW_ROLES, role_requests)
        contract_sql, contract_params = connection.cursor_instance.calls[1]
        self.assertIn("platform_account_id=%s AND company_id=%s", contract_sql)
        self.assertEqual(contract_params, (3, 42))

    def test_preview_autofills_account_licensor_and_tariff_without_writes(self):
        connection = FakeConnection([
            company_row(),
            licensor_row(),
            [],
        ])
        handlers, role_requests = register_handlers(connection)

        result = handlers[("POST", "/system/client-contracts/preview")](
            payload(),
            {"id": 1, "role": "system_owner"},
        )

        self.assertTrue(result["readyForDraft"])
        self.assertEqual(result["contract"]["platformAccountId"], 3)
        self.assertEqual(result["contract"]["licensorProfileId"], 7)
        self.assertEqual(result["contract"]["plan"], "pro")
        self.assertEqual(result["contract"]["monthlyFee"], "49900.00")
        self.assertEqual(result["contract"]["maxUsers"], 40)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(connection.commits, 0)
        self.assertIn(routes.PLATFORM_MANAGE_ROLES, role_requests)

    def test_preview_explains_missing_licensor_profile(self):
        connection = FakeConnection([
            company_row(),
            None,
            [],
        ])
        handlers, _role_requests = register_handlers(connection)

        result = handlers[("POST", "/system/client-contracts/preview")](
            payload(),
            {"id": 1, "role": "system_owner"},
        )

        self.assertFalse(result["readyForDraft"])
        codes = {item["code"] for item in result["blockers"]}
        self.assertIn("licensor_profile_required", codes)
        self.assertIn("licensor_legal_name_required", codes)

    def test_create_writes_one_draft_and_audit_but_no_payment(self):
        created = contract_row(request_fingerprint="b" * 64)
        connection = FakeConnection([
            company_row(),
            licensor_row(),
            [],
            {"id": 101},
            created,
        ])
        handlers, _role_requests = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("POST", "/system/client-contracts")](
                payload(),
                {"id": 1, "name": "Владелец", "role": "system_owner"},
            )

        self.assertTrue(result["created"])
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["contract"]["status"], "draft")
        self.assertEqual(connection.commits, 1)
        insert_sql = connection.cursor_instance.calls[4][0]
        self.assertIn("INSERT INTO platform_client_contracts", insert_sql)
        all_sql = " ".join(sql for sql, _params in connection.cursor_instance.calls)
        self.assertNotIn("company_payments", all_sql)
        self.assertNotIn("platform_billing_documents", all_sql)
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[2], "platform_client_contract_created")

    def test_repeated_create_returns_existing_contract_without_insert(self):
        existing = contract_row(request_fingerprint=None)
        connection = FakeConnection([
            company_row(),
            licensor_row(),
            [existing],
        ])
        handlers, _role_requests = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("POST", "/system/client-contracts")](
                payload(),
                {"id": 1, "role": "system_owner"},
            )

        self.assertFalse(result["created"])
        self.assertTrue(result["idempotent"])
        self.assertEqual(result["contract"]["id"], 101)
        self.assertFalse(any(
            "INSERT INTO platform_client_contracts" in sql
            for sql, _params in connection.cursor_instance.calls
        ))
        self.assertEqual(connection.commits, 0)
        audit.assert_not_called()

    def test_create_refuses_incomplete_client_without_writing(self):
        connection = FakeConnection([
            company_row(settlement_account="", bank_name=""),
            licensor_row(),
            [],
        ])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("POST", "/system/client-contracts")](
                payload(),
                {"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any(
            "INSERT INTO platform_client_contracts" in sql
            for sql, _params in connection.cursor_instance.calls
        ))
        self.assertEqual(connection.commits, 0)

    def test_create_rejects_active_status_before_opening_transaction(self):
        connection = FakeConnection()
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("POST", "/system/client-contracts")](
                payload(status="active"),
                {"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(connection.cursor_instance.calls, [])

    def test_status_change_uses_manage_role_writes_audit_and_no_payment(self):
        source = contract_row(
            status="issued",
            generated_file_url="/tenant-files/501/content",
            signed_file_url="/tenant-files/502/content",
        )
        updated = contract_row(
            status="active",
            generated_file_url="/tenant-files/501/content",
            signed_file_url="/tenant-files/502/content",
            activated_at="2026-09-03T12:00:00",
        )
        connection = FakeConnection([source, {"id": 42}, [source], updated])
        handlers, role_requests = register_handlers(connection)

        with patch.object(routes, "_system_write_audit") as audit:
            result = handlers[("PUT", "/system/client-contracts/{contract_id}")](
                contract_id=101,
                data={"status": "active", "reason": "Подписан обеими сторонами"},
                current_user={"id": 1, "name": "Владелец", "role": "system_owner"},
            )

        self.assertTrue(result["changed"])
        self.assertEqual(result["contract"]["status"], "active")
        self.assertIn(routes.PLATFORM_MANAGE_ROLES, role_requests)
        all_sql = " ".join(sql for sql, _params in connection.cursor_instance.calls)
        self.assertIn(
            "SELECT id FROM companies WHERE id=%s AND platform_account_id=%s FOR UPDATE",
            all_sql,
        )
        self.assertIn("UPDATE platform_client_contracts", all_sql)
        self.assertNotIn("DELETE FROM", all_sql)
        self.assertNotIn("company_payments", all_sql)
        self.assertEqual(connection.commits, 1)
        audit.assert_called_once()
        self.assertEqual(
            audit.call_args.args[2],
            "platform_client_contract_status_changed",
        )
        self.assertEqual(audit.call_args.kwargs["details"]["fromStatus"], "issued")
        self.assertEqual(audit.call_args.kwargs["details"]["toStatus"], "active")

    def test_status_change_rejects_unsigned_activation_without_write(self):
        connection = FakeConnection([
            contract_row(
                status="issued",
                generated_file_url="/tenant-files/501/content",
            ),
            {"id": 42},
            [contract_row(status="issued")],
        ])
        handlers, _role_requests = register_handlers(connection)

        with self.assertRaises(HTTPException) as raised:
            handlers[("PUT", "/system/client-contracts/{contract_id}")](
                contract_id=101,
                data={"status": "active"},
                current_user={"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(connection.commits, 0)
        self.assertFalse(any(
            "UPDATE platform_client_contracts" in sql
            for sql, _params in connection.cursor_instance.calls
        ))

    def test_preview_rejects_supplied_foreign_platform_account(self):
        connection = FakeConnection([
            company_row(),
            licensor_row(),
            [],
        ])
        handlers, _role_requests = register_handlers(connection)

        result = handlers[("POST", "/system/client-contracts/preview")](
            payload(platformAccountId=99),
            {"id": 1, "role": "system_owner"},
        )

        self.assertIn(
            "company_platform_account_mismatch",
            {item["code"] for item in result["blockers"]},
        )

    def test_preview_detects_idempotency_key_used_by_another_company(self):
        connection = FakeConnection([
            company_row(),
            licensor_row(),
            [contract_row(company_id=77)],
        ])
        handlers, _role_requests = register_handlers(connection)

        result = handlers[("POST", "/system/client-contracts/preview")](
            payload(),
            {"id": 1, "role": "system_owner"},
        )

        self.assertIn(
            "idempotency_key_conflict",
            {item["code"] for item in result["blockers"]},
        )
        preview_sql, preview_params = connection.cursor_instance.calls[2]
        self.assertIn("company_id=%s OR idempotency_key=%s", preview_sql)
        self.assertEqual(preview_params, (3, 42, "contract-42-2026"))

    def test_generate_pdf_registers_private_company_file_without_payment_write(self):
        generated_url = "/tenant-files/501/content"
        updated = contract_row(generated_file_url=generated_url)
        connection = FakeConnection([
            contract_row(),
            {"id": 501},
            updated,
        ])
        saved_calls = []

        def save_upload_bytes(*args, **kwargs):
            saved_calls.append((args, kwargs))
            return {
                "url": "https://storage.example/private/object.pdf",
                "storage": "s3",
                "key": "uploads/company-42-common-platform-client-contract/object.pdf",
                "filename": args[1],
            }

        handlers, _role_requests = register_handlers(connection, save_upload_bytes)

        with patch.object(
            client_contract_routes,
            "render_client_contract_pdf",
        ) as render_pdf, patch.object(routes, "_system_write_audit") as audit:
            render_pdf.return_value.content = b"%PDF-1.7\ncontract"
            render_pdf.return_value.filename = "STK-2026-0101.pdf"
            result = handlers[(
                "POST",
                "/system/client-contracts/{contract_id}/generate-pdf",
            )](
                contract_id=101,
                current_user={"id": 1, "name": "Владелец", "role": "system_owner"},
            )

        self.assertTrue(result["generated"])
        self.assertEqual(result["fileUrl"], generated_url)
        self.assertEqual(result["contract"]["generatedFileUrl"], generated_url)
        self.assertEqual(saved_calls[0][0][0], b"%PDF-1.7\ncontract")
        self.assertEqual(saved_calls[0][0][2], "company-42-common-platform-client-contract")
        self.assertEqual(saved_calls[0][0][3], "platform-client-contract")
        self.assertEqual(saved_calls[0][0][4], "application/pdf")
        self.assertEqual(saved_calls[0][0][5], "")
        sql = " ".join(item[0] for item in connection.cursor_instance.calls)
        self.assertIn("INSERT INTO file_ownership", sql)
        self.assertNotIn("company_payments", sql)
        self.assertNotIn("platform_billing_documents", sql)
        self.assertEqual(connection.commits, 1)
        audit.assert_called_once()

    def test_generate_pdf_is_idempotent_after_file_exists(self):
        existing = contract_row(generated_file_url="/tenant-files/501/content")
        connection = FakeConnection([existing])
        saver = unittest.mock.Mock()
        handlers, _role_requests = register_handlers(connection, saver)

        result = handlers[(
            "POST",
            "/system/client-contracts/{contract_id}/generate-pdf",
        )](
            contract_id=101,
            current_user={"id": 1, "role": "system_owner"},
        )

        self.assertFalse(result["generated"])
        self.assertEqual(result["fileUrl"], "/tenant-files/501/content")
        saver.assert_not_called()
        self.assertEqual(connection.commits, 0)

    def test_generate_pdf_refuses_to_expose_invalid_existing_file_url(self):
        existing = contract_row(
            generated_file_url="https://storage.example/private/object.pdf",
        )
        connection = FakeConnection([existing])
        saver = unittest.mock.Mock()
        handlers, _role_requests = register_handlers(connection, saver)

        with self.assertRaises(HTTPException) as raised:
            handlers[(
                "POST",
                "/system/client-contracts/{contract_id}/generate-pdf",
            )](
                contract_id=101,
                current_user={"id": 1, "role": "system_owner"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        saver.assert_not_called()
        self.assertEqual(connection.commits, 0)

    def test_signed_pdf_is_registered_once_without_changing_contract_status(self):
        generated_url = "/tenant-files/501/content"
        signed_url = "/tenant-files/502/content"
        updated = contract_row(
            generated_file_url=generated_url,
            signed_file_url=signed_url,
        )
        connection = FakeConnection([
            contract_row(generated_file_url=generated_url),
            {"id": 502},
            updated,
        ])
        saved_calls = []

        def save_upload_bytes(*args, **kwargs):
            saved_calls.append((args, kwargs))
            return {
                "url": "https://storage.example/private/signed.pdf",
                "storage": "s3",
                "key": "uploads/company-42-common-platform-client-contract/signed.pdf",
                "filename": args[1],
            }

        handlers, _role_requests = register_handlers(connection, save_upload_bytes)
        upload = UploadFile(
            file=io.BytesIO(b"%PDF-1.7\nsigned"),
            filename="signed-contract.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )

        with patch.object(routes, "_system_write_audit") as audit:
            result = asyncio.run(handlers[(
                "POST",
                "/system/client-contracts/{contract_id}/signed-file",
            )](
                contract_id=101,
                file=upload,
                current_user={"id": 1, "name": "Владелец", "role": "system_owner"},
            ))

        self.assertTrue(result["uploaded"])
        self.assertEqual(result["fileUrl"], signed_url)
        self.assertEqual(result["contract"]["status"], "draft")
        self.assertEqual(result["contract"]["signedFileUrl"], signed_url)
        self.assertEqual(saved_calls[0][0][0], b"%PDF-1.7\nsigned")
        sql = " ".join(item[0] for item in connection.cursor_instance.calls)
        self.assertNotIn("company_payments", sql)
        self.assertNotIn("platform_billing_documents", sql)
        self.assertEqual(connection.commits, 1)
        audit.assert_called_once()

    def test_signed_pdf_requires_generated_contract_and_never_overwrites(self):
        for source, detail in (
            (contract_row(), "Сначала сформируйте PDF договора."),
            (
                contract_row(
                    generated_file_url="/tenant-files/501/content",
                    signed_file_url="/tenant-files/502/content",
                ),
                "Подписанный файл уже загружен.",
            ),
        ):
            with self.subTest(detail=detail):
                connection = FakeConnection([source])
                handlers, _role_requests = register_handlers(
                    connection,
                    unittest.mock.Mock(),
                )
                upload = UploadFile(
                    file=io.BytesIO(b"%PDF-1.7\nsigned"),
                    filename="signed-contract.pdf",
                    headers=Headers({"content-type": "application/pdf"}),
                )

                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(handlers[(
                        "POST",
                        "/system/client-contracts/{contract_id}/signed-file",
                    )](
                        contract_id=101,
                        file=upload,
                        current_user={"id": 1, "role": "system_owner"},
                    ))

                self.assertEqual(raised.exception.status_code, 409)
                self.assertEqual(raised.exception.detail, detail)
                self.assertEqual(connection.commits, 0)


if __name__ == "__main__":
    unittest.main()
