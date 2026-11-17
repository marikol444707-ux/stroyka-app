"""Real company/parent authorization for historical AOSR snapshots."""
import json
import os
import unittest

from ..customer_cabinet.test_hidden_acts_postgres import CustomerHiddenActTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class DocumentVersionAccessTests(unittest.TestCase):
    setUpClass = classmethod(CustomerHiddenActTests.setUpClass.__func__)
    api = CustomerHiddenActTests.api
    sql = CustomerHiddenActTests.sql
    seed = CustomerHiddenActTests.seed

    def version(self, company=2, snapshot_change=None, document_type='hidden_works_act'):
        act = self.seed(company)
        snapshot = self.sql('SELECT row_to_json(h) FROM hidden_works_acts h WHERE id=%s', (act,))[0][0]
        if snapshot_change:
            snapshot_change(snapshot)
        version = self.sql('''INSERT INTO document_versions(document_type,document_id,version_label,
            snapshot_json,changed_by,change_reason) VALUES(%s,%s,'v1',%s,'Private author','Private reason')
            RETURNING id''', (document_type,act,json.dumps(snapshot,default=str)))[0][0]
        return act, version

    def test_foreign_version_hidden_from_list_and_known_id(self):
        self.sql('INSERT INTO projects(name,company_id) VALUES(%s,3)',(self.fixture['project'],))
        _, foreign = self.version(3)
        actor = self.fixture['users']['director']
        rows = self.api(actor,'GET','/document-versions')
        self.assertNotIn(foreign, [row['id'] for row in rows])
        self.api(actor,'GET',f'/document-versions/{foreign}',expected=404)
        own = self.api(self.fixture['users']['stranger'],'GET',f'/document-versions/{foreign}',company=3)
        self.assertEqual(own['snapshot']['company_id'],3)

    def test_customer_snapshot_does_not_leak_internal_financial_fields(self):
        _, version = self.version()
        result = self.api(self.customer,'GET',f'/document-versions/{version}')
        self.assertNotIn('total',result['snapshot'])
        self.assertNotIn('comments',result['snapshot'])
        self.assertEqual(result['snapshot']['work_name'],'Hidden work')
        self.assertEqual(result['changedBy'],'')
        self.assertEqual(result['changeReason'],'')

    def test_current_director_keeps_own_snapshot_and_filters(self):
        act, version = self.version()
        actor = self.fixture['users']['director']
        result = self.api(actor,'GET',f'/document-versions/{version}')
        self.assertEqual(result['snapshot']['total'],99)
        rows = self.api(actor,'GET',f'/document-versions?document_type=hidden_works_act&document_id={act}')
        self.assertEqual([r['id'] for r in rows],[version])
        self.api(actor,'GET',f'/document-versions/{version}',company=3,expected=403)

    def test_unassigned_unknown_malformed_and_mismatched_versions_are_hidden(self):
        actor = self.fixture['users']['director']
        hidden = []
        for change in (lambda s:s.pop('company_id'),lambda s:s.update(company_id=3),
                       lambda s:s.update(id=2147483647),lambda s:s.update(project_name='Different'),
                       lambda s:s.update(work_journal_id=2147483647),lambda s:s.update(work_package='Other')):
            hidden.append(self.version(snapshot_change=change)[1])
        hidden.append(self.version(document_type='untrusted_parent')[1])
        _, bad = self.version()
        self.sql('UPDATE document_versions SET snapshot_json=%s WHERE id=%s',('broken json',bad))
        hidden.append(bad)
        rows = self.api(actor,'GET','/document-versions')
        self.assertFalse(set(hidden)&{row['id'] for row in rows})
        for version in hidden:
            self.api(actor,'GET',f'/document-versions/{version}',expected=404)

    def test_deleted_parent_and_unconfirmed_work_are_hidden(self):
        act, version = self.version()
        self.sql("UPDATE work_journal SET status='На проверке' WHERE id=(SELECT work_journal_id FROM hidden_works_acts WHERE id=%s)",(act,))
        self.api(self.customer,'GET',f'/document-versions/{version}',expected=404)
        self.sql('DELETE FROM hidden_works_acts WHERE id=%s',(act,))
        self.api(self.fixture['users']['director'],'GET',f'/document-versions/{version}',expected=404)

    def test_revoked_membership_blocks_own_history(self):
        _, version = self.version()
        actor = self.fixture['users']['director']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(actor['id'],))
        try:
            self.api(actor,'GET',f'/document-versions/{version}',expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(actor['id'],))

    def test_real_act_update_saves_readable_owned_snapshot(self):
        act = self.seed()
        actor = self.fixture['users']['director']
        self.api(actor,'PUT',f'/hidden-works-acts/{act}',{'comments':'Updated'})
        rows = self.api(actor,'GET',f'/document-versions?document_type=hidden_works_act&document_id={act}')
        self.assertEqual(len(rows),1)
        snapshot = self.api(actor,'GET',f'/document-versions/{rows[0]["id"]}')['snapshot']
        self.assertEqual(snapshot['company_id'],2)
        self.assertEqual(snapshot['comments'],'PRIVATE')

    def test_master_requires_confirmed_own_work_and_package(self):
        act, version = self.version()
        actor = dict(self.customer,role='мастер')
        self.sql("UPDATE users SET role='мастер' WHERE id=%s",(actor['id'],))
        self.sql("UPDATE user_company_roles SET role='мастер' WHERE user_id=%s AND company_id=2",(actor['id'],))
        try:
            self.api(actor,'GET',f'/document-versions/{version}',expected=404)
            self.sql('UPDATE work_journal SET master_id=%s WHERE id=(SELECT work_journal_id FROM hidden_works_acts WHERE id=%s)',(actor['id'],act))
            result = self.api(actor,'GET',f'/document-versions/{version}')
            self.assertNotIn('total',result['snapshot'])
            self.sql("UPDATE user_company_roles SET assigned_packages='[]' WHERE user_id=%s AND company_id=2",(actor['id'],))
            self.api(actor,'GET',f'/document-versions/{version}',expected=404)
        finally:
            self.sql("UPDATE users SET role='заказчик' WHERE id=%s",(actor['id'],))
            self.sql('UPDATE user_company_roles SET role=%s,assigned_packages=%s WHERE user_id=%s AND company_id=2',('заказчик','["Основная"]',actor['id']))

    def test_project_document_mutations_and_files_reject_foreign_company(self):
        import base64
        director = self.fixture['users']['director']
        foreign = self.fixture['users']['stranger']
        image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
        def headers(actor, company):
            return {'Authorization':'Bearer '+self.main.create_auth_token(actor,two_factor_passed=True),
                    'X-Company-Id':str(company),'X-Company-Mode':'company'}
        response = self.client.post('/upload-photo',headers=headers(director,2),
            data={'projectId':str(self.fixture['projectId']),'context':'project-documents'},
            files={'file':('test.png',image,'image/png')})
        self.assertEqual(response.status_code,200,response.text)
        upload = response.json()
        url = upload['url']
        record = self.api(director,'POST','/project-documents',{'projectId':self.fixture['projectId'],
            'side':'contractor','docType':'Прочее','scanUrl':url,'notes':'Private'})
        path = '/project-documents/'+str(record['id'])
        rows = self.api(foreign,'GET','/project-documents',company=3)
        self.assertNotIn(record['id'],{row['id'] for row in rows})
        self.api(foreign,'PUT',path,{'notes':'Attack'},company=3,expected=404)
        self.api(foreign,'DELETE',path,company=3,expected=404)
        file_id = int(upload['metadataUrl'].rsplit('/',1)[1])
        legacy_url = self.sql('SELECT file_url FROM file_ownership WHERE id=%s',(file_id,))[0][0]
        for target in (f'/tenant-files/{file_id}',f'/tenant-files/{file_id}/content',legacy_url):
            rejected = self.client.get(target,headers=headers(foreign,3))
            # The file API uses 409 when the selected company differs from
            # the resource owner, before deciding access in that company.
            self.assertIn(rejected.status_code,(403,404,409),target)
            self.assertNotEqual(rejected.content,image)
        rejected = self.client.delete(f'/tenant-files/{file_id}',headers=headers(foreign,3))
        self.assertIn(rejected.status_code,(403,404,409))
        content = self.client.get(f'/tenant-files/{file_id}/content',headers=headers(director,2))
        self.assertEqual(content.status_code,200)
        self.assertEqual(content.content,image)
        self.assertEqual(self.sql('SELECT notes FROM project_documents WHERE id=%s',(record['id'],)),[('Private',)])
