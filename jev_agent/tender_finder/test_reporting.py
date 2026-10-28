from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import unittest

from .contract import validate_v2_request
from .reporting import SourceOutcome, TenderEvidence, build_report, evaluate, official_url, requested_filters

NOW = datetime(2026, 10, 28, 10, tzinfo=timezone.utc)


def request(**overrides):
    value = {'version': 2, 'request_id': 'synthetic-request', 'region': 'Ставропольский край',
             'sources': ['commercial'], 'commercial_sources': ['B2B-Center'], 'topics': ['капремонт']}
    value.update(overrides)
    return validate_v2_request(value)


def card(**changes):
    fields = {'source': 'B2B-Center', 'external_id': 'synthetic-1',
              'url': 'https://www.b2b-center.ru/market/tender-synthetic-1/',
              'title': 'Synthetic: капитальный ремонт школы', 'checked_at': NOW,
              'customer': 'Synthetic customer', 'work_location': 'Synthetic work address',
              'work_region': 'Ставропольский край', 'location_basis': 'work_address',
              'price_rub': Decimal('5000000.00'), 'currency': 'RUB',
              'deadline': NOW + timedelta(days=5), 'status': 'accepting',
              'legal_regime': 'commercial', 'matched_topics': ('capital_repair',)}
    fields.update(changes)
    return TenderEvidence(**fields)


def outcome(req, **changes):
    fields = {'source': 'B2B-Center', 'status': 'ok_with_results', 'checked_at': NOW,
              'url': 'https://www.b2b-center.ru/app/next/market-search', 'queries_checked': 1,
              'pages_checked': 1, 'matched_count': 1, 'applied_filters': tuple(requested_filters(req))}
    fields.update(changes)
    return SourceOutcome(**fields)


def report(req, outcomes, cards):
    return build_report(req, 8, outcomes, cards, started_at=NOW, completed_at=NOW + timedelta(seconds=10))


class EvidencePolicyTests(unittest.TestCase):
    def test_verified_card_passes_and_unknowns_are_never_fabricated(self):
        self.assertEqual(evaluate(card(), request(), NOW), ('accepted', ()))
        decision, reasons = evaluate(card(price_rub=None, deadline=None, status='unknown'), request(), NOW)
        self.assertEqual(decision, 'review')
        self.assertTrue({'price_unknown', 'deadline_unknown', 'active_status_unknown'} <= set(reasons))

    def test_customer_region_cannot_prove_work_location(self):
        for basis in ('customer_region', 'unknown'):
            self.assertIn('work_region_unverified', evaluate(card(location_basis=basis), request(), NOW)[1])
        self.assertEqual(evaluate(card(work_region='Москва'), request(), NOW)[0], 'excluded')

    def test_expired_deadline_overrides_accepting_label(self):
        decision, reasons = evaluate(card(deadline=NOW), request(), NOW)
        self.assertEqual(decision, 'excluded')
        self.assertIn('deadline_expired', reasons)
        self.assertEqual(evaluate(card(deadline=NOW - timedelta(days=1), status='closed'), request(active_only=False), NOW)[0], 'accepted')

    def test_unknown_currency_never_uses_price_as_rubles(self):
        foreign = card(currency='USD', price_rub=None, raw_price='10 USD')
        decision, reasons = evaluate(foreign, request(price_min_rub=100), NOW)
        self.assertEqual(decision, 'review')
        self.assertNotIn('price_below_range', reasons)
        self.assertIn('currency_unverified_for_ruble_filter', reasons)
        with self.assertRaises(ValueError):
            card(currency='USD', price_rub=Decimal('10'))

    def test_known_prices_and_deadline_bounds_exclude_with_specific_reasons(self):
        self.assertIn('price_below_range', evaluate(card(), request(price_min_rub=6000000), NOW)[1])
        self.assertIn('price_above_range', evaluate(card(), request(price_max_rub=4000000), NOW)[1])
        self.assertIn('deadline_after_range', evaluate(card(), request(deadline_to='2026-10-29'), NOW)[1])

    def test_mixed_platform_regime_is_checked_independently(self):
        regulated = card(legal_regime='223-ФЗ')
        self.assertEqual(evaluate(regulated, request(), NOW)[0], 'excluded')
        self.assertEqual(evaluate(regulated, request(legal_regimes=['223-ФЗ']), NOW)[0], 'accepted')
        with self.assertRaises(ValueError):
            card(source='eis:44-ФЗ', url='https://zakupki.gov.ru/notice', legal_regime='223-ФЗ')

    def test_unknown_topic_and_keywords_are_reviewed_instead_of_invented(self):
        self.assertIn('topic_unverified', evaluate(card(matched_topics=()), request(), NOW)[1])
        self.assertIn('keyword_not_verified_in_evidence', evaluate(card(), request(keywords=['котельная']), NOW)[1])
        self.assertEqual(evaluate(card(), request(exclude_keywords=['школы']), NOW)[0], 'excluded')

    def test_official_url_rejects_unrelated_hosts_credentials_and_http(self):
        for url in ('http://www.b2b-center.ru/1', 'https://www.b2b-center.ru.evil.example/1',
                    'https://secret@www.b2b-center.ru/1', 'https://www.b2b-center.ru:8443/1',
                    'https://www.b2b-center.ru/1#fragment', 'https://www.b2b-center.ru/\n1'):
            self.assertFalse(official_url('B2B-Center', url), url)
        self.assertTrue(official_url('B2B-Center', card().url))


