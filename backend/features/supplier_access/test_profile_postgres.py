"""Supplier-owned profile and leader-only edits, with real HTTP and PostgreSQL."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from backend.features.supplier_team import test_customer_team_postgres as support

@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Requires isolated PostgreSQL')
class SupplierProfilePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.CustomerTeamPostgresTests.setUpClass.__func__(cls)
    api=support.CustomerTeamPostgresTests.api
    sql=support.CustomerTeamPostgresTests.sql
    setUp=support.CustomerTeamPostgresTests.setUp

    @property
    def path(self):return f"/suppliers/{self.fixture['supplierId']}/requisites"

    def test_profile_has_actual_fields_no_buyer_terms_or_fabricated_tariff(self):
        result=self.api('supplier','GET',self.path)
        self.assertEqual(result['fields']['name'],self.sql('SELECT name FROM suppliers WHERE id=%s',(self.fixture['supplierId'],))[0][0])
        self.assertNotIn('contractNumber',result['fields'])
        self.assertNotIn('notes',result['fields'])
        self.assertEqual(result['tariff'],{'status':'not_configured'})
        self.assertIsNone(result['team']['managerLimit'])
        for role in ('manager','stranger_supplier','director'):
            self.api(role,'GET',self.path,expected=403)

    def test_save_stale_write_and_empty_name(self):
        before=self.api('supplier','GET',self.path)
        saved=self.api('supplier','PUT',self.path,{'phone':'Profile test 123','expectedProfileVersion':before['version']})
        self.assertEqual(saved['fields']['phone'],'Profile test 123')
        self.assertNotEqual(saved['version'],before['version'])
        self.api('supplier','PUT',self.path,{'phone':'Lost update','expectedProfileVersion':before['version']},expected=409)
        self.api('supplier','PUT',self.path,{'name':'  '},expected=422)
        self.assertEqual(self.api('supplier','GET',self.path),{k:v for k,v in saved.items() if k!='ok'})

    def test_leader_member_can_edit_but_disabled_member_and_manager_cannot(self):
        self.api('manager','PUT',self.path,{'phone':'Forbidden'},expected=403)
        self.sql("UPDATE supplier_team_members SET role='leader' WHERE id=%s",(self.member_id,))
        profile=self.api('manager','GET',self.path)
        self.api('manager','PUT',self.path,{'website':'https://example.test','expectedProfileVersion':profile['version']})
        self.sql('UPDATE supplier_team_members SET active=FALSE WHERE id=%s',(self.member_id,))
        self.api('manager','GET',self.path,expected=403)
        self.api('manager','PUT',self.path,{'website':'https://forbidden.test'},expected=403)

    def test_company_deal_fields_rejected_and_foreign_identity_unchanged(self):
        before=self.sql('SELECT row_to_json(s)::text FROM suppliers s ORDER BY id')
        self.api('supplier','PUT',self.path,{'contractNumber':'Private buyer contract'},expected=422)
        self.api('stranger_supplier','PUT',self.path,{'bank':'Foreign bank'},expected=403)
        self.assertEqual(self.sql('SELECT row_to_json(s)::text FROM suppliers s ORDER BY id'),before)

    def test_parallel_writes_only_one_can_use_current_revision(self):
        version=self.api('supplier','GET',self.path)['version']
        token=self.main.create_auth_token(self.fixture['users']['supplier'],two_factor_passed=True)
        def change(phone):
            return self.client.put(self.path,json={'phone':phone,'expectedProfileVersion':version},headers={'Authorization':'Bearer '+token}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(change,['Concurrent A','Concurrent B']))
        self.assertEqual(sorted(statuses),[200,409])

    def test_field_limits_reject_before_database_and_allow_long_address(self):
        before=self.api('supplier','GET',self.path)
        for key,limit in before['fieldLimits'].items():
            self.api('supplier','PUT',self.path,{key:'x'*(limit+1)},expected=422)
        self.assertEqual(self.api('supplier','GET',self.path),before)
        saved=self.api('supplier','PUT',self.path,{'legalAddress':'x'*4000})
        self.assertEqual(len(saved['fields']['legalAddress']),4000)
