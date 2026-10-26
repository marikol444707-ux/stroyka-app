import unittest
from unittest.mock import Mock, patch

from scripts.inspect_invoice_binding import child_main, inspect_record


def row():
    return {'id':168,'number':'232604','total_with_vat':106880,'company_id':41,'company_name':'Synthetic Company',
        'supplier_id':40,'supplier_name':'Synthetic Vendor','supplier_invoice_id':72,'status':'Принята',
        'accounting_status':'На проверке','warehouse_photo':'private-url-never-print', 'warehouse_photos':'[]',
        'linked_invoice_id':72,'linked_supplier_id':40,'linked_supplier_name':'Synthetic Vendor',
        'warehouse_invoice_id':168,'linked_status':'На утверждении','linked_file':'','linked_photo':'private-url-never-print',
        'supplier_in_company':True}


class InspectInvoiceBindingTest(unittest.TestCase):
    def test_reads_one_exact_record_and_reports_links_without_exposing_urls(self):
        cur=Mock()
        cur.fetchone.return_value=row()
        report=inspect_record(cur,168,'232604',106880)
        self.assertEqual(cur.execute.call_args.args[1],(168,))
        self.assertIn('si.company_id=w.company_id',cur.execute.call_args.args[0])
        self.assertTrue(report['accountingInvoice']['backLinkMatches'])
        self.assertTrue(report['warehouseInvoice']['hasOriginal'])
        self.assertNotIn('private-url',str(report))

    def test_a_missing_or_other_company_link_does_not_expose_foreign_invoice_data(self):
        cur=Mock()
        value=row()
        for field in ['linked_invoice_id','linked_supplier_id','linked_supplier_name','warehouse_invoice_id','linked_status','linked_file','linked_photo']:
            value[field]=None
        cur.fetchone.return_value=value
        report=inspect_record(cur,168,'232604',106880)
        self.assertFalse(report['accountingInvoice']['foundInSameCompany'])
        self.assertFalse(report['accountingInvoice']['backLinkMatches'])

    def test_mismatching_invoice_is_not_reported_as_the_requested_document(self):
        cur=Mock()
        cur.fetchone.return_value={**row(),'number':'Different invoice'}
        report=inspect_record(cur,168,'232604',106880)
        self.assertEqual(report['state'],'candidate_does_not_match_requested_upd')
        self.assertNotIn('warehouseInvoice',report)

    def test_transaction_is_readonly_and_rolled_back_even_on_failure(self):
        connection=Mock()
        cur=connection.cursor.return_value.__enter__.return_value if hasattr(connection.cursor.return_value,'__enter__') else Mock()
        from unittest.mock import MagicMock
        connection.cursor.return_value=MagicMock()
        connection.cursor.return_value.__enter__.return_value=cur
        cur.fetchone.side_effect=RuntimeError('Synthetic failure')
        with patch('backend.db.get_db',return_value=connection):
            with self.assertRaises(RuntimeError):
                child_main((168,'232604',106880))
        connection.set_session.assert_called_once_with(readonly=True,autocommit=False)
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()


if __name__=='__main__':
    unittest.main()
