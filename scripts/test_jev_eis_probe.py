import unittest
from scripts.jev_eis_probe import classify, verify_ca
from pathlib import Path
import tempfile

class EisProbeTests(unittest.TestCase):
    def test_real_registry_is_access_not_completed_search(self):
        result = classify('<title>Закупки</title><input name="searchString">'
                          '<a href="/epz/order/notice/ea20/view/common-info.html?regNumber=123">№123</a>')
        self.assertTrue(result['ok'])
        self.assertFalse(result['search_execution_verified'])
        self.assertEqual(result['notice_links_observed'], 1)

    def test_homepage_is_not_registry(self):
        self.assertFalse(classify('<title>ЕИС</title>')['ok'])

    def test_certificate_failure_not_success(self):
        self.assertEqual(classify('ERR_CERT_AUTHORITY_INVALID')['status'], 'tls_failed')

    def test_404_is_not_empty_results(self):
        self.assertFalse(classify('<title>404 Not Found</title>')['ok'])

    def test_foreign_links_do_not_count(self):
        result=classify('<title>Закупки</title><input name="searchString">'
                        '<a href="https://evil.test/common-info.html?regNumber=123">№123</a>')
        self.assertFalse(result['ok'])

    def test_query_requires_both_url_and_form_confirmation(self):
        html='<title>Закупки</title><input name="searchString" value="кабель"><a href="/epz/order/notice/ea20/view/common-info.html?regNumber=123">123</a>'
        self.assertTrue(classify(html, url='https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=кабель', query='кабель')['search_execution_verified'])
        self.assertFalse(classify(html, url='https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=кирпич', query='кабель')['ok'])
        self.assertFalse(classify(html, query='кабель')['ok'])

    def test_official_ca_matches_pin(self):
        verify_ca(Path(__file__).resolve().parent.parent / 'dev_control/certificates/russian-trusted-root.pem')

    def test_substituted_ca_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ca.pem'
            path.write_text('-----BEGIN CERTIFICATE-----\nYWJj\n-----END CERTIFICATE-----\n')
            with self.assertRaises(ValueError): verify_ca(path)

if __name__ == '__main__': unittest.main()