class ReportTests(unittest.TestCase):
    def test_complete_empty_requires_verified_checks_and_discloses_coverage(self):
        req = request()
        value = report(req, [outcome(req, status='ok_empty', matched_count=0)], [])
        self.assertEqual(value['status'], 'completed')
        self.assertEqual(value['tenders'], [])
        self.assertEqual(value['unapplied_filters'], [])
        self.assertIn('полный охват рынка не подтверждён', value['warnings'][0])

    def test_unverified_empty_search_is_partial_not_proof_of_absence(self):
        req = request()
        value = report(req, [outcome(req, status='ok_empty', matched_count=0, applied_filters=())], [])
        self.assertEqual(value['status'], 'partial')
        self.assertIn('region', value['unapplied_filters'])
        self.assertTrue(any('не доказывает' in warning for warning in value['warnings']))

    def test_missing_or_failed_sources_remain_visible(self):
        req = request(commercial_sources=['B2B-Center', 'Росэлторг'])
        value = report(req, [outcome(req, status='ok_empty', matched_count=0)], [])
        self.assertEqual(value['status'], 'partial')
        self.assertEqual({row['source']: row['status'] for row in value['sources_status']},
                         {'B2B-Center': 'ok_empty', 'Росэлторг': 'not_tested'})
        failed = outcome(request(), status='error', matched_count=0, pages_checked=0, error_code='timeout')
        self.assertEqual(report(request(), [failed], [])['status'], 'failed')

    def test_source_failure_does_not_discard_other_source_results(self):
        req = request(commercial_sources=['B2B-Center', 'Росэлторг'])
        failure = outcome(req, source='Росэлторг', status='blocked_by_login_or_captcha',
                          url='https://www.roseltorg.ru/', pages_checked=0, matched_count=0,
                          applied_filters=(), error_code='captcha')
        value = report(req, [outcome(req), failure], [card()])
        self.assertEqual(value['status'], 'partial')
        self.assertEqual(len(value['tenders']), 1)
        self.assertEqual(value['errors'], [{'source': 'Росэлторг', 'code': 'captcha'}])

    def test_deduplication_preserves_ids_and_conflicting_facts_for_review(self):
        req = request()
        value = report(req, [outcome(req)], [card(), card(checked_at=NOW + timedelta(seconds=1))])
        self.assertEqual(value['deduplicated_count'], 1)
        self.assertEqual(len(value['tenders']), 1)
        conflict = report(req, [outcome(req)], [card(), card(price_rub=Decimal('6000000'))])
        self.assertEqual(conflict['status'], 'partial')
        self.assertEqual(len(conflict['tenders']), 2)
        self.assertTrue(all(row['needs_manual_review'] for row in conflict['tenders']))
        self.assertTrue(all('duplicate_identity_conflict' in row['reasons'] for row in conflict['tenders']))

    def test_same_title_with_different_ids_is_not_merged(self):
        req = request()
        value = report(req, [outcome(req, matched_count=2)], [card(), card(external_id='synthetic-2', url=card().url + '2')])
        self.assertEqual(value['deduplicated_count'], 0)
        self.assertEqual(len(value['tenders']), 2)

    def test_unknown_price_and_deadline_remain_null_and_require_review(self):
        req = request()
        value = report(req, [outcome(req)], [card(price_rub=None, deadline=None)])
        self.assertEqual(value['status'], 'partial')
        self.assertIsNone(value['tenders'][0]['price_rub'])
        self.assertIsNone(value['tenders'][0]['deadline'])
        self.assertTrue(value['tenders'][0]['needs_manual_review'])
        json.dumps(value)

    def test_report_rejects_foreign_sources_and_false_empty_outcomes(self):
        req = request()
        with self.assertRaises(ValueError):
            report(req, [outcome(req, status='ok_empty', matched_count=0)], [card()])
        with self.assertRaises(ValueError):
            report(req, [outcome(req)], [card(source='Росэлторг', url='https://www.roseltorg.ru/procedure/1')])

    def test_source_checks_must_belong_to_this_run(self):
        req = request()
        with self.assertRaises(ValueError):
            report(req, [outcome(req, checked_at=NOW - timedelta(days=1))], [])
        with self.assertRaises(ValueError):
            report(req, [outcome(req)], [card(checked_at=NOW + timedelta(days=1))])

    def test_bad_source_evidence_cannot_be_marked_successful(self):
        req = request()
        for changes in ({'status':'ok_empty'}, {'pages_checked':0}, {'checked_at':None},
                        {'status':'error'}, {'status':'not_tested'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                outcome(req, **changes)

    def test_no_search_executed_is_failed_and_every_source_is_listed(self):
        value = report(request(), [], [])
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['sources_status'][0]['status'], 'not_tested')

    def test_unexecuted_source_cannot_leak_credentials_in_a_placeholder_url(self):
        with self.assertRaisesRegex(ValueError, 'invalid_source_url'):
            SourceOutcome('B2B-Center', 'not_tested', url='https://PRIVATE@www.b2b-center.ru/')

    def test_input_budget_does_not_consume_an_unbounded_source_iterator(self):
        consumed = []
        def stream():
            while True:
                consumed.append(1)
                yield card()
        req = request()
        with self.assertRaisesRegex(ValueError, 'report_input_limit'):
            report(req, [outcome(req)], stream())
        self.assertEqual(len(consumed), 2001)

    def test_foreign_currency_amount_is_not_mislabeled_as_rubles(self):
        req = request(price_min_rub=100)
        value = report(req, [outcome(req)], [card(price_rub=None, currency='USD', raw_price='10 USD')])
        self.assertIsNone(value['tenders'][0]['price_rub'])
        self.assertEqual(value['tenders'][0]['raw_price'], '10 USD')
        self.assertTrue(value['tenders'][0]['needs_manual_review'])

    def test_record_limit_is_disclosed_and_not_presented_as_complete_coverage(self):
        req = request(limit=1)
        value = report(req, [outcome(req, matched_count=2)], [card(), card(external_id='synthetic-2')])
        self.assertEqual(len(value['tenders']), 1)
        self.assertEqual(value['omitted_by_limit'], 1)
        self.assertEqual(value['status'], 'partial')


if __name__ == '__main__':
    unittest.main()
