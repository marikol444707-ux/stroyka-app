import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('jev_eis_search.py')
SPEC = importlib.util.spec_from_file_location('jev_eis_search', SOURCE)
eis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eis)


class EISSearchTests(unittest.TestCase):
    def test_query_explicitly_selects_one_law_active_stage_and_first_page(self):
        from urllib.parse import parse_qs, urlsplit
        params = parse_qs(urlsplit(eis.build_url('капремонт Ставрополь', '615-ПП')).query)
        self.assertEqual(params['ppRf615'], ['on'])
        self.assertNotIn('fz44', params)
        self.assertEqual(params['af'], ['on'])
        self.assertEqual(params['pageNumber'], ['1'])
        self.assertEqual(params['recordsPerPage'], ['_10'])

    def test_unsupported_law_and_query_are_rejected(self):
        with self.assertRaises(ValueError):
            eis.build_url('ремонт', 'unknown')
        with self.assertRaises(ValueError):
            eis.build_url('x' * 101, '44-ФЗ')

    def test_rss_maps_official_notice_law_and_evidence_without_claiming_region(self):
        notice = '0821400000126000233'
        xml = f'''<rss><channel><item>
          <title>Электронный аукцион №{notice}</title>
          <link>https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={notice}</link>
          <description><![CDATA[<strong>Этап закупки:</strong> Подача заявок<br/>
            <a href="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={notice}">Капитальный ремонт здания</a>]]></description>
          <author>Заказчик, Ставрополь</author><pubDate>Thu, 22 Oct 2026 06:42:01 GMT</pubDate>
        </item></channel></rss>'''
        row, = eis.parse_rss(xml.encode(), '44-ФЗ', 'капитальный ремонт Ставрополь')
        self.assertEqual(row['id'], notice)
        self.assertEqual(row['source'], 'ЕИС')
        self.assertEqual(row['regime'], '44-ФЗ')
        self.assertEqual(row['status'], 'Подача заявок')
        self.assertEqual(row['region_scope'], 'not_filtered')
        self.assertEqual(row['region'], '')
        self.assertEqual(row['title'], 'Капитальный ремонт здания')

    def test_non_official_or_malformed_notice_links_are_discarded(self):
        xml = '''<rss><channel><item><title>Извещение №123</title>
        <link>https://evil.example/epz/order/notice/ea20/view/common-info.html?regNumber=123</link>
        <description>Капитальный ремонт</description></item></channel></rss>'''
        self.assertEqual(eis.parse_rss(xml, '223-ФЗ', 'ремонт'), [])

    def test_report_url_has_only_expected_eis_host(self):
        self.assertTrue(eis._safe_notice_url('https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0821400000126000233'))
        self.assertFalse(eis._safe_notice_url('http://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0821400000126000233'))

    def test_search_deduplicates_same_notice_across_queries(self):
        row = {'id': '0821400000126000233', 'regime': '44-ФЗ', 'search_query': 'ремонт'}
        with patch.object(eis, '_ssl_context', return_value=object()), \
             patch.object(eis, 'fetch_search', side_effect=[[dict(row)], [dict(row, search_query='строительство')]]):
            rows, sources = eis.search_eis(('ремонт', 'строительство'), ('44-ФЗ',))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['search_queries'], ['ремонт', 'строительство'])
        self.assertEqual(len(sources), 2)


if __name__ == '__main__':
    unittest.main()
