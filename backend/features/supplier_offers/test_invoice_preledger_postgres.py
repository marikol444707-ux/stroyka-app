"""Offer creation compatibility before migration 0017; use a fresh database."""
import os
import unittest

from ..supplier_access import test_postgres_chain as chain
from . import test_invoice_ledger_guards_postgres as guarded


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class OfferInvoicePreledgerTests(unittest.TestCase):
    setUpClass = classmethod(chain.PostgresSupplyChainTests.setUpClass.__func__)
    setUp = guarded.OfferInvoiceLedgerTests.setUp
    sql = guarded.OfferInvoiceLedgerTests.sql
    api = guarded.OfferInvoiceLedgerTests.api
    create = guarded.OfferInvoiceLedgerTests.create
    test_unmanaged_duplicate_is_reused = guarded.OfferInvoiceLedgerTests.test_unmanaged_duplicate_is_reused
    test_new_invoice_and_event_remain_atomic = guarded.OfferInvoiceLedgerTests.test_new_invoice_and_event_remain_atomic
