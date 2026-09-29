import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from backend.features.supplier_offers import test_response_postgres as support

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Requires isolated PostgreSQL')
class ResponseDeadlinesPostgresTests(unittest.TestCase):
    setUpClass=classmethod(support.SupplierResponsePostgresTests.setUpClass.__func__)
    api=support.SupplierResponsePostgresTests.api
    sql=support.SupplierResponsePostgresTests.sql
    quote=support.SupplierResponsePostgresTests.quote
    def test_default_is_persisted_scoped_and_not_extended_by_retry(self):
        due=datetime(2030,9,23,11,0,tzinfo=timezone.utc)
        with patch.object(self.main,'response_deadline',return_value=due):offer,_,_=self.quote()
        self.assertEqual(datetime.fromisoformat(offer['responseDueAt']),due)
        path='/supply-requests/'+str(offer['requestId'])+'/request-kp'
        result=self.api('director','POST',path,{'supplierIds':[self.fixture['supplierId']],'responseDueAt':'2031-09-23T14:00:00+03:00'})
        self.assertEqual(result['created'],0)
        self.assertEqual(self.sql('SELECT response_due_at FROM supplier_offers WHERE id=%s',(offer['id'],)),[(due,)])
        self.assertEqual(self.api('stranger_supplier','GET','/supplier-offers'),[])
    def test_invalid_new_deadline_rolls_back_quotes_and_recipients(self):
        f=self.fixture
        request=self.api('director','POST','/supply-requests',{'project':f['project'],'companyId':f['companyId'],'workPackage':f['workPackage'],'items':[{**{k:f[k] for k in ('materialName','unit','workPackage')},'quantity':1}]})
        path='/supply-requests/'+str(request['id'])
        self.api('foreman','PUT',path,{'action':'confirm_prorab'})
        self.api('director','PUT',path,{'action':'approve_director'})
        self.api('director','POST',path+'/request-kp',{'supplierIds':[f['supplierId']],'responseDueAt':'2000-01-01T00:00:00Z'},expected=400)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_offers WHERE request_id=%s',(request['id'],)),[(0,)])
        self.assertEqual(self.sql('SELECT count(*) FROM supply_request_recipients WHERE request_id=%s',(request['id'],)),[(0,)])
        self.api('director','POST',path+'/request-kp',{'supplierIds':[f['supplierId']],'responseDueAt':'2031-09-23T14:00:00+03:00'})
        self.assertEqual(self.sql('SELECT response_due_at FROM supplier_offers WHERE request_id=%s',(request['id'],)),[(datetime(2031,9,23,11,tzinfo=timezone.utc),)])
    def test_migration_keeps_legacy_without_deadline_and_refuses_data_loss(self):
        import importlib
        from types import SimpleNamespace
        migration=importlib.import_module('migrations.versions.0034_supplier_response_due')
        conn=self.main.get_db();conn.autocommit=False
        try:
            with conn.cursor() as cur:
                cur.execute('CREATE TEMP TABLE supplier_offers(id INTEGER)')
                cur.execute('INSERT INTO supplier_offers VALUES(1)')
                with patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                    migration.upgrade();migration.upgrade()
                    cur.execute('SELECT response_due_at FROM supplier_offers')
                    self.assertEqual(cur.fetchall(),[(None,)])
                    cur.execute('UPDATE supplier_offers SET response_due_at=NOW()')
                    with self.assertRaisesRegex(Exception,'Cannot discard recorded'):
                        migration.downgrade()
        finally:conn.rollback();conn.close()
