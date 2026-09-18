import os
from unittest.mock import patch

from . import test_owner_stock_postgres as support


class JournalSuggestionsPostgresTests(support.OwnerStockPostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        flags = patch.dict(os.environ, {'OWNED_QUALITY_ACCESS_ENABLED': '1', 'OWNED_QUALITY_AI_ENABLED': '1'})
        flags.start()
        cls.addClassCleanup(flags.stop)

    def row(self):
        return self.sql('''INSERT INTO material_inspection_journal(company_id,project_id,project_name,
            material_name,unit,quantity,work_package) VALUES(2,%s,%s,'Material','шт',2,'Основная') RETURNING id''',
            (self.f['projectId'], self.f['project']))[0][0]

    def suggest(self, row_id, expected=200, actor='director'):
        return self.api(actor, 'POST', '/material-inspection/'+str(row_id)+'/ai-suggest', {}, expected=expected)

    def test_valid_suggestion_is_saved_after_reauthorization(self):
        row_id = self.row()
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text',
                   return_value='{"normatives":"Проверить стандарт","requiredDocs":"Паспорт"}'):
            result = self.suggest(row_id)
        self.assertTrue(result['aiFilled'])
        self.assertEqual(self.sql('SELECT normatives,remarks,ai_filled FROM material_inspection_journal WHERE id=%s', (row_id,)),
                         [('Проверить стандарт', 'Требуемые документы: Паспорт', True)])

    def test_edit_during_provider_call_is_not_overwritten(self):
        row_id = self.row()
        def provider(*args, **kwargs):
            self.sql("UPDATE material_inspection_journal SET remarks='Human edit' WHERE id=%s", (row_id,))
            return '{"normatives":"AI","requiredDocs":"Passport"}'
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text', side_effect=provider):
            self.suggest(row_id, expected=409)
        self.assertEqual(self.sql('SELECT remarks,ai_filled FROM material_inspection_journal WHERE id=%s', (row_id,)), [('Human edit', False)])

    def test_revocation_during_provider_call_prevents_save(self):
        row_id = self.row()
        user_id = self.f['users']['foreman']['id']
        def provider(*args, **kwargs):
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (user_id,))
            return '{"normatives":"AI","requiredDocs":"Passport"}'
        try:
            with patch('backend.features.quality_journals.suggestions.request_suggestion_text', side_effect=provider):
                self.suggest(row_id, expected=403, actor='foreman')
            self.assertEqual(self.sql('SELECT normatives,ai_filled FROM material_inspection_journal WHERE id=%s', (row_id,)), [(None, False)])
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (user_id,))

    def test_inaccessible_row_never_calls_provider(self):
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text') as provider:
            self.suggest(2147483647, expected=404)
            provider.assert_not_called()

    def test_malformed_provider_output_is_not_saved(self):
        row_id = self.row()
        for value in ('[]', '{"normatives":3,"requiredDocs":"x"}', '{"normatives":"x","requiredDocs":"y","sql":"x"}'):
            with patch('backend.features.quality_journals.suggestions.request_suggestion_text', return_value=value):
                self.suggest(row_id, expected=502)
        self.assertEqual(self.sql('SELECT ai_filled FROM material_inspection_journal WHERE id=%s', (row_id,)), [(False,)])

    def test_human_remarks_are_preserved(self):
        row_id = self.row()
        self.sql("UPDATE material_inspection_journal SET remarks='Human notes' WHERE id=%s", (row_id,))
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text',
                   return_value='{"normatives":"AI","requiredDocs":"Passport"}'):
            self.suggest(row_id)
        self.assertEqual(self.sql('SELECT remarks FROM material_inspection_journal WHERE id=%s', (row_id,)), [('Human notes',)])

    def test_cable_suggestion_uses_same_guarded_save(self):
        row_id = self.sql("""INSERT INTO cable_journal(company_id,project_id,project_name,cable_brand,work_package)
            VALUES(2,%s,%s,'ВВГнг 3х2,5','Основная') RETURNING id""", (self.f['projectId'], self.f['project']))[0][0]
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text',
                   return_value='{"normatives":"Check","minInsulation":"1","recommendations":"Verify"}'):
            result = self.api('director', 'POST', '/cable-journal/'+str(row_id)+'/ai-suggest', {})
        self.assertTrue(result['aiFilled'])
        self.assertIn('Verify', result['normatives'])

    def test_annulment_during_provider_call_prevents_save(self):
        row_id = self.sql("""INSERT INTO cable_journal(company_id,project_id,project_name,cable_brand,work_package)
            VALUES(2,%s,%s,'ВВГнг 3х2,5','Основная') RETURNING id""", (self.f['projectId'], self.f['project']))[0][0]
        def provider(*args, **kwargs):
            self.sql("UPDATE cable_journal SET status='Аннулирована' WHERE id=%s", (row_id,))
            return '{"normatives":"Check","minInsulation":"1","recommendations":"Verify"}'
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text', side_effect=provider):
            self.api('director', 'POST', '/cable-journal/'+str(row_id)+'/ai-suggest', {}, expected=409)
        self.assertEqual(self.sql('SELECT ai_filled FROM cable_journal WHERE id=%s', (row_id,)), [(False,)])
        with patch('backend.features.quality_journals.suggestions.request_suggestion_text') as provider:
            self.api('director', 'POST', '/cable-journal/'+str(row_id)+'/ai-suggest', {}, expected=409)
            provider.assert_not_called()
