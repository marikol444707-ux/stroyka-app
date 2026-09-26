import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from .routes import register_supplier_deal_parties_module


OFFER = {'id': 40, 'company_id': 12, 'request_id': 20, 'supplier_id': 5,
         'project': 'Объект А', 'work_package': 'Основная', 'status': 'Утверждено'}
USER = {'id': 8, 'name': 'Анна', 'role': 'бухгалтер', 'companyId': 12}


class Cursor:
    def __init__(self, latest=None, deny_supplier=False):
        self.calls = []
        self.latest = latest
        self.row = None
        self.rows = []
        self.deny_supplier = deny_supplier

    def execute(self, sql, params=()):
        self.calls.append((' '.join(sql.split()), params))
        if 'FROM supplier_offers o' in sql:
            self.row = dict(OFFER)
        elif 'SELECT id FROM supplier_offers WHERE' in sql:
            self.row = None if self.deny_supplier else {'id': 40}
        elif 'FROM supplier_deal_parties' in sql:
            self.row = self.latest
            self.rows = [self.latest] if self.latest else []
        elif sql.lstrip().startswith('INSERT'):
            keys = ['offer_id','company_id','request_id','supplier_id','buyer_company_id',
                    'payer_company_id','version','reason','created_by_id','created_by']
            self.row = {**dict(zip(keys, params)), 'created_at': '2026-09-15'}
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class Connection:
    def __init__(self, cursor):
        self.cur = cursor
        self.commits = self.rollbacks = 0
        self.autocommit = True

    def cursor(self, **kwargs):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def build(*, user=None, latest=None, allowed=(12, 99), deny_supplier=False, deny_project=False):
    app = FastAPI()
    cursor = Cursor(latest, deny_supplier)
    conn = Connection(cursor)
    user = dict(user or USER)
    checks = []

    def resolve(cur, actor, company_id, mode, **kwargs):
        checks.append(company_id)
        if company_id not in allowed or actor.get('role') not in kwargs.get('allowed_roles', ()):
            raise HTTPException(403, 'Denied')
        return {'companyId': company_id}, {**actor, 'companyId': company_id}

    def project(*args):
        if deny_project:
            raise HTTPException(403, 'Denied project')

    register_supplier_deal_parties_module(app, {
        'get_db': lambda: conn, 'get_current_user': lambda: user,
        'resolve_resource_company_actor': resolve,
        'current_supplier_ids': lambda cur, actor: [5],
        'require_project_access': project,
        'has_package_access': lambda actor, package: True,
        'platform_staff_roles': (), 'client_account_roles': (),
    })
    return TestClient(app), cursor, conn, checks


class DealPartiesTest(unittest.TestCase):
    def test_create_keeps_source_owner_supplier_and_request(self):
        client, cursor, conn, checks = build()
        response = client.put('/supplier-offers/40/parties', json={
            'buyerCompanyId': 12, 'payerCompanyId': 99, 'expectedVersion': 0, 'reason': 'По договору'})
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()
        self.assertEqual((row['companyId'], row['requestId'], row['supplierId'], row['payerCompanyId']), (12,20,5,99))
        self.assertEqual(row['version'], 1)
        self.assertEqual(row['status'], 'draft')
        self.assertIn(99, checks)
        self.assertEqual(conn.commits, 1)
        self.assertFalse(any(sql.startswith('UPDATE') for sql, _ in cursor.calls))

    def test_foreign_payer_is_not_authorized_by_being_selected(self):
        client, cursor, conn, _ = build(allowed=(12,))
        response = client.put('/supplier-offers/40/parties', json={
            'buyerCompanyId':12, 'payerCompanyId':99, 'expectedVersion':0, 'reason':'Плательщик'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(conn.commits, 0)
        self.assertFalse(any(sql.startswith('INSERT') for sql, _ in cursor.calls))

    def test_supplier_cannot_change_parties(self):
        client, cursor, conn, _ = build(user={**USER, 'role':'поставщик'})
        response = client.put('/supplier-offers/40/parties', json={
            'buyerCompanyId':12, 'payerCompanyId':99, 'expectedVersion':0, 'reason':'Подмена'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(conn.commits, 0)

    def test_stale_version_has_no_write(self):
        client, cursor, conn, _ = build(latest={'version':2})
        response = client.put('/supplier-offers/40/parties', json={
            'buyerCompanyId':12, 'payerCompanyId':99, 'expectedVersion':1, 'reason':'Изменение'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(conn.commits, 0)

    def test_owner_and_supplier_cannot_be_overridden_in_body(self):
        client, *_ = build()
        response = client.put('/supplier-offers/40/parties', json={
            'companyId':99,'supplierId':6,'buyerCompanyId':12, 'payerCompanyId':12,
            'expectedVersion':0,'reason':'Подмена'})
        self.assertEqual(response.status_code, 422)

    def test_project_restriction_is_checked(self):
        client, *_ = build(deny_project=True)
        self.assertEqual(client.get('/supplier-offers/40/parties').status_code, 403)

    def test_supplier_read_reuses_offer_disclosure_guard(self):
        client, *_ = build(user={**USER,'role':'поставщик'}, deny_supplier=True)
        self.assertEqual(client.get('/supplier-offers/40/parties').status_code, 403)

    def test_get_without_draft_does_not_invent_agreed_payer(self):
        client, *_ = build()
        response = client.get('/supplier-offers/40/parties')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['version'], 0)
        self.assertIsNone(response.json()['payerCompanyId'])
