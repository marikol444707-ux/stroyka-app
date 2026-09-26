"""0018 derived mirrors remain protected by real legacy HTTP handlers."""
import os
import unittest

from . import test_attachments_postgres as attachments
from . import test_document_writer_guards_postgres as writers


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AttachedWriterRoutesTests(unittest.TestCase):
    sql = attachments.AttachmentTests.sql
    body = attachments.AttachmentTests.body
    policy = attachments.AttachmentTests.policy
    execute = attachments.AttachmentTests.execute
    pair_policy = attachments.AttachmentTests.pair_policy
    seed_warehouse = attachments.AttachmentTests.seed_warehouse
    attachment_body = attachments.AttachmentTests.attachment_body
    attach = attachments.AttachmentTests.attach
    setUp = attachments.AttachmentTests.setUp
    api = writers.DocumentWriterGuardTests.api
    request = writers.DocumentWriterGuardTests.request
    snapshot = writers.DocumentWriterGuardTests.snapshot
    assert_denied_unchanged = writers.DocumentWriterGuardTests.assert_denied_unchanged

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        attachments.AttachmentTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def test_attached_pair_rejects_all_four_legacy_writers(self):
        self.attach()
        for route in ('supplier_put', 'supplier_delete', 'warehouse_put', 'warehouse_delete'):
            with self.subTest(route=route):
                self.assert_denied_unchanged(route)
        # The dedicated internal engine still owns future changes.
        self.execute(self.body('10'), policy=self.pair)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (self.warehouse,)), [(70,)])
