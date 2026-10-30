"""Synthetic evidence only. These tests establish no live platform coverage."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import tempfile
import unittest

from .model import Candidate, Document, Fact, Profile, public_url
from .policy import assess
from .registry import compare, deduplicate, registry
from .runner import SourceResult, render, run
from .sources import Source, source_registry
from .readers import Page, PublicAdapter
from ..state import Scope, RequestConflict

NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
HOSTS = {'b2b': ('www.b2b-center.ru',), 'owner': ('owner.example',)}
SCOPE = Scope(71, 'telegram:fixture-owner')
BASE = {'title': 'Капремонт санатория', 'counterparty': 'Синтетический заказчик',
        'role': 'owner', 'work_address': 'г. Кисловодск, условный объект',
        'work_region': 'Ставропольский край', 'work_scope': 'Ремонт кровли 3000 м²',
        'kind': 'capital_repair', 'regime': 'commercial', 'price': '5000000',
        'currency': 'RUB', 'stage': 'accepting', 'deadline': '2026-11-15T12:00:00+03:00',
        'payment': 'advance', 'advance_conditions': 'Аванс 20% под БГ; зачёт по этапам'}


def candidate(changes=None, *, source='b2b', number='fixture-1', kind='card', timestamp=NOW):
    values = {**BASE, **(changes or {})}
    values = {key: value for key, value in values.items() if value is not None}
    text = '\n'.join(f'{key}: {value}' for key, value in values.items())
    doc = Document('card', source, 'https://' + HOSTS[source][0] + '/fixture/' + number,
                   'Синтетическая карточка', kind, timestamp, text)
    facts = {key: (Fact(value, 'card', f'{key}: {value}', 'Карточка, поле ' + key),)
             for key, value in values.items()}
    return Candidate(source, number, (doc,), facts)


def checked(item):
    return SourceResult('checked', (item,), (item.documents[0],))


class PolicyTests(unittest.TestCase):
    def check(self, changes=None, **kwargs):
        return assess(candidate(changes, **kwargs), NOW, HOSTS)

    def test_confirmed_primary_direct_order(self):
        row = self.check()
        self.assertEqual(row['bucket'], 'priority')
        self.assertTrue(row['direct_contract_confirmed'])
        self.assertEqual(row['evidence']['price'][0]['locator'], 'Карточка, поле price')

    def test_unknown_price_is_not_zero_or_excluded(self):
        row = self.check({'price': None})
        self.assertEqual(row['bucket'], 'priority')
        self.assertIn('Бюджет: Требует уточнения', row['risks'])
        self.assertNotIn('price', row['values'])

    def test_threshold_exact_and_non_rub_never_converted(self):
        self.assertEqual(self.check({'price': '2999999.99'})['bucket'], 'excluded')
        self.assertEqual(self.check({'price': '3000000'})['bucket'], 'priority')
        row = self.check({'price': '100000', 'currency': 'EUR'})
        self.assertNotIn('Бюджет ниже ориентира', row['exclusions'])

    def test_region_is_worksite_not_customer_address(self):
        self.assertEqual(self.check({'work_region': 'Краснодарский край'})['bucket'], 'priority')
        self.assertEqual(self.check({'work_region': 'Москва'})['bucket'], 'excluded')
        self.assertEqual(self.check({'work_region': None})['bucket'], 'unconfirmed')

    def test_no_general_contractor_or_unconfirmed_operator(self):
        self.assertEqual(self.check({'role': 'general_contractor'})['bucket'], 'excluded')
        self.assertEqual(self.check({'role': 'authorized_operator'})['bucket'], 'unconfirmed')
        self.assertEqual(self.check({'role': 'authorized_operator', 'authority': 'confirmed'})['bucket'], 'priority')

    def test_regulated_procurements_are_separate(self):
        for regime in ('44-ФЗ', '223-ФЗ', '615-ПП'):
            self.assertEqual(self.check({'regime': regime})['bucket'], 'excluded')

    def test_non_target_work_excluded_and_adjacent_separate(self):
        for kind in ('goods', 'equipment_rental', 'maintenance', 'design_only'):
            self.assertEqual(self.check({'kind': kind})['bucket'], 'excluded')
        for kind in ('current_repair', 'engineering_modernization'):
            self.assertEqual(self.check({'kind': kind})['bucket'], 'adjacent')

    def test_stages_and_postpayment(self):
        for stage in ('suspended', 'cancelled', 'closed', 'archive'):
            self.assertEqual(self.check({'stage': stage})['bucket'], 'excluded')
        for stage in ('qualification', 'standing'):
            self.assertEqual(self.check({'stage': stage})['bucket'], 'qualifications')
        self.assertEqual(self.check({'payment': 'postpayment'})['bucket'], 'postpayment')

    def test_advance_requires_actual_conditions(self):
        self.assertEqual(self.check({'advance_conditions': None})['bucket'], 'unconfirmed')
        self.assertEqual(self.check({'payment': 'unknown', 'customer_materials': 'yes'})['bucket'], 'priority')

    def test_no_timezone_or_missing_deadline_is_explicit(self):
        row = self.check({'deadline': '2026-11-15T12:00:00'})
        self.assertTrue(any('часовой пояс' in risk for risk in row['risks']))
        self.assertIn('Дедлайн не подтверждён', self.check({'deadline': None})['risks'])
        self.assertEqual(self.check({'deadline': '2026-10-01T12:00:00+03:00'})['bucket'], 'unconfirmed')

    def test_aggregator_and_stale_card_never_confirm(self):
        for kwargs in ({'kind': 'aggregator'}, {'timestamp': NOW - timedelta(days=1)}):
            self.assertEqual(self.check(**kwargs)['bucket'], 'unconfirmed')

    def test_latest_primary_stage_overrides_old_snippet(self):
        old = candidate({'stage': 'closed'}, kind='aggregator', timestamp=NOW-timedelta(days=1))
        current = candidate()
        doc = replace(old.documents[0], id='old')
        facts = deepcopy(current.facts)
        facts['stage'] += (replace(old.facts['stage'][0], document='old'),)
        row = assess(replace(current, documents=(*current.documents, doc), facts=facts), NOW, HOSTS)
        self.assertEqual(row['values']['stage'], 'accepting')
        self.assertEqual(len(row['evidence']['stage']), 2)

    def test_contract_conflict_retains_both_and_quarantines(self):
        current = candidate()
        contract = Document('contract', 'b2b', current.documents[0].url, 'Договор', 'contract', NOW, 'Аванс: 0')
        facts = deepcopy(current.facts)
        facts['payment'] += (Fact('postpayment', 'contract', 'Аванс: 0', 'п. 5.1'),)
        row = assess(replace(current, documents=(*current.documents, contract), facts=facts), NOW, HOSTS)
        self.assertEqual(row['bucket'], 'unconfirmed')
        self.assertIn('payment', row['conflicts'])
        self.assertEqual(len(row['evidence']['payment']), 2)

    def test_qualification_is_entity_specific_and_not_inferred(self):
        item = candidate({'design_sro': 'required', 'construction_sro': 'required', 'fire_license': 'required'})
        row = assess(item, NOW, HOSTS, Profile(legal_entity='fixture ООО', qualifications=frozenset({'construction_sro'})))
        self.assertEqual(row['eligibility']['construction_sro'], 'Подтверждено профилем')
        self.assertNotEqual(row['eligibility']['design_sro'], 'Подтверждено профилем')
        self.assertNotEqual(row['eligibility']['fire_license'], 'Подтверждено профилем')

    def test_forged_quote_and_future_capture_rejected(self):
        item = candidate()
        for replacement in (replace(item, facts={**item.facts, 'price': (Fact('1', 'card', 'НЕ СУЩЕСТВУЕТ', 'п. 1'),)}),
                            candidate(timestamp=NOW+timedelta(minutes=1))):
            with self.assertRaises(ValueError): assess(replacement, NOW, HOSTS)

    def test_missing_reasons_are_distinct(self):
        item = candidate()
        for reason in ('Не указано', 'Не удалось проверить', 'Требует уточнения'):
            row = assess(replace(item, facts={**item.facts, 'vat': (Fact(missing=reason),)}), NOW, HOSTS)
            self.assertEqual(row['evidence']['vat'], [{'missing': reason}])

    def test_no_nonfinite_price_or_private_url(self):
        for amount in ('NaN', 'Infinity', '-1'):
            with self.assertRaises(ValueError): self.check({'price': amount})
        for url in ('http://example.com/a', 'https://127.0.0.1/a', 'https://user:secret@example.com',
                    'https://host.local/a', 'https://example.com\\@127.0.0.1'):
            self.assertFalse(public_url(url))


class RegistryTests(unittest.TestCase):
    def row(self, changes=None, **kwargs): return assess(candidate(changes, **kwargs), NOW, HOSTS)

    def test_first_baseline_then_new_and_changes(self):
        records, additions, changes, baseline = compare([self.row()], None)
        self.assertTrue(baseline); self.assertEqual(additions, [])
        next_records, additions, changes, baseline = compare([
            self.row({'price': '6000000'}), self.row(number='fixture-2')], {'records': records})
        self.assertFalse(baseline); self.assertEqual(len(additions), 1)
        price = next(item for item in changes if item['field'] == 'price')
        self.assertEqual((price['before'], price['after']), ('5000000', '6000000'))
        self.assertTrue(any(item['field'] == 'document_revision' for item in changes))
        _, additions, changes, _ = compare(list(next_records.values()), {'records': next_records})
        self.assertEqual((additions, changes), ([], []))

    def test_cross_site_requires_explicit_ids_not_titles(self):
        a, b = self.row(), self.row(source='owner', number='other')
        self.assertEqual(len(deduplicate([a, b])), 2)
        ids = {'counterparty_id': 'fixture-inn', 'object_id': 'fixture-object', 'procedure_id': 'fixture-tender'}
        a, b = self.row(ids), self.row(ids, source='owner', number='other')
        merged = deduplicate([a, b])
        self.assertEqual(len(merged), 1); self.assertEqual(len(merged[0]['links']), 2)

    def test_conflicting_duplicates_keep_evidence(self):
        ids = {'counterparty_id': 'fixture-inn', 'object_id': 'fixture-object', 'procedure_id': 'fixture-tender'}
        row = deduplicate([self.row(ids), self.row({**ids, 'price': '9000000'}, source='owner')])[0]
        self.assertEqual(row['bucket'], 'unconfirmed')
        self.assertIn('price', row['conflicts']); self.assertNotIn('price', row['values'])

    def test_scope_conflict_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with registry(directory, SCOPE) as (_, save): save({'records': {}})
            with self.assertRaises(RequestConflict):
                with registry(directory, Scope(72, 'telegram:other')): pass
            target = Path(directory) / 'commercial-v3.json'
            target.unlink(); target.symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                with registry(directory, SCOPE): pass

    def test_inaccessible_field_is_not_announced_as_deleted_then_new(self):
        records, _, _, _ = compare([self.row()], None)
        records, _, changes, _ = compare([self.row({'price': None})], {'records': records})
        self.assertFalse(any(item['field'] == 'price' for item in changes))
        _, _, changes, _ = compare([self.row()], {'records': records})
        self.assertFalse(any(item['field'] == 'price' for item in changes))

    def test_existing_v2_or_foreign_namespace_not_adopted(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / '.jev-private-namespace').write_text('fixture-existing-v2')
            with self.assertRaises(ValueError):
                with registry(directory, SCOPE): pass
            self.assertFalse((Path(directory) / 'commercial-v3.json').exists())


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.sources = {'b2b': Source('b2b', 'B2B', 'platform', HOSTS['b2b'])}

    def run_job(self, request='fixture-run', adapter=None, **kwargs):
        return run(request, SCOPE, self.temp.name, adapters={} if adapter is None else {'b2b': adapter},
                   sources=self.sources, clock=lambda: NOW, **kwargs)

    def test_actual_pipeline_replay_does_not_call_reader(self):
        calls = []
        def reader(*args): calls.append(args); return checked(candidate())
        first = self.run_job(adapter=reader)
        second = self.run_job(adapter=lambda *_: self.fail('replayed search'))
        self.assertEqual(first, second); self.assertEqual(len(calls), 1)
        self.assertEqual(first['new_confirmed_count'], 0)
        self.assertIn('Первый базовый сбор', render(first))

    def test_source_not_connected_and_no_fake_empty(self):
        report = self.run_job()
        self.assertEqual(report['coverage'][0]['status'], 'not_connected')
        self.assertFalse(report['sources_complete'])
        report = self.run_job('another', lambda *_: SourceResult('checked'))
        self.assertEqual(report['coverage'][0]['status'], 'partial')

    def test_real_empty_capture_and_no_cards_counted_from_snippets(self):
        listing = candidate().documents[0]
        report = self.run_job(adapter=lambda *_: SourceResult('checked', (), (listing,)))
        self.assertTrue(report['sources_complete'])
        self.assertEqual(report['coverage'][0]['primary_cards'], 0)

    def test_outage_is_not_zero_and_no_secrets_in_report(self):
        self.run_job(adapter=lambda *_: checked(candidate()))
        def failing(*_): raise RuntimeError('PRIVATE_TOKEN_DO_NOT_PRINT')
        report = self.run_job('next', failing)
        self.assertEqual(report['coverage'][0]['status'], 'error')
        self.assertNotIn('PRIVATE_TOKEN', str(report))
        report = self.run_job('third', lambda *_: checked(candidate()))
        self.assertEqual(report['new_confirmed_count'], 0)
        self.assertEqual(report['change_count'], 0)

    def test_filtered_replay_conflicts_before_reader(self):
        self.run_job(adapter=lambda *_: checked(candidate()))
        with self.assertRaises(RequestConflict):
            self.run_job(adapter=lambda *_: self.fail('search'), profile=Profile(minimum_rub=Decimal('4000000')))

    def test_crash_reservation_never_repeats_search(self):
        def crash(*_): raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_job(adapter=crash)
        report = self.run_job(adapter=lambda *_: self.fail('repeat'))
        self.assertEqual(report['status'], 'interrupted')

    def test_catalog_is_expandable_and_never_claims_connection(self):
        sources = source_registry((Source('new-owner', 'Новый собственник', 'owner'),))
        self.assertIn('new-owner', sources)
        self.assertGreater(len(sources), 9)
        for key in ('tenderpro', 'ozon', 'agrokompleks', 'damate'):
            self.assertEqual(sources[key].hosts, ())


class ReaderTests(unittest.TestCase):
    def adapter(self, fetch, **kwargs):
        source = Source('b2b', 'B2B', 'platform', HOSTS['b2b'])
        return PublicAdapter(source, plan=lambda _: ('https://www.b2b-center.ru/listing',), fetch=fetch,
                             links=kwargs.get('links', lambda _: (candidate().documents[0].url,)),
                             extract=kwargs.get('extract', lambda card: replace(candidate(), documents=(card,),
                                 facts={key: tuple(replace(fact, document=card.id) for fact in facts)
                                        for key, facts in candidate().facts.items()})), clock=lambda: NOW)

    def test_public_listing_card_parser_to_scoped_registry(self):
        def fetch(url): return Page(url, 'ok', candidate().documents[0].text, NOW)
        adapter = self.adapter(fetch)
        with tempfile.TemporaryDirectory() as directory:
            report = run('fixture-e2e', SCOPE, directory, adapters={'b2b': adapter},
                         sources={'b2b': adapter.source}, clock=lambda: NOW)
        self.assertEqual(report['coverage'][0]['primary_cards'], 1)
        self.assertEqual(report['sections']['priority'][0]['number'], 'fixture-1')

    def test_captcha_stops_and_is_not_empty(self):
        calls = []
        def fetch(url): calls.append(url); return Page(url, 'captcha')
        result = self.adapter(fetch)(Profile(), NOW)
        self.assertEqual(result.status, 'captcha'); self.assertEqual(len(calls), 1)

    def test_foreign_endpoint_is_rejected_before_fetch(self):
        calls = []
        def fetch(url): calls.append(url); return Page(url, 'ok', 'fixture', NOW)
        adapter = self.adapter(fetch, links=lambda _: ('https://attacker.example/private',))
        with self.assertRaises(ValueError): adapter(Profile(), NOW)
        self.assertEqual(len(calls), 1)

    def test_redirect_or_fabricated_parser_capture_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter(lambda _: Page('https://www.b2b-center.ru/login', 'ok', 'fixture', NOW))(Profile(), NOW)
        with self.assertRaises(ValueError):
            self.adapter(lambda url: Page(url, 'ok', 'fixture', NOW), extract=lambda _: candidate())(Profile(), NOW)


class BundleTests(unittest.TestCase):
    def test_offline_bundle_never_claims_search_or_independent_verification(self):
        from dataclasses import asdict
        from .__main__ import evaluate
        item = candidate()
        document = asdict(item.documents[0]); document['checked_at'] = NOW.isoformat()
        payload = {'format': 3, 'candidates': [{'source': item.source, 'number': item.number,
                    'documents': [document], 'facts': {key: [asdict(fact) for fact in facts]
                                                      for key, facts in item.facts.items()}}]}
        report = evaluate(payload, now=NOW)
        self.assertFalse(report['search_executed'])
        self.assertFalse(report['independent_source_verification'])
        self.assertFalse(report['registry_changed'])
        self.assertEqual(report['results'][0]['bucket'], 'priority')

    def test_bundle_duplicate_keys_rejected(self):
        import json
        from .__main__ import _pairs
        with self.assertRaises(ValueError): json.loads('{"format":3,"format":2}', object_pairs_hook=_pairs)


if __name__ == '__main__': unittest.main()
