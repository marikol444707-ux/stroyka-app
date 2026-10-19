import unittest
from scripts.jev_eis_probe import classify, verify_ca, probe
from unittest.mock import patch
from types import SimpleNamespace
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

    def test_worker_failure_retains_structured_reason_and_cleanup(self):
        failure = SimpleNamespace(returncode=1, stdout='{"ok":false,"status":"search_result_not_verified"}', stderr='private diagnostics')
        cleanup = SimpleNamespace(returncode=0, stdout='', stderr='')
        with patch('scripts.jev_eis_probe.subprocess.run', side_effect=[failure, cleanup]) as run:
            self.assertEqual(probe('кабель')['status'], 'search_result_not_verified')
            self.assertEqual(run.call_args.args[0][:3], ['docker', 'rm', '-f'])

    def test_empty_search_is_a_verified_result(self):
        html='<title>Закупки</title><input name="searchString" value="неттовара"><div>0 записей</div><div>Поиск не дал результатов</div>'
        result=classify(html, url='https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=неттовара', query='неттовара')
        self.assertTrue(result['ok'])
        self.assertTrue(result['search_execution_verified'])
        self.assertEqual(result['status'], 'keyword_search_empty')
        self.assertFalse(classify(html, query='неттовара')['ok'])

    def test_hidden_empty_search_text_is_not_evidence(self):
        html='<title>Закупки</title><input name="searchString" value="кабель"><script>0 записей Поиск не дал результатов</script>'
        result=classify(html, url='https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=кабель', query='кабель')
        self.assertFalse(result['ok'])

    def test_empty_marker_hidden_from_browser_cannot_confirm_empty_results(self):
        html='<title>Закупки</title><input name="searchString" value="кабель"><div hidden>0 записей Поиск не дал результатов</div>'
        result=classify(html, url='https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=кабель', query='кабель', visible_text='Результаты поиска')
        self.assertFalse(result['ok'])

    def test_official_ca_matches_pin(self):
        verify_ca(Path(__file__).resolve().parent.parent / 'dev_control/certificates/russian-trusted-root.pem')

    def test_substituted_ca_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ca.pem'
            path.write_text('-----BEGIN CERTIFICATE-----\nYWJj\n-----END CERTIFICATE-----\n')
            with self.assertRaises(ValueError): verify_ca(path)

if __name__ == '__main__': unittest.main()
