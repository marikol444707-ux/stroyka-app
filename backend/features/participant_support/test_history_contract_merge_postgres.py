"""Contract originals/addenda use the actual file router's startup policy."""
import importlib
import json
import os
import unittest
import uuid
from unittest.mock import patch

from .test_postgres import ParticipantSupportPostgresTests as Support
from .test_history_merge_postgres import SupplierHistoryMergePostgresTests as Merge
from .test_history_preview_postgres import SupplierHistoryPreviewPostgresTests as History


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class SupplierHistoryContractMergePostgresTests(unittest.TestCase):
    sql,api,pair=Support.sql,Support.api,History.pair
    path,review,confirm=Merge.path,Merge.review,Merge.confirm

    @classmethod
    def setUpClass(cls):
        from ..supplier_access import test_postgres_chain_support as fixture
        build=fixture.build_fixture
        with patch.object(fixture,'build_fixture',side_effect=lambda:build(contract_review=True)):
            Support.setUpClass.__func__(cls)
        from ..supplier_deal_parties.test_contract_postgres import statements
        for statement in statements('upgrade','0067_supplier_contract_originals.py'):
            cls.sql(cls,statement)
        for name in ('0038_supplier_customer_team','0095_supplier_buyer_connections','0096_supplier_history_merge_plans'):
            cls.sql(cls,importlib.import_module('migrations.versions.'+name).SCHEMA_SQL)
        patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1',SUPPLIER_TEAM_ENABLED='1').start()

    def original(self,source):
        files=[self.sql("INSERT INTO file_ownership(company_id,file_url,context) VALUES(2,%s,'documents') RETURNING id",
                        ('/uploads/company-2-common-documents/'+str(uuid.uuid4())+'.pdf',))[0][0] for _ in range(3)]
        registry=self.sql('INSERT INTO supplier_contract_registry(company_id,supplier_id,buyer_company_id,payer_company_id) VALUES(2,%s,2,2) RETURNING id',(source,))[0][0]
        version=self.sql('''INSERT INTO supplier_contract_versions(company_id,version,source_file_id,snapshot_json,snapshot_hash,
            reason,reviewed_by_id,reviewed_by) VALUES(2,1,%s,%s,%s,'Synthetic checked original',%s,'Synthetic reviewer') RETURNING id''',
            (files[0],json.dumps(dict(supplier=dict(supplierId=source),addenda=[dict(sourceFileId=files[1])])),
             '0'*64,self.fixture['users']['director']['id']))[0][0]
        self.sql('INSERT INTO supplier_contract_registry_versions(registry_id,contract_version_id,company_id) VALUES(%s,%s,2)',(registry,version))
        return version,files

    def test_original_and_addendum_match_actual_metadata_access_without_unrelated_file(self):
        source,target=self.pair();version,files=self.original(source)
        before=self.sql('SELECT to_jsonb(v) FROM supplier_contract_versions v WHERE id=%s',(version,))
        self.api('supplier','GET',f'/tenant-files/{files[0]}',expected=403)
        plan=self.review(source,target)
        self.assertEqual(plan['newAccess']['files'],files[:2])
        self.confirm(source,plan)
        for fid in files[:2]:self.api('supplier','GET',f'/tenant-files/{fid}')
        self.api('supplier','GET',f'/tenant-files/{files[2]}',expected=403)
        self.assertEqual(before,self.sql('SELECT to_jsonb(v) FROM supplier_contract_versions v WHERE id=%s',(version,)))

    def test_deleting_addendum_invalidates_review_and_is_excluded_from_new_plan(self):
        source,target=self.pair();_,files=self.original(source)
        plan=self.review(source,target)
        self.sql("UPDATE file_ownership SET deletion_status='deleting' WHERE id=%s",(files[1],))
        self.confirm(source,plan,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.review(source,target)['newAccess']['files'],[files[0]])
