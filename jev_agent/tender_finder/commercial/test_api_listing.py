"""Offline transport/flow regression tests; no claim of live card acceptance."""
from contextlib import asynccontextmanager
import json
from unittest import TestCase
from unittest.mock import Mock

from .access import Decision
from .api_listing import observe, Reply, FEDERATION_API, MAX_BODY
from .b2b import Observation
from .model import Profile
from .platforms import platform_specs
from .portal_reader import source_bundle, collect_portal
from .test_commercial import NOW, SCOPE
from .test_platforms import CARDS, TEXT


def response(rows=(), total=None):
    return Reply(200, 'application/json; charset=utf-8', json.dumps({
        'data': list(rows), 'page': 1, 'limit': 10,
        'total_count': len(rows) if total is None else total}).encode())


ROW = {'id': CARDS['federation'].rsplit('/', 1)[1],
       'platform_type': 'SECTION_COMMERCIAL_PROCEDURES', 'status': 'STATUS_ACCEPTING_APPLICATIONS',
       'close_bid_date': 'malformed date is not a primary fact', 'role': 'owner',
       'region': 'untrusted organizer region'}


class ApiTests(TestCase):
    def setUp(self):
        self.profile = Profile(queries=('кровля',))
        self.spec = platform_specs(self.profile, NOW)['federation']
        self.allow = lambda _: Decision(True, 'allowed')

    def read(self, fetch, **kwargs):
        return observe(self.spec, self.profile, FEDERATION_API, clock=lambda: NOW,
                       access_check=self.allow, fetch=fetch, **kwargs)

    def test_all_selected_terms_and_work_regions_have_captured_search_bodies(self):
        fetch = Mock(return_value=response())
        result = self.read(fetch)
        bodies = [json.loads(call.args[1]) for call in fetch.call_args_list]
        self.assertEqual([body['name'] for body in bodies], list((*self.profile.queries, *self.profile.regions)))
        self.assertTrue(all(call.args[0] == FEDERATION_API for call in fetch.call_args_list))
        self.assertTrue(all(body['sections'] == ['SECTION_COMMERCIAL_PROCEDURES'] for body in bodies))
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.search_state['request_count'], 3)
        self.assertEqual(result.search_state['notice_urls'], [])
        self.assertEqual(len(json.loads(result.text)), 3)

    def test_discovery_deduplicates_links_and_does_not_parse_listing_facts(self):
        result = self.read(Mock(return_value=response((ROW,))))
        self.assertEqual(result.search_state['notice_urls'], [CARDS['federation']])
        self.assertIn('untrusted organizer region', result.text)
        self.assertFalse(hasattr(result, 'facts'))

    def test_access_checked_for_every_request_and_denial_does_not_fetch(self):
        fetch = Mock(return_value=response())
        permission = Mock(side_effect=[Decision(True, 'allowed'), Decision(False, 'robots_disallow')])
        result = observe(self.spec, self.profile, FEDERATION_API, clock=lambda: NOW,
                         access_check=permission, fetch=fetch)
        self.assertEqual(result.status, 'robots_disallow')
        self.assertEqual(fetch.call_count, 1)

    def test_html_challenge_redirect_auth_and_errors_never_prove_empty_search(self):
        for reply in (Reply(200, 'text/html', b'<html>Testing...</html>'),
                      Reply(302, 'application/json', b'{}'), Reply(503, 'text/plain', b'error'),
                      Reply(401, 'text/html', b'login'), Reply(200, 'application/json', b'not json')):
            with self.subTest(reply=reply):
                result = self.read(Mock(return_value=reply))
                self.assertNotEqual(result.status, 'ok')
                self.assertEqual(result.search_state['notice_urls'], [])

    def test_malformed_foreign_and_noncommercial_rows_fail_closed(self):
        for rows in (({**ROW, 'id': 'https://attacker.example/card'},),
                     ({**ROW, 'platform_type': 'SECTION_GOVERNMENT'},),
                     ({**ROW, 'status': 'CLOSED'},)):
            self.assertEqual(self.read(Mock(return_value=response(rows))).status, 'unavailable')

    def test_inconsistent_counts_duplicates_and_oversize_are_not_empty_success(self):
        for reply in (response(total=1), response(total=True),
                      Reply(200, 'application/json', b'{"data":[],"data":[],"page":1,"limit":10,"total_count":0}'),
                      Reply(200, 'application/json', b'x' * (MAX_BODY + 1))):
            self.assertEqual(self.read(Mock(return_value=reply)).status, 'unavailable')

    def test_deadline_preserves_completed_evidence_and_marks_partial_coverage(self):
        ticks = iter((0, 0, 151))
        fetch = Mock(return_value=response())
        result = self.read(fetch, monotonic=lambda: next(ticks))
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.search_state['request_count'], 1)
        self.assertEqual(result.search_state['limitations'], ['read_budget_exhausted'])
        self.assertEqual(fetch.call_count, 1)

    def test_transport_error_does_not_leak_private_error_text(self):
        result = self.read(Mock(side_effect=RuntimeError('PRIVATE_TOKEN')))
        self.assertEqual(result.status, 'unavailable')
        self.assertNotIn('PRIVATE_TOKEN', str(result))

    def test_rtender_uses_get_and_validates_exact_native_json_shape(self):
        spec = platform_specs(self.profile, NOW)['rtender']
        fetch = Mock(return_value=Reply(200, 'application/javascript;charset=UTF-8', b'{"list":[],"count":0,"totalCount":0}'))
        result = observe(spec, self.profile, spec.listings[0], clock=lambda: NOW,
                         access_check=self.allow, fetch=fetch)
        self.assertEqual(result.status, 'ok')
        self.assertIsNone(fetch.call_args.args[1])

    def test_legacy_mime_does_not_allow_executable_jsonp_or_federation_script(self):
        spec = platform_specs(self.profile, NOW)['rtender']
        result = observe(spec, self.profile, spec.listings[0], clock=lambda: NOW,
                         access_check=self.allow, fetch=lambda *_: Reply(200, 'application/javascript', b'callback({"list":[]})'))
        self.assertEqual(result.status, 'unavailable')
        self.assertEqual(self.read(lambda *_: Reply(200, 'application/javascript', response().body)).status, 'unavailable')

    def test_rtender_invalid_nonempty_page_is_not_silently_changed_into_empty_success(self):
        spec = platform_specs(self.profile, NOW)['rtender']
        data = {'list': [{'type': 'BUYING_GOVERNMENT'}], 'count': 1, 'totalCount': 1}
        result = observe(spec, self.profile, spec.listings[0], clock=lambda: NOW,
            access_check=self.allow, fetch=lambda *_: Reply(200, 'application/json', json.dumps(data).encode()))
        self.assertEqual(result.status, 'unavailable')


