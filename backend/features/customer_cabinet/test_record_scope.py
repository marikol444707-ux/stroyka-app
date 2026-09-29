import unittest
from fastapi import HTTPException
from backend.features.customer_cabinet.record_scope import project_visibility, require_record_author

class RecordScopeTest(unittest.TestCase):
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
