"""Journal tests use only the deployed schema plus the journal owner migration."""
import os
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from .test_owner_migration import load_migration


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
                     'Requires an explicit fresh socket-only PostgreSQL database')
class OwnerStockPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        migration = load_migration()
        conn = cls.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor() as cur:
                cls.main._ensure_journal_source_columns(cur)
                with patch.object(migration, 'op', SimpleNamespace(execute=cur.execute)):
                    migration.upgrade()
        finally:
            conn.close()

    def sql(self, statement, params=()):
        conn = self.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(statement, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def setUp(self):
        from psycopg2.extras import Json, RealDictCursor
        self.f = dict(self.fixture, users=dict(self.fixture['users']))
        suffix = uuid4().hex[:10]
        self.f['project'] = 'Journal project ' + suffix
        self.f['materialName'] = 'Journal material ' + suffix
        self.f['projectId'] = self.sql('INSERT INTO projects(name,company_id) VALUES(%s,2) RETURNING id',
                                      (self.f['project'],))[0][0]
        sections = [{'name': 'Основная', 'items': [{'id': suffix, 'name': self.f['materialName'],
            'type': 'material', 'itemType': 'material', 'unit': 'шт', 'quantity': 20,
            'price': 100, 'priceMaterial': 100, 'lineTotal': 2000, 'workPackage': 'Основная'}]}]
        self.sql('''INSERT INTO estimates(company_id,project_id,project_name,name,version,
            sections_json,status,is_template,smeta_type,work_package)
            VALUES(2,%s,%s,'Journal estimate','1',%s,'Активная',FALSE,'Заказчик','Основная')''',
            (self.f['projectId'],self.f['project'],json.dumps(sections,ensure_ascii=False)))
        foreman = self.f['users']['foreman']['id']
        self.sql('UPDATE users SET assigned_projects=%s WHERE id=%s', (Json([self.f['project']]), foreman))
        self.sql('UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s AND company_id=2',
                 (Json([self.f['project']]), foreman))
        worker = self.sql('''INSERT INTO users(name,email,password,role,active,company_id,assigned_projects,assigned_packages)
            VALUES('Journal worker',%s,'disabled','мастер',TRUE,2,%s,%s) RETURNING id''',
            (suffix+'@synthetic.invalid',Json([self.f['project']]),Json(['Основная'])))[0][0]
        self.sql('''INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,
            assigned_projects,assigned_packages,active,is_default)
            VALUES(%s,2,1,'мастер',%s,%s,TRUE,TRUE)''', (worker,Json([self.f['project']]),Json(['Основная'])))
        conn = self.main.get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT * FROM users WHERE id=%s',(worker,))
                self.f['users']['worker']=dict(cur.fetchone())
        finally:
            conn.close()

    def request(self, method, path, data, actor='director', **headers):
        from fastapi.testclient import TestClient
        token = self.main.create_auth_token(self.f['users'][actor], two_factor_passed=True)
        with TestClient(self.main.app, raise_server_exceptions=False) as client:
            return client.request(method,path,json=data,headers={'Authorization':'Bearer '+token,**headers})

    def api(self, actor, method, path, payload=None, expected=200, **headers):
        response = self.request(method,path,payload,actor,**headers)
        self.assertEqual(response.status_code,expected,response.text)
        return response.json()

    def wait_blocked(self, query_fragment, count=1):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            rows=self.sql("""SELECT pid FROM pg_stat_activity WHERE datname=current_database()
                AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE %s""", ('%'+query_fragment+'%',))
            if len(rows)>=count:
                return rows
            time.sleep(.02)
        self.fail('Expected blocked query '+query_fragment)

    def receipt_payload(self, quantity=2):
        return dict(companyId=2,location='Основной склад',warehouseTarget='main',inventoryOnly=True,
            number='Journal-'+uuid4().hex,date='2026-09-18',items=[dict(name=self.f['materialName'],
            materialName=self.f['materialName'],unit='шт',quantity=quantity,price=100,workPackage='Основная')])

    def finances(self, allow_receipt_link=False):
        return [self.sql('SELECT * FROM '+table+' ORDER BY id') for table in ('supplier_invoices','project_payments')]

    def prepare_supplier_delivery(self):
        """Create the actual addressed request, offer, invoice and shipment via HTTP."""
        item = dict(materialName=self.f['materialName'], quantity=2, unit='шт', workPackage='Основная')
        rid = self.api('director', 'POST', '/supply-requests', dict(companyId=2,
            project=self.f['project'], workPackage='Основная', items=[item]))['id']
        path = '/supply-requests/'+str(rid)
        self.api('foreman', 'PUT', path, {'action': 'confirm_prorab'})
        self.api('director', 'PUT', path, {'action': 'approve_director'})
        self.api('director', 'POST', path+'/request-kp', {'supplierIds': [self.f['supplierId']]})
        offer = next(r for r in self.api('supplier', 'GET', '/supplier-offers') if r['requestId'] == rid)
        path = '/supplier-offers/'+str(offer['id'])
        self.api('supplier', 'PUT', path, dict(action='respond', pricePerUnit=100, totalPrice=200,
            deliveryDays=1, paymentTerms='Предоплата 100%', vatIncluded=False,
            itemsKp=[dict(item, pricePerUnit=100, totalPrice=200, deliveryDays=1)]))
        self.api('director', 'PUT', path, {'action': 'select'})
        invoice = self.api('supplier', 'POST', path+'/create-invoice',
            dict(invoiceNumber='CHAIN-'+str(rid), invoiceDate='2026-09-16', amount=200, vatAmount=0))['id']
        self.api('accountant', 'PUT', '/supplier-invoices/'+str(invoice), {'status': 'Утверждён'})
        self.api('accountant', 'PUT', '/supplier-invoices/'+str(invoice),
                 dict(status='Оплачен', paidAmount=200, paidAt='2026-09-16'))
        delivery = self.api('supplier', 'POST', path+'/ship',
            dict(shippedQuantity=2, waybillNumber='SHIP-'+str(rid), waybillDate='2026-09-16'))['id']
        return delivery, invoice
