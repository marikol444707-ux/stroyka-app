import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import quote

from . import test_owner_stock_postgres as support


class JournalAccessPostgresTests(support.OwnerStockPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flag = patch.dict(os.environ, {'OWNED_QUALITY_ACCESS_ENABLED': '1'})
        flag.start()
        cls.addClassCleanup(flag.stop)

    def rows(self, table):
        foreign_project = self.sql('INSERT INTO projects(name,company_id) VALUES(%s,3) RETURNING id', (self.f['project'],))[0][0]
        ids = []
        for company, project in ((2, self.f['projectId']), (3, foreign_project), (None, None)):
            ids.append(self.sql(f'''INSERT INTO {table}(company_id,project_id,project_name,work_package)
                VALUES(%s,%s,%s,'Основная') RETURNING id''', (company, project, self.f['project']))[0][0])
        return ids

    def test_lists_exclude_foreign_and_unbound_without_backfill(self):
        for table, path in [('material_inspection_journal', '/material-inspection'), ('cable_journal', '/cable-journal')]:
            ours, foreign, legacy = self.rows(table)
            before = self.sql('SELECT * FROM '+table+' ORDER BY id')
            rows = self.api('director', 'GET', path+'?project_name='+quote(self.f['project']))
            self.assertEqual([row['id'] for row in rows], [ours])
            self.assertEqual(rows[0]['companyId'], 2)
            self.assertEqual(self.sql('SELECT * FROM '+table+' ORDER BY id'), before)

    def test_foreign_and_legacy_mutation_is_rejected(self):
        for table, path in [('material_inspection_journal', '/material-inspection'), ('cable_journal', '/cable-journal')]:
            ours, foreign, legacy = self.rows(table)
            for row_id in (foreign, legacy):
                self.api('director', 'PUT', path+'/'+str(row_id), {'normatives': 'foreign write'}, expected=404)
            self.api('director', 'PUT', path+'/'+str(ours), {'normatives': 'owned write'})
            self.assertEqual(self.sql(f'SELECT normatives FROM {table} WHERE id=%s', (ours,)), [('owned write',)])

    def test_ai_is_closed_before_external_call(self):
        for path in ('/material-inspection', '/cable-journal'):
            self.api('director', 'POST', path+'/1/ai-suggest', {}, expected=503)

    def test_complete_owned_snapshot_is_explicit_even_when_empty(self):
        for path in ('/material-inspection', '/cable-journal'):
            response = self.request('GET', path+'?project_name=missing-project', None)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), [])
            self.assertEqual(response.headers.get('X-Quality-Journal-Snapshot'), 'owned-v1')
        self.api('worker', 'GET', '/cable-journal', expected=403)

    def test_project_assignment_ambiguity_fails_closed(self):
        ours, _, _ = self.rows('material_inspection_journal')
        self.sql('INSERT INTO projects(name,company_id) VALUES(%s,2)', (self.f['project'],))
        self.assertEqual(self.api('foreman', 'GET', '/material-inspection?project_name='+quote(self.f['project'])), [])
        self.api('foreman', 'PUT', '/material-inspection/'+str(ours), {'remarks': 'denied'}, expected=404)

    def test_package_filter_applies_to_owned_rows(self):
        ours, _, _ = self.rows('material_inspection_journal')
        self.sql("UPDATE material_inspection_journal SET work_package='Скрытая' WHERE id=%s", (ours,))
        self.assertEqual(self.api('worker', 'GET', '/material-inspection?project_name='+quote(self.f['project'])), [])

    def test_owner_and_receipt_data_are_not_editable(self):
        ours, _, _ = self.rows('cable_journal')
        for data in ({'companyId': 3}, {'projectId': 999}, {'lengthReceived': 10}, {'cableBrand': 'replacement'}):
            self.api('director', 'PUT', '/cable-journal/'+str(ours), data, expected=409)

    def test_invalid_values_do_not_partially_update(self):
        ours, _, _ = self.rows('cable_journal')
        self.api('director', 'PUT', '/cable-journal/'+str(ours), {'normatives': 'partial', 'lengthInstalled': -1}, expected=400)
        self.assertEqual(self.sql('SELECT normatives FROM cable_journal WHERE id=%s', (ours,)), [(None,)])

    def test_revoked_membership_blocks_mutation(self):
        ours, _, _ = self.rows('material_inspection_journal')
        user_id = self.f['users']['foreman']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (user_id,))
        try:
            self.api('foreman', 'PUT', '/material-inspection/'+str(ours), {'remarks': 'denied'}, expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (user_id,))

    def test_foreign_company_header_does_not_grant_access(self):
        from fastapi.testclient import TestClient
        token = self.main.create_auth_token(self.f['users']['director'], two_factor_passed=True)
        with TestClient(self.main.app, raise_server_exceptions=False) as client:
            response = client.get('/material-inspection', headers={'Authorization': 'Bearer '+token, 'X-Company-Id': '3'})
        self.assertEqual(response.status_code, 403, response.text)

    def test_flag_off_keeps_legacy_list_update_and_role_guard(self):
        with patch.dict(os.environ, {'OWNED_QUALITY_ACCESS_ENABLED': '0'}):
            for table, path in [('material_inspection_journal', '/material-inspection'), ('cable_journal', '/cable-journal')]:
                ours, _, _ = self.rows(table)
                if table == 'cable_journal':
                    self.sql("UPDATE cable_journal SET cable_brand='ВВГнг 3х2,5' WHERE id=%s", (ours,))
                rows = self.api('director', 'GET', path+'?project_name='+quote(self.f['project']))
                self.assertIn(ours, [row['id'] for row in rows])
                self.api('director', 'PUT', path+'/'+str(ours), {'normatives': 'legacy'})
                self.api('worker', 'PUT', path+'/'+str(ours), {'normatives': 'denied'}, expected=403)

    def test_cleared_membership_projects_do_not_use_legacy_user_project(self):
        ours, _, _ = self.rows('material_inspection_journal')
        user_id = self.f['users']['foreman']['id']
        before = self.sql('SELECT project_name FROM users WHERE id=%s', (user_id,))[0][0]
        self.sql('UPDATE users SET project_name=%s WHERE id=%s', (self.f['project'], user_id))
        self.sql("UPDATE user_company_roles SET assigned_projects='[]' WHERE user_id=%s AND company_id=2", (user_id,))
        try:
            self.assertEqual(self.api('foreman', 'GET', '/material-inspection'), [])
            self.api('foreman', 'PUT', '/material-inspection/'+str(ours), {'remarks': 'denied'}, expected=404)
        finally:
            self.sql('UPDATE users SET project_name=%s WHERE id=%s', (before, user_id))

    def test_revocation_committed_while_waiting_for_membership_is_rechecked(self):
        ours, _, _ = self.rows('material_inspection_journal')
        user_id = self.f['users']['foreman']['id']
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (user_id,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.request, 'PUT', '/material-inspection/'+str(ours), {'remarks': 'denied'}, 'foreman')
                try:
                    self.wait_blocked('SELECT id FROM user_company_roles')
                finally:
                    blocker.commit()
                response = future.result(timeout=15)
            self.assertEqual(response.status_code, 403, response.text)
        finally:
            blocker.rollback()
            blocker.close()
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (user_id,))

    def test_membership_lock_is_held_while_put_waits_for_journal(self):
        ours, _, _ = self.rows('material_inspection_journal')
        user_id = self.f['users']['foreman']['id']
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('SELECT id FROM material_inspection_journal WHERE id=%s FOR UPDATE', (ours,))
            with ThreadPoolExecutor(max_workers=2) as pool:
                update = pool.submit(self.request, 'PUT', '/material-inspection/'+str(ours), {'remarks': 'authorized'}, 'foreman')
                try:
                    self.wait_blocked('SELECT j.id,j.company_id')
                    revoke = pool.submit(self.sql, 'UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (user_id,))
                    self.wait_blocked('UPDATE user_company_roles SET active=FALSE')
                finally:
                    blocker.rollback()
                self.assertEqual(update.result(timeout=15).status_code, 200)
                revoke.result(timeout=15)
            self.api('foreman', 'PUT', '/material-inspection/'+str(ours), {'remarks': 'denied'}, expected=403)
        finally:
            blocker.rollback()
            blocker.close()
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (user_id,))

    def test_refresh_cannot_switch_to_an_unlocked_alternative_role(self):
        ours, _, _ = self.rows('material_inspection_journal')
        user_id = self.f['users']['foreman']['id']
        alternate = self.sql("""INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
            role,active,is_default,assigned_projects,assigned_packages)
            VALUES(%s,2,1,'главный_инженер',TRUE,FALSE,'[]','[]') RETURNING id""", (user_id,))[0][0]
        blocker = self.main.get_db()
        blocker.autocommit = False
        try:
            with blocker.cursor() as cur:
                cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2 AND id<>%s', (user_id, alternate))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.request, 'PUT', '/material-inspection/'+str(ours), {'remarks': 'denied'}, 'foreman')
                try:
                    self.wait_blocked('SELECT id FROM user_company_roles')
                finally:
                    blocker.commit()
                response = future.result(timeout=15)
            self.assertEqual(response.status_code, 403, response.text)
        finally:
            blocker.rollback()
            blocker.close()
            self.sql('DELETE FROM user_company_roles WHERE id=%s', (alternate,))
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (user_id,))
