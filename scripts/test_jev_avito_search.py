import unittest
from scripts.jev_avito_search import assess_page


class AvitoPageTest(unittest.TestCase):
    def test_homepage_after_submit_is_not_a_completed_search(self):
        report = assess_page('https://www.avito.ru/', 'Авито', 'Ставропольский край')
        self.assertEqual(report['status'], 'search_query_lost')
        self.assertFalse(report['ok'])

    def test_unrelated_search_is_rejected(self):
        report = assess_page('https://www.avito.ru/stavropolskiy_kray?q=полу+автомат',
                             'полу автомат', 'Ставропольский край')
        self.assertEqual(report['status'], 'search_query_changed')

    def test_national_results_do_not_pass_region_check(self):
        report = assess_page('https://www.avito.ru/all?q=кирпич+б%2Fу',
                             'кирпич б/у', 'Ставропольский край в рекомендациях')
        self.assertEqual(report['status'], 'search_region_not_verified')

    def test_query_url_without_matching_heading_is_not_proof(self):
        report = assess_page('https://www.avito.ru/stavropolskiy_kray?q=кирпич+б%2Fу',
                             'Товары в Ставропольском крае', 'Рекомендации для вас')
        self.assertEqual(report['status'], 'search_results_not_verified')

    def test_security_check_stops_before_model_calls(self):
        report = assess_page('https://www.avito.ru/', 'Доступ ограничен: проверка безопасности', '')
        self.assertEqual(report['status'], 'site_security_check')
        self.assertEqual(report['model_calls'], 0)

    def test_gateway_error_is_distinct_from_empty_results(self):
        report = assess_page('https://www.avito.ru/', 'HTTP 502', 'Bad gateway')
        self.assertEqual(report['status'], 'site_gateway_error')

    def test_external_redirect_is_rejected(self):
        self.assertEqual(assess_page('https://avito.ru.evil.test/', '', '')['status'], 'unexpected_origin')

    def test_visible_search_alone_is_still_not_five_verified_listings(self):
        report = assess_page('https://www.avito.ru/stavropolskiy_kray?q=кирпич+б%2Fу',
                             'Кирпич б/у в Ставропольском крае', 'Кирпич б/у')
        self.assertEqual(report['status'], 'search_page_observed')
        self.assertFalse(report['ok'])
        self.assertEqual(report['verified_listings'], [])


if __name__ == '__main__':
    unittest.main()
