import unittest
from fastapi import HTTPException
from backend.features.customer_cabinet.record_scope import positive_id, project_visibility, require_record_author

class RecordScopeTest(unittest.TestCase):
    def test_zero_negative_and_malformed_ids_are_not_owner_ids(self):
        for value in (0, '0', -1, '-1', True, False, None, '', 'bad', [], {}, 1.0):
            with self.subTest(value=value):
                self.assertIsNone(positive_id(value))

    def test_legacy_company_and_project_fields_keep_the_exact_scope(self):
        sql, params = project_visibility(
            [{'company_id': '2', 'role': 'заказчик', 'project_id': '7'}],
            ('заказчик',), lambda actor: ['Лицей'],
        )
        self.assertIn('p.company_id=%s', sql)
        self.assertIn('p.id=%s', sql)
        self.assertEqual(params, [2, ['Лицей'], 7])

    def test_lowest_positive_company_id_remains_visible(self):
        for company_id in (1, '1'):
            with self.subTest(company_id=company_id):
                sql, params = project_visibility(
                    [{'companyId': company_id, 'role': 'директор'}],
                    ('директор',), lambda actor: None,
                )
                self.assertIn('p.company_id=%s', sql)
                self.assertEqual(params, [1])

    def test_customer_assignment_accepts_lowest_positive_project_id(self):
        for project_id in (1, '1'):
            with self.subTest(project_id=project_id):
                sql, params = project_visibility(
                    [{'companyId': 2, 'role': 'заказчик', 'projectId': project_id}],
                    ('заказчик',), lambda actor: ['Лицей'],
                )
                self.assertIn('p.company_id=%s', sql)
                self.assertIn('p.id=%s', sql)
                self.assertEqual(params, [2, ['Лицей'], 1])

    def test_missing_company_and_disallowed_role_fail_closed(self):
        visible=lambda user:None
        self.assertEqual(project_visibility([{'role':'директор'}],('директор',),visible),('FALSE',[]))
        self.assertEqual(project_visibility([{'role':'поставщик','companyId':1}],('директор',),visible),('FALSE',[]))

    def test_selected_membership_role_and_projects_are_used(self):
        sql,params=project_visibility([{'companyId':2,'role':'заказчик','project_id':7}],('заказчик',),lambda user:['Лицей'])
        self.assertIn('p.company_id=%s',sql);self.assertIn('p.id=%s',sql)
        self.assertEqual(params,[2,['Лицей'],7])

    def test_legacy_name_cannot_match_two_projects_in_one_company(self):
        sql,params=project_visibility([{'companyId':2,'role':'заказчик'}],('заказчик',),lambda user:['Лицей'])
        self.assertIn('NOT EXISTS',sql);self.assertIn('other.company_id=p.company_id',sql)
        self.assertEqual(params,[2,['Лицей']])

    def test_same_customer_role_and_name_do_not_prove_authorship(self):
        with self.assertRaises(HTTPException):
            require_record_author({'id':9,'role':'заказчик','name':'Клиент'},8)
        with self.assertRaises(HTTPException):
            require_record_author({'id':9,'role':'заказчик','name':'Клиент'},None)
        require_record_author({'id':9,'role':'заказчик'},9)

    def test_malformed_customer_assignment_never_falls_back_to_name(self):
        for project_id in (False, True, 0, 'bad', []):
            self.assertEqual(project_visibility([{'companyId':1,'role':'заказчик','projectId':project_id}],
                ('заказчик',),lambda user:['Лицей']),('FALSE',[]))
