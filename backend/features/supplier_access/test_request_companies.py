import unittest
import json
from unittest.mock import Mock
from backend.features.supplier_access.request_companies import attach_requester_identity
from backend.features.supplier_access.supply_request_workflow import sanitize_supplier_request_response

class RequestCompanyTests(unittest.TestCase):
    def test_only_names_of_already_authorized_companies_are_requested(self):
        cur=Mock();cur.fetchall.return_value=[
            {'request_id':5,'company_id':2,'project':'Объект А','requester_snapshot_json':json.dumps({
                'version':1,'requestId':5,'companyId':2,'companyName':'Альфа на дату отправки',
                'companyEmail':'','companyPhone':'','contactUserId':7,'contactName':'Иван','contactEmail':'ivan@example.test',
                'contactPhone':'','projectId':11,'projectName':'Объект А','deliveryAddress':'','frozenAt':'2026-10-01T12:00:00Z'}),
             'name':'Альфа сейчас'},
            {'request_id':6,'company_id':3,'project':'Объект Б','requester_snapshot_json':None,'name':'Бета'},
        ]
        rows=attach_requester_identity(cur,[{'id':5,'companyId':2},{'id':6,'companyId':3}])
        self.assertEqual(cur.execute.call_args.args[1],([5,6],))
        self.assertEqual([r['companyName'] for r in rows],['Альфа на дату отправки','Бета'])
        safe=sanitize_supplier_request_response(rows[0])
        self.assertEqual(safe['companyName'],'Альфа на дату отправки')
        self.assertEqual(safe['contactName'],'Иван')
        self.assertEqual(safe['contactEmail'],'ivan@example.test')
    def test_empty_scope_does_not_query_directory(self):
        cur=Mock()
        self.assertEqual(attach_requester_identity(cur,[]),[])
        cur.execute.assert_not_called()
