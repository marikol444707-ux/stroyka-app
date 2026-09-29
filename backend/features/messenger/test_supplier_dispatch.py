import unittest
from unittest.mock import Mock, MagicMock
from .supplier_dispatch import dispatch_supplier_message

class SupplierDispatchTests(unittest.TestCase):
    def test_unclaimed_message_never_contacts_provider(self):
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value=None
        send=Mock()
        self.assertIsNone(dispatch_supplier_message(lambda:conn,1,send))
        send.assert_not_called()

    def test_claim_is_committed_before_network_and_unknown_never_requeued(self):
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value={'id':1,'company_id':2,'entity_id':3,'target_supplier_id':4,'supplier_user_id':5}
        def send(row):
            conn.commit.assert_called_once()
            raise TimeoutError('private provider detail')
        result=dispatch_supplier_message(lambda:conn,1,send)
        self.assertEqual(result['status'],'unconfirmed')
        self.assertNotIn('private',str(result))
        sql=' '.join(str(c.args[0]) for c in cur.execute.call_args_list)
        self.assertNotIn("SET status='queued'",sql)

    def test_commit_failure_prevents_network(self):
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value={'id':1,'company_id':2,'entity_id':3,'target_supplier_id':4,'supplier_user_id':5}
        conn.commit.side_effect=RuntimeError('db')
        send=Mock()
        with self.assertRaises(RuntimeError):dispatch_supplier_message(lambda:conn,1,send)
        send.assert_not_called()
