"""Fail closed when a company merge no longer matches the reviewed evidence."""
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from . import company_merge


class CompanyMergePreviewTests(TestCase):
    def setUp(self):
        self.company = dict(id=2, platform_account_id=1)
        self.target = dict(id=10, link_id=100, name='Target', link_version=2, inn='7799112233', ogrn='', user_id=None, profile={})
        self.source = dict(id=20, link_id=200, name='Source', link_version=3, inn='7799112233', ogrn='', user_id=None, profile={})

    def review(self, document='old', company=None, target=None):
        cur = MagicMock()
        cur.fetchall.side_effect = [[dict(id=42, fingerprint=document)], [], []]
        return company_merge.preview_for_pair(cur, company or self.company, target or self.target, self.source)

    def test_fingerprint_binds_document_contents_legal_values_and_company(self):
        original = self.review()
        self.assertEqual(original['documents'], dict(supplier_invoices=1, warehouse_invoices=0, supplier_offers=0))
        self.assertEqual(len(original['reviewVersion']), 64)
        self.assertEqual(original, self.review())
        self.assertNotEqual(original['reviewVersion'], self.review(document='changed')['reviewVersion'])
        self.assertNotEqual(original['reviewVersion'], self.review(company=dict(id=3, platform_account_id=1))['reviewVersion'])
        self.assertNotEqual(original['reviewVersion'], self.review(target={**self.target, 'inn': '7799112234'})['reviewVersion'])

    def test_missing_wrong_or_stale_preview_never_applies_merge(self):
        for supplied in (None, '', '0' * 64):
            cur = MagicMock()
            directory = MagicMock()
            @contextmanager
            def transaction(*args, **kwargs):
                yield cur, self.company, dict(role='директор')
            directory.transaction = transaction
            review = self.review()
            with patch.object(company_merge, 'pair', return_value=(self.target, self.source)), \
                 patch.object(company_merge, 'preview_for_pair', return_value=review), \
                 patch.object(company_merge, 'apply_pair') as apply:
                with self.assertRaises(HTTPException) as caught:
                    company_merge.confirm(directory, dict(confirmed=True, companyId=2, sourceId=20,
                                          targetVersion=2, sourceVersion=3, expectedReview=supplied), {}, (), 10)
                self.assertEqual(caught.exception.status_code, 409)
                apply.assert_not_called()
                directory.audit.assert_not_called()
