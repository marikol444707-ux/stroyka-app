import ast
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import unittest

from .catalog import BY_ID, TOPICS, resolve_topic
from .contract import InvalidRequest, PROVIDERS, parse_v2_request, validate_v2_request


def request(**changes):
    value = {'version': 2, 'request_id': 'search-20261028-001', 'region': 'Ставропольский край',
             'sources': ['eis', 'commercial'], 'topics': ['капремонт', 'электромонтаж']}
    value.update(changes)
    return value


class ContractTests(unittest.TestCase):
    def reject(self, value, field, code):
        with self.assertRaises(InvalidRequest) as caught:
            validate_v2_request(value)
        self.assertIn((field, code), [(issue.field, issue.code) for issue in caught.exception.issues])

    def test_example_request_maps_only_supported_cli_fields_with_trusted_company(self):
        raw = request(commercial_sources=['B2B-Center', 'Росэлторг', 'Фабрикант'],
                      deadline_from='2026-10-28', deadline_to='2026-11-30',
                      price_min_rub=1000000, price_max_rub=50000000)
        normalized = parse_v2_request(json.dumps(raw, ensure_ascii=False))
        profile = normalized.company_profile(17)
        self.assertEqual(set(profile), {'companyId', 'region', 'searchTerms', 'sourceProviders'})
        self.assertEqual(profile['companyId'], 17)
        self.assertEqual(normalized.price_min_rub, Decimal('1000000.00'))
        self.assertEqual(normalized.deadline_from.utcoffset(), timedelta(hours=3))
        self.assertEqual(normalized.deadline_from.hour, 0)
        self.assertEqual(normalized.deadline_to.hour, 23)
        self.assertEqual(normalized.deadline_to.microsecond, 999999)

    def test_unknown_fields_and_company_override_have_specific_errors(self):
        with self.assertRaises(InvalidRequest) as caught:
            validate_v2_request(request(companyId=999, arbitrary='not-executed'))
        self.assertEqual({issue.field: issue.code for issue in caught.exception.issues},
                         {'arbitrary': 'unknown_field', 'companyId': 'untrusted_company_field'})
        self.assertNotIn('not-executed', json.dumps(caught.exception.as_dict()))

    def test_legacy_is_not_silently_reinterpreted_as_v2(self):
        self.reject(request(version=1), 'version', 'v2_required')
        self.reject(request(version=True), 'version', 'v2_required')

    def test_unknown_and_empty_logical_sources(self):
        self.reject(request(sources=[]), 'sources', 'invalid_list')
        self.reject(request(sources=['shell']), 'sources', 'unknown_source_group')
        self.reject(request(commercial_sources=[]), 'commercial_sources', 'invalid_list')
        self.reject(request(commercial_sources=['Unverified platform']), 'commercial_sources', 'unknown_provider')

    def test_sources_and_legal_regimes_cannot_contradict_each_other(self):
        self.reject(request(sources=['eis'], commercial_sources=['B2B-Center']), 'commercial_sources', 'source_group_mismatch')
        self.reject(request(sources=['eis'], legal_regimes=['commercial']), 'legal_regimes', 'source_group_mismatch')
        mixed_platform = validate_v2_request(request(sources=['commercial'], legal_regimes=['223-ФЗ']))
        self.assertEqual(mixed_platform.legal_regimes, ('223-ФЗ',))
        self.reject(request(legal_regimes=[]), 'legal_regimes', 'invalid_list')
        self.reject(request(legal_regimes=['unknown']), 'legal_regimes', 'unknown_legal_regime')

    def test_eis_only_request_cannot_invoke_commercial_profile(self):
        normalized = validate_v2_request(request(sources=['eis']))
        self.assertEqual(normalized.commercial_sources, ())
        self.assertEqual(set(normalized.legal_regimes), {'44-ФЗ', '223-ФЗ', '615-ПП'})
        self.assertEqual(len(normalized.fingerprint(4)), 64)
        with self.assertRaises(InvalidRequest):
            normalized.company_profile(4)

    def test_region_and_topic_validation(self):
        self.reject(request(region='Москва'), 'region', 'unsupported_region')
        self.reject(request(topics=[]), 'topics', 'invalid_list')
        self.reject(request(topics=['неизвестное направление']), 'topics', 'unknown_topic')

    def test_phrase_plan_is_bounded_across_topics_and_keywords_without_truncation(self):
        self.reject(request(keywords=['фраза %02d' % index for index in range(19)]), 'keywords', 'search_plan_too_broad')
        self.reject(request(keywords=['x' * 81]), 'keywords', 'invalid_string_length')
        self.reject(request(keywords=['фраза'] * 21), 'keywords', 'invalid_list')
        valid = validate_v2_request(request(keywords=['  Школа ', 'школа']))
        self.assertEqual(valid.keywords, ('Школа',))

    def test_paths_and_shell_in_request_id_are_rejected(self):
        for identifier in ('../search', '/tmp/search', 'a;touch-x', '$(command)', 'a\nb', 'x' * 65):
            with self.subTest(identifier=identifier):
                self.reject(request(request_id=identifier), 'request_id', 'invalid_request_id')

    def test_prices_remain_exact_and_unknown_is_not_zero(self):
        normalized = parse_v2_request(json.dumps(request(price_min_rub=0.1, price_max_rub=0.29)))
        self.assertEqual(normalized.price_min_rub, Decimal('0.10'))
        self.assertEqual(normalized.price_max_rub, Decimal('0.29'))
        self.assertIsNone(validate_v2_request(request()).price_min_rub)
        self.assertEqual(validate_v2_request(request(price_min_rub=0)).price_min_rub, Decimal('0.00'))
        for value in (-1, True, '1000000', float('inf'), float('nan'), 0.001, 1000000000001):
            with self.subTest(value=repr(value)):
                self.reject(request(price_min_rub=value), 'price_min_rub', 'invalid_price')
        self.reject(request(price_min_rub=20, price_max_rub=10), 'price_max_rub', 'inverted_prices')

    def test_deadline_must_be_real_iso_with_offset_and_valid_bounds(self):
        for value in ('2026-02-30', '28.10.2026', '2026-10-28T12:00', '2026-10-28T12:00+03:99', '2026-10-28T25:00Z'):
            with self.subTest(value=value):
                self.reject(request(deadline_from=value), 'deadline_from', 'invalid_deadline')
        self.reject(request(deadline_from='2026-11-30', deadline_to='2026-10-28'), 'deadline_to', 'inverted_deadlines')
        normalized = validate_v2_request(request(deadline_from='2026-10-28T09:00:00Z'))
        self.assertEqual(normalized.deadline_from.hour, 12)

    def test_boolean_and_limit_types_are_strict(self):
        self.reject(request(active_only=1), 'active_only', 'invalid_boolean')
        for value in (0, 51, True, 2.0, '5'):
            self.reject(request(limit=value), 'limit', 'invalid_limit')

    def test_duplicate_json_fields_nonfinite_numbers_and_large_payloads(self):
        for raw, code in [(b'{"version":2,"version":2}', 'duplicate_field'),
                          (b'{"value":NaN}', 'nonfinite_number'),
                          (b' ' * 32769, 'request_too_large'), (b'\xff', 'invalid_json')]:
            with self.subTest(code=code), self.assertRaises(InvalidRequest) as caught:
                parse_v2_request(raw)
            self.assertEqual(caught.exception.issues[0].code, code)

    def test_fingerprint_normalizes_aliases_and_is_tenant_scoped(self):
        first = validate_v2_request(request(topics=['капремонт', 'электромонтаж'], keywords=['Школа']))
        second = validate_v2_request(request(topics=['Электромонтажные работы', 'Капитальный ремонт'],
                                              sources=['commercial', 'eis'], keywords=['школа']))
        self.assertEqual(first.fingerprint(1), second.fingerprint(1))
        self.assertNotEqual(first.fingerprint(1), first.fingerprint(2))
        self.assertNotEqual(first.fingerprint(1), validate_v2_request(request(limit=2)).fingerprint(1))
        for company in (None, True, 0, -1, '2'):
            with self.assertRaises(InvalidRequest):
                first.company_profile(company)


class CatalogTests(unittest.TestCase):
    def test_all_26_topics_have_distinct_ids_and_two_control_aliases(self):
        self.assertEqual(len(TOPICS), 26)
        self.assertEqual(len(BY_ID), 26)
        for topic in TOPICS:
            with self.subTest(topic=topic.id):
                self.assertEqual(resolve_topic(topic.name), topic.id)
                self.assertEqual(resolve_topic(topic.aliases[0]), topic.id)
                self.assertEqual(resolve_topic(topic.query), topic.id)
                self.assertEqual(topic.verified_sources, ())

    def test_occupational_safety_is_not_classified_as_construction(self):
        self.assertFalse(BY_ID['occupational_safety'].construction_related)
        self.assertTrue(BY_ID['electrical'].construction_related)

    def test_provider_allowlist_agrees_with_actual_server_runtime(self):
        source = Path(__file__).resolve().parents[1] / 'server_runtime/scripts/jev_commercial_search.py'
        tree = ast.parse(source.read_bytes())
        node = next(node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'ACTIVE_PROVIDERS' for target in node.targets))
        self.assertEqual(PROVIDERS, ast.literal_eval(node.value))


if __name__ == '__main__':
    unittest.main()
