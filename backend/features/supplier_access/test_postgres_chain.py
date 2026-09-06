"""Opt-in real PostgreSQL + authenticated HTTP supply chain, no real suppliers.

See docs/supply-request-current-chain.md for isolated database setup. This test
does not run against a production URL or substitute authorization dependencies.
"""

import datetime as dt
import os
import unittest


@unittest.skipUnless(os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
                     "Requires an explicitly provisioned isolated PostgreSQL database")
class PostgresSupplyChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.postgres_chain_fixture import build_fixture
        from fastapi.testclient import TestClient

        cls.main, cls.fixture, cls.cleanup = build_fixture()
        cls.addClassCleanup(cls.cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def api(self, actor, method, path, payload=None, expected=200, **extra_headers):
        token = self.main.create_auth_token(self.fixture["users"][actor], two_factor_passed=True)
        response = self.client.request(method, path, json=payload, headers={
            "Authorization": "Bearer " + token, **extra_headers,
        })
        self.assertEqual(response.status_code, expected,
                         (actor, method, path, response.status_code, response.text))
        return response.json()

    def sql(self, sql, params=()):
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def test_addressed_supplier_to_paid_invoice_and_exact_company_stock(self):
        f = self.fixture
        item = {key: f[key] for key in ("materialName", "quantity", "unit", "workPackage")}
        request = self.api("director", "POST", "/supply-requests", {
            "project": f["project"], "companyId": f["companyId"],
            "workPackage": f["workPackage"], "items": [item],
            "notes": "Isolated local chain; external network disabled",
        })
        request_id = request["id"]
        request_path = f"/supply-requests/{request_id}"
        self.assertEqual(self.sql(
            "SELECT status,prorab_confirmed_at,director_approved_at FROM supply_requests WHERE id=%s",
            (request_id,),
        ), [("Новая", None, None)])
        self.api("director", "POST", request_path + "/request-kp",
                 {"supplierIds": [f["supplierId"]]}, expected=400)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM supplier_offers WHERE request_id=%s", (request_id,)), [(0,)])
        self.api("foreman", "PUT", request_path, {"action": "confirm_prorab"})
        self.api("director", "PUT", request_path, {"action": "approve_director"})
        self.api("director", "POST", request_path + "/request-kp", {"supplierIds": [f["supplierId"]]})

        offers = self.api("supplier", "GET", "/supplier-offers")
        addressed = [row for row in offers if row["requestId"] == request_id]
        self.assertEqual(len(addressed), 1)
        offer_id = addressed[0]["id"]
        offer_path = f"/supplier-offers/{offer_id}"
        self.assertIn(request_id, [row["id"] for row in self.api("supplier", "GET", "/supply-requests")])
        self.assertNotIn(offer_id, [row["id"] for row in self.api("stranger", "GET", "/supplier-offers")])
        self.api("stranger", "PUT", offer_path, {"action": "respond", "totalPrice": 200}, expected=403)
        self.api("stranger_supplier", "PUT", offer_path,
                 {"action": "respond", "totalPrice": 200}, expected=403)

        # The supplier is not an employee of the customer. Billing must follow
        # the authorized offer, even when a different company header is sent.
        self.sql("UPDATE companies SET plan='business', plan_expires_at=%s, payment_status='active' WHERE id=%s",
                 (dt.date.today() - dt.timedelta(days=1), f["companyId"]))
        try:
            blocked = self.api("supplier", "PUT", offer_path, {"action": "respond"},
                               expected=403, **{"X-Company-Id": "1"})
            self.assertEqual(blocked["code"], "subscription_read_only")
            self.assertIn(offer_id, [row["id"] for row in self.api("supplier", "GET", "/supplier-offers")])
        finally:
            self.sql("UPDATE companies SET plan_expires_at=%s WHERE id=%s",
                     (dt.date.today() + dt.timedelta(days=30), f["companyId"]))

        self.api("supplier", "PUT", offer_path, {
            "action": "respond", "pricePerUnit": 100, "totalPrice": 200,
            "deliveryDays": 1, "paymentTerms": "Предоплата 100%", "vatIncluded": False,
            "itemsKp": [{**item, "pricePerUnit": 100, "totalPrice": 200, "deliveryDays": 1}],
        })
        self.api("director", "PUT", offer_path, {"action": "select"})
        invoice_payload = {"invoiceNumber": f"LOCAL-{request_id}", "invoiceDate": dt.date.today().isoformat(),
                           "amount": 200, "vatAmount": 0}
        invoice_id = self.api("supplier", "POST", offer_path + "/create-invoice", invoice_payload)["id"]
        replay = self.api("supplier", "POST", offer_path + "/create-invoice", invoice_payload)
        self.assertEqual(replay["id"], invoice_id)
        self.assertTrue(replay["alreadyExists"])
        ship = {"shippedQuantity": 2, "waybillNumber": f"LOCAL-{request_id}", "waybillDate": dt.date.today().isoformat()}
        self.api("supplier", "POST", offer_path + "/ship", ship, expected=400)
        self.api("accountant", "PUT", f"/supplier-invoices/{invoice_id}",
                 {"status": "Утверждён", "approvedBy": "Local finance"})
        self.api("accountant", "PUT", f"/supplier-invoices/{invoice_id}", {
            "status": "Оплачен", "paidAmount": 200, "paidAt": dt.date.today().isoformat(), "paidBy": "Local finance",
        })
        # Mirror the current finance UI's separate ledger request. This proves
        # its happy path, not atomicity across the two HTTP requests.
        payment = self.api("accountant", "POST", "/project-payments", {
            "projectName": f["project"], "workPackage": f["workPackage"], "amount": 200,
            "note": f"Оплата счёта LOCAL №LOCAL-{request_id}",
            "date": dt.date.today().isoformat(), "paidBy": "Local finance",
        })
        self.assertEqual(self.sql("SELECT company_id,amount FROM project_payments WHERE id=%s", (payment["id"],)),
                         [(f["companyId"], 200)])
        shipment = self.api("supplier", "POST", offer_path + "/ship", ship)
        delivery_id = shipment["id"]  # Single-line API returns the delivery itself.
        receipt = {"receivedQuantity": 2, "qualityStatus": "Принято", "receivedBy": "Local foreman"}
        receive_path = f"/supply-deliveries/{delivery_id}/receive"
        received = self.api("foreman", "PUT", receive_path, receipt)
        self.assertTrue(received["invoiceId"])
        replay = self.api("foreman", "PUT", receive_path, receipt)
        self.assertTrue(replay["alreadyReceived"])
        self.assertEqual(replay["invoiceId"], received["invoiceId"])
        self.assertEqual(self.sql("SELECT company_id,quantity FROM materials WHERE project=%s AND name=%s",
                                  (f["project"], f["materialName"])), [(f["companyId"], 2)])
        self.assertEqual(self.sql("SELECT company_id,status FROM supply_requests WHERE id=%s", (request_id,)),
                         [(f["companyId"], "Поставлено")])
        self.assertEqual(self.sql("SELECT company_id,status,paid_amount FROM supplier_invoices WHERE id=%s", (invoice_id,)),
                         [(f["companyId"], "Оплачен", 200)])
        self.assertEqual(self.sql("SELECT company_id,vat FROM warehouse_invoices WHERE supply_delivery_id=%s", (delivery_id,)),
                         [(f["companyId"], "Без НДС")])
        self.assertEqual(self.sql("SELECT company_id,quantity FROM warehouse_history WHERE source_type='supply_delivery' AND source_id=%s",
                                  (str(delivery_id),)), [(f["companyId"], 2)])


if __name__ == "__main__":
    unittest.main()