class BatchTests(TestCase):
    def test_batch_api_requests_share_the_card_read_budget(self):
        spec = platform_specs(Profile(), NOW)['federation']
        notices = ['https://etpp.ru/tenders/00000000-0000-0000-0000-' + f'{index:012d}' for index in range(40)]
        reads = []
        def read(url):
            reads.append(url)
            if url in spec.listings:
                return Observation(url, 'ok', NOW, 'Captured API responses', {
                    'url': url, 'notice_urls': notices, 'request_count': 14})
            return Observation(url, 'ok', NOW, TEXT)
        result = collect_portal(spec, read=read, clock=lambda: NOW)
        self.assertEqual(len(result.primary_captures), 26)
        self.assertEqual(len(reads), 27)  # 14 API requests represented by one listing + 26 cards
        self.assertIn('read_budget_exhausted', result.limitations)

    def test_empty_native_searches_never_open_browser(self):
        def fetch(url, body):
            return response() if body else Reply(200, 'application/json', b'{"list":[],"count":0,"totalCount":0}')
        opened = Mock(side_effect=AssertionError('browser should not open'))
        _, adapters = source_bundle(open_browser=opened, clock=lambda: NOW, scope=SCOPE,
            access_check=lambda _: Decision(True, 'allowed'), api_fetch=fetch)
        for key in ('federation', 'rtender'):
            result = adapters[key](Profile(queries=('кровля',)), NOW)
            self.assertEqual(result.status, 'partial')
            self.assertTrue(result.listings)
            self.assertEqual(result.candidates, ())
        opened.assert_not_called()

    def test_found_links_open_one_browser_and_require_fresh_primary_facts(self):
        opened, closed = [], []
        @asynccontextmanager
        async def browser(source):
            opened.append(source.id)
            async def call(method, args):
                if method == 'Page.navigate':
                    self.assertEqual(args['url'], CARDS['federation'])
                    return {}
                return {'result': {'value': {'url': CARDS['federation'], 'ready': 'complete',
                    'oversize': False, 'text': TEXT, 'links': []}}}
            try:
                yield call
            finally:
                closed.append(True)
        _, adapters = source_bundle(open_browser=browser, clock=lambda: NOW,
            access_check=lambda _: Decision(True, 'allowed'), api_fetch=Mock(return_value=response((ROW,))))
        result = adapters['federation'](Profile(queries=('кровля',)), NOW)
        self.assertEqual(opened, ['federation'])
        self.assertEqual(closed, [True])
        self.assertEqual(len(result.candidates), 1)
        self.assertNotIn('role', result.candidates[0].facts)
        self.assertEqual(result.candidates[0].facts['work_region'][0].value, 'Краснодарский край')

