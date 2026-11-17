"""Chief engineer is project-scoped only in the explicit receipt filter."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock
from backend.features.supplier_access.fulfilment import internal_fulfilment_filter


class ReceiptRoleTests(unittest.TestCase):
    def test_chief_is_not_added_to_generic_warehouse_roles(self):
        tree=ast.parse(Path('backend/main.py').read_text())
        generic=next(node.value for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WAREHOUSE_ROLES' for t in node.targets))
        self.assertNotIn('главный_инженер', ast.literal_eval(generic))

    def test_chief_requires_receipt_opt_in_and_keeps_project_package_scope(self):
        actor={'role':'главный_инженер','company_id':2}
        deps={'can_see_all_company_data':lambda user:False,
              'scoped_project_filter':Mock(return_value=(' AND d.project=ANY(%s)',[['School']])),
              'package_access_filter':Mock(return_value=(' AND d.package=ANY(%s)',[['Main']])),
              'worker_execution_roles':()}
        args=dict(company_column='d.company_id',project_column='d.project',package_column='d.package',deps=deps)
        sql,values=internal_fulfilment_filter([actor],**args)
        self.assertEqual(sql,'FALSE')
        deps['scoped_project_filter'].assert_not_called()
        sql,values=internal_fulfilment_filter([actor],additional_project_roles=('главный_инженер',),**args)
        self.assertIn('d.company_id=%s',sql)
        self.assertIn('d.project=ANY(%s)',sql)
        self.assertIn('d.package=ANY(%s)',sql)
        self.assertEqual(values,[2,['School'],['Main']])
        deps['scoped_project_filter'].assert_called_once_with(actor,'d.project')
