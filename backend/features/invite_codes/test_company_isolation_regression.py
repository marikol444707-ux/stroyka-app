import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.features.invite_codes.routes import register_invite_codes_module


class FakeCursor:
    def __init__(self):
        self.last_query = ""
        self.last_params = ()
        self.inserted = None

    def execute(self, query, params=()):
        self.last_query = " ".join(str(query).split())
        self.last_params = params
        if self.last_query.startswith("INSERT INTO invite_codes"):
            self.inserted = params

    def fetchone(self):
        if self.last_query.startswith("SELECT platform_account_id FROM companies"):
            # Deliberately make the claimed foreign company exist. Existence is
            # not authorization.
            return {"platform_account_id": 50}
        if self.last_query.startswith("INSERT INTO invite_codes"):
            return {
                "id": 1,
                "code": "TESTCODE",
                "role": self.inserted[1],
                "company_id": self.inserted[-2],
                "platform_account_id": self.inserted[-1],
            }
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cur = FakeCursor()

    def cursor(self, **_kwargs):
        return self.cur

    def close(self):
        pass


class SupplierInviteCompanyIsolationRegression(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.user = {
            "id": 42,
            "role": "директор",
            "companyId": 7,
            "platformAccountId": 5,
        }

        def require_roles(*_roles):
            def dependency():
                return self.user
            return dependency

        def resolve_company(_cur, _user, requested_company_id=None, action_mode="read", **kwargs):
            self.assertEqual(action_mode, "create")
            header_id = kwargs.get("x_company_id")
            mode = kwargs.get("x_company_mode")
            if mode == "all_companies":
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="concrete company required")
            selected = int(header_id or requested_company_id or self.user["companyId"])
            if selected != self.user["companyId"]:
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Нет доступа к выбранной компании")
            return {
                "mode": "company",
                "companyId": selected,
                "platformAccountId": self.user["platformAccountId"],
                "effectiveRole": self.user["role"],
            }

        app = FastAPI()
        register_invite_codes_module(app, {
            "get_db": lambda: self.connection,
            "require_roles": require_roles,
            "admin_roles": ("директор",),
            "prepare_user_access_scope": (
                lambda _cur, _role, project_name, assigned_projects, assigned_packages:
                (assigned_projects or ([project_name] if project_name else []), assigned_packages or [])
            ),
            "resolve_work_company_context": resolve_company,
        })
        self.client = TestClient(app)

    def test_foreign_company_claim_is_rejected_not_looked_up_and_inserted(self):
        response = self.client.post("/invite-codes", json={
            "role": "поставщик",
            "companyId": 8,
            "platformAccountId": 999,
        })

        # Security contract: body companyId/platformAccountId are untrusted
        # claims. A director of company 7 must not mint an invite for company 8.
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.connection.cur.inserted)

    def test_selected_company_role_cannot_inherit_global_director(self):
        self.user["role"] = "прораб"
        response = self.client.post("/invite-codes", json={
            "role": "поставщик",
            "companyId": 7,
        })
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.connection.cur.inserted)

    def test_all_companies_write_fails_closed(self):
        response = self.client.post(
            "/invite-codes",
            headers={"X-Company-Mode": "all_companies"},
            json={"role": "поставщик"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.connection.cur.inserted)

    def test_body_platform_account_claim_is_ignored(self):
        response = self.client.post("/invite-codes", json={
            "role": "поставщик",
            "companyId": 7,
            "platformAccountId": 999,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["platform_account_id"], 5)

    def test_own_company_invite_remains_allowed(self):
        response = self.client.post("/invite-codes", json={
            "role": "поставщик",
            "companyId": 7,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["company_id"], 7)


if __name__ == "__main__":
    unittest.main()
