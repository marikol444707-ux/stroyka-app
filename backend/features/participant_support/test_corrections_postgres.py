"""Correct an unused connection only; retain both companies' business history."""
import importlib
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from psycopg2.errors import RaiseException, CheckViolation

from .test_correction_preview_postgres import SupplierCorrectionPreviewPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupplierCorrectionsPostgresTests(unittest.TestCase):
    sql, api, connection = Base.sql, Base.api, Base.connection

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)
        from ..supplier_deal_parties.test_migration import migration_statements
        from ..supplier_deal_parties.test_contract_postgres import statements
        for statement in (migration_statements('upgrade')+statements('upgrade')+
                          statements('upgrade','0064_supplier_contract_registry.py')+
                          statements('upgrade','0067_supplier_contract_originals.py')):
            cls.sql(cls,statement)
        cls.sql(cls,importlib.import_module('migrations.versions.0099_supplier_connection_corrections').SCHEMA_SQL)
        patch.dict(os.environ,PARTICIPANT_CORRECTIONS_ENABLED='1').start()

    def path(self, source, request, company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{request}/correction-plans'

    def plan(self, source, request, **kwargs):
        return self.api('admin','POST',self.path(source,request),dict(operationId=str(uuid.uuid4())),**kwargs)

    def confirm(self, source, request, plan, reason='Synthetic mistaken buyer connection', **kwargs):
        return self.api('admin','POST',self.path(source,request)+'/'+plan['id']+'/confirm',dict(confirmed=True,reason=reason),**kwargs)

    def test_00_empty_migration_replay_downgrade_and_no_business_backfill(self):
        migration=importlib.import_module('migrations.versions.0099_supplier_connection_corrections')
        conn=self.main.get_db()
        try:
            with conn,conn.cursor() as cur,patch.object(migration,'op',SimpleNamespace(execute=cur.execute)):
                migration.downgrade();migration.upgrade();migration.upgrade()
        finally:conn.close()
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_connection_correction_plans'),[(0,)])

    def test_exact_empty_connection_disables_only_target_link_and_keeps_receipt_history(self):
        source,target,request=self.connection()
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,400,100),(3,%s,999,50)',(source,target))
        before={t:self.sql('SELECT to_jsonb(t) FROM '+t+' t ORDER BY id') for t in
                ('suppliers','users','supplier_invoices','supplier_buyer_connection_requests')}
        foreign=self.sql('SELECT to_jsonb(l) FROM company_supplier_links l WHERE company_id=3 ORDER BY id')
        plan=self.plan(source,request)
        self.assertEqual(plan['companyId'],2)
        self.assertEqual(plan['targetId'],target)
        self.assertEqual(plan['retainedDocuments']['invoices'],1)
        self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',)])
        result=self.confirm(source,request,plan)
        self.assertTrue(result['ok'])
        self.assertEqual(result['relationshipStatus'],'Неактивный')
        self.assertEqual(self.confirm(source,request,plan),result)
        self.assertEqual(self.sql('SELECT status,version FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Неактивный',2)])
        for table,rows in before.items():self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))
        self.assertEqual(foreign,self.sql('SELECT to_jsonb(l) FROM company_supplier_links l WHERE company_id=3 ORDER BY id'))
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_connection_corrected' AND company_id=2 AND entity_id=%s",(target,)),[(1,)])
        listing=self.api('admin','GET',self.path(source,request).rsplit('/',2)[0])
        self.assertEqual(next(r for r in listing['items'] if r['id']==request)['correctionStatus'],'disconnected')
        from ..supplier_access.procurement_scope import explicit_supplier_targets
        conn=self.main.get_db()
        try:
            from psycopg2.extras import RealDictCursor
            from fastapi import HTTPException
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                with self.assertRaises(HTTPException) as failure:explicit_supplier_targets(cur,2,[target])
                self.assertEqual(failure.exception.status_code,409)
        finally:conn.close()

    def test_target_history_recipients_assignments_and_unassigned_records_block(self):
        for table in ('supplier_invoices','warehouse_invoices','supplier_offers'):
            source,target,request=self.connection()
            self.sql('INSERT INTO '+table+'(company_id,supplier_id) VALUES(2,%s)',(target,))
            self.plan(source,request,expected=409)
        source,target,request=self.connection()
        self.sql("INSERT INTO supply_requests(company_id,material_name,selected_suppliers) VALUES(2,'Synthetic addressed request',%s)",([target],))
        self.plan(source,request,expected=409)
        source,target,request=self.connection()
        self.sql('INSERT INTO supplier_customer_assignments(supplier_id,company_id) VALUES(%s,2)',(target,))
        self.plan(source,request,expected=409)
        source,target,request=self.connection()
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id) VALUES(NULL,%s)',(target,))
        self.plan(source,request,expected=409)

    def test_document_edit_new_address_and_link_change_invalidate_the_saved_plan(self):
        source,target,request=self.connection()
        invoice=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(2,%s,1) RETURNING id',(source,))[0][0]
        plan=self.plan(source,request)
        self.sql('UPDATE supplier_invoices SET amount=2 WHERE id=%s',(invoice,))
        self.confirm(source,request,plan,expected=409)
        plan=self.plan(source,request)
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id) VALUES(2,%s)',(target,))
        self.confirm(source,request,plan,expected=409)
        source,target,request=self.connection();plan=self.plan(source,request)
        self.sql('UPDATE company_supplier_links SET version=version+1 WHERE company_id=2 AND supplier_id=%s',(target,))
        self.confirm(source,request,plan,expected=409)

    def test_identity_aba_merge_missing_schema_and_pending_request_do_not_apply(self):
        source,target,request=self.connection();plan=self.plan(source,request)
        owner=self.fixture['users']['supplier']['id']
        self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s',(target,))
        self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(owner,target))
        self.confirm(source,request,plan,expected=409)
        source,target,request=self.connection()
        self.sql("UPDATE company_supplier_links SET profile=jsonb_build_object('mergedIntoSupplierId',%s) WHERE company_id=2 AND supplier_id=%s",(target,source))
        self.plan(source,request,expected=409)
        source,target,request=self.connection(False)
        self.plan(source,request,expected=409)
        source,target,request=self.connection()
        self.sql('ALTER TABLE file_ownership RENAME TO correction_saved_files')
        try:self.plan(source,request,expected=503)
        finally:self.sql('ALTER TABLE correction_saved_files RENAME TO file_ownership')

    def test_forgery_revocation_default_off_and_strict_confirmation(self):
        source,target,request=self.connection();plan=self.plan(source,request)
        self.api('director','POST',self.path(source,request),dict(operationId=str(uuid.uuid4())),expected=403)
        self.api('admin','POST',self.path(source,request,3),dict(operationId=str(uuid.uuid4())),expected=404)
        self.api('admin','POST',self.path(source,request),dict(operationId=str(uuid.uuid4()),targetSupplierId=target),expected=422)
        self.api('admin','POST',self.path(source,request)+'/'+plan['id']+'/confirm',dict(confirmed=False,reason='Synthetic reason'),expected=422)
        self.confirm(source,request,plan,reason='no',expected=422)
        with patch.dict(os.environ,PARTICIPANT_CORRECTIONS_ENABLED='0'):
            self.confirm(source,request,plan,expected=503)
        uid=self.fixture['users']['admin']['id']
        self.sql("UPDATE users SET role='platform_admin' WHERE id=%s",(uid,))
        try:self.confirm(source,request,plan,expected=409)
        finally:self.sql("UPDATE users SET role='system_owner' WHERE id=%s",(uid,))

    def test_plan_is_immutable_audit_rollback_and_repeat_reason_must_match(self):
        source,target,request=self.connection();plan=self.plan(source,request)
        for query in ('UPDATE supplier_connection_correction_plans SET expires_at=NOW() WHERE id=%s',
                      'DELETE FROM supplier_connection_correction_plans WHERE id=%s'):
            with self.assertRaises(RaiseException):self.sql(query,(plan['id'],))
        with self.assertRaises(RaiseException):self.sql('TRUNCATE supplier_connection_correction_plans')
        with self.assertRaises(CheckViolation):self.sql('UPDATE supplier_connection_correction_plans SET applied_at=NOW() WHERE id=%s',(plan['id'],))
        self.sql("""CREATE FUNCTION correction_test_audit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF NEW.action='supplier_connection_corrected' THEN RAISE EXCEPTION 'synthetic audit unavailable'; END IF; RETURN NEW; END $$;
            CREATE TRIGGER correction_test_audit_failure BEFORE INSERT ON audit_log FOR EACH ROW EXECUTE FUNCTION correction_test_audit_failure()""")
        try:
            with self.assertRaises(RaiseException):self.confirm(source,request,plan)
        finally:self.sql('DROP TRIGGER correction_test_audit_failure ON audit_log; DROP FUNCTION correction_test_audit_failure()')
        self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',)])
        self.assertEqual(self.sql('SELECT applied_at FROM supplier_connection_correction_plans WHERE id=%s',(plan['id'],)),[(None,)])
        self.confirm(source,request,plan)
        self.confirm(source,request,plan,reason='A different synthetic reason',expected=409)

    def test_proposal_and_confirmation_are_idempotent_under_parallel_retries(self):
        source,target,request=self.connection();operation=dict(operationId=str(uuid.uuid4()))
        with ThreadPoolExecutor(max_workers=2) as pool:
            proposals=list(pool.map(lambda _:self.api('admin','POST',self.path(source,request),operation),range(2)))
        self.assertEqual(proposals[0],proposals[1]);first=proposals[0]
        self.assertEqual(first,self.api('admin','POST',self.path(source,request),operation))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.confirm(source,request,first),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_connection_corrected' AND entity_id=%s",(target,)),[(1,)])

    def test_expired_plan_other_administrator_and_company_header_cannot_apply(self):
        source,target,request=self.connection();plan=self.plan(source,request)
        uid=self.sql("INSERT INTO users(name,email,password,role,active) VALUES('Synthetic second admin',%s,'unused','platform_admin',TRUE) RETURNING id",(str(uuid.uuid4())+'@local.invalid',))[0][0]
        self.fixture['users']['second_admin']=dict(id=uid,role='platform_admin',name='Synthetic second admin')
        path=self.path(source,request)+'/'+plan['id']+'/confirm'
        self.api('second_admin','POST',path,dict(confirmed=True,reason='Synthetic second administrator'),expected=404)
        self.api('admin','POST',self.path(source,request,3)+'/'+plan['id']+'/confirm',dict(confirmed=True,reason='Synthetic different company'),expected=404)
        self.sql('''ALTER TABLE supplier_connection_correction_plans DISABLE TRIGGER supplier_connection_correction_immutable;
            UPDATE supplier_connection_correction_plans SET created_at=NOW()-INTERVAL '20 minutes',expires_at=NOW()-INTERVAL '5 minutes' WHERE id=%s;
            ALTER TABLE supplier_connection_correction_plans ENABLE TRIGGER supplier_connection_correction_immutable''',(plan['id'],))
        self.confirm(source,request,plan,expected=409)
        self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',)])

    def test_foreign_key_and_group_recipient_and_standalone_contract_are_not_missed(self):
        source,target,request=self.connection()
        self.sql('CREATE TABLE correction_vendor_probe(id SERIAL PRIMARY KEY,company_id INT,vendor_id INT REFERENCES suppliers(id))')
        try:
            self.sql('INSERT INTO correction_vendor_probe(company_id,vendor_id) VALUES(2,%s)',(target,))
            self.plan(source,request,expected=409)
        finally:self.sql('DROP TABLE correction_vendor_probe')
        source,target,request=self.connection()
        registry=self.sql('INSERT INTO supplier_contract_registry(company_id,supplier_id,buyer_company_id,payer_company_id) VALUES(2,%s,2,2) RETURNING id',(target,))[0][0]
        self.assertGreater(registry,0);self.plan(source,request,expected=409)
        source,target,request=self.connection()
        rid=self.sql("INSERT INTO supply_requests(company_id,material_name) VALUES(2,'Synthetic group recipient') RETURNING id")[0][0]
        self.sql('INSERT INTO supply_request_recipients(company_id,request_id,supplier_id,target_supplier_id,supplier_group_ids) VALUES(2,%s,%s,%s,%s)',
                 (rid,source,source,[target]))
        self.plan(source,request,expected=409)

    def test_uncommitted_business_writer_wins_before_confirm_predicate_lock(self):
        from threading import Event
        from . import corrections
        source,target,request=self.connection();plan=self.plan(source,request)
        writer=self.main.get_db();writer.autocommit=False
        with writer.cursor() as cur:cur.execute('INSERT INTO supplier_invoices(company_id,supplier_id) VALUES(2,%s)',(target,))
        reached=Event();original=corrections.company_lock
        # If the command improperly skips the business locks, company_lock will
        # be reached and an uncommitted row could be missed by the inventory.
        def marker(*args):reached.set();return original(*args)
        try:
            with patch.object(corrections,'company_lock',side_effect=marker),ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.confirm,source,request,plan,expected=409)
                self.assertFalse(reached.wait(.2))
                writer.commit()
                future.result(timeout=20)
        finally:writer.close()
        self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',)])

    def test_list_tracks_current_status_after_an_explicit_later_reactivation(self):
        source,target,request=self.connection();plan=self.plan(source,request)
        self.confirm(source,request,plan)
        with patch.dict(os.environ,PARTICIPANT_CORRECTIONS_ENABLED='0'):
            listing=self.api('admin','GET',self.path(source,request).rsplit('/',2)[0])
            self.assertEqual(next(r for r in listing['items'] if r['id']==request)['correctionStatus'],'disconnected')
        self.sql("UPDATE company_supplier_links SET status='Активный',version=version+1 WHERE company_id=2 AND supplier_id=%s",(target,))
        listing=self.api('admin','GET',self.path(source,request).rsplit('/',2)[0])
        self.assertIsNone(next(r for r in listing['items'] if r['id']==request)['correctionStatus'])
        self.confirm(source,request,plan,expected=409)

    def test_large_archive_is_a_review_requirement_without_partial_changes(self):
        source,target,request=self.connection()
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id) SELECT 2,%s FROM generate_series(1,2001)',(source,))
        try:
            result=self.plan(source,request,expected=409)
            self.assertIn('Архив слишком большой',result['detail'])
            self.assertEqual(self.sql('SELECT status FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(target,)),[('Активный',)])
        finally:self.sql('DELETE FROM supplier_invoices WHERE company_id=2 AND supplier_id=%s',(source,))
