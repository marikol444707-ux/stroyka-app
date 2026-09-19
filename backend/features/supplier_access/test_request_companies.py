import unittest
from unittest.mock import Mock
from backend.features.supplier_access.request_companies import attach_request_company_names
from backend.features.supplier_access.supply_request_workflow import sanitize_supplier_request_response

class RequestCompanyTests(unittest.TestCase):
    def test_only_names_of_already_authorized_companies_are_requested(self):
        cur=Mock();cur.fetchall.return_value=[{'id':2,'name':'Альфа'},{'id':3,'name':'Бета'}]
        rows=attach_request_company_names(cur,[{'id':5,'companyId':2},{'id':6,'companyId':3}])
        self.assertEqual(cur.execute.call_args.args[1],([2,3],))
        self.assertEqual([r['companyName'] for r in rows],['Альфа','Бета'])
        self.assertEqual(sanitize_supplier_request_response(rows[0])['companyName'],'Альфа')
    def test_empty_scope_does_not_query_directory(self):
        cur=Mock()
        self.assertEqual(attach_request_company_names(cur,[]),[])
        cur.execute.assert_not_called()
