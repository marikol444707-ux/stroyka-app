"""Read-only preflight for the owner's agreed public Avito search.

An observed search page is never reported as five verified listings.
"""
import re
from urllib.parse import parse_qs, urlencode, urlsplit


SEARCH_URL = ('https://www.avito.ru/stavropolskiy_kray/remont_i_stroitelstvo?'
              + urlencode({'q': 'кирпич б/у', 'localPriority': '0'}))


def assess_page(url, title, snapshot):
    report = {'ok': False, 'status': 'observation_missing', 'model_calls': 0,
              'verified_listings': []}
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname not in {'www.avito.ru', 'avito.ru'}
                or parts.username or parts.password or parts.port not in {None, 443}):
            return dict(report, status='unexpected_origin')
    except ValueError:
        return dict(report, status='unexpected_origin')
    if title.startswith('HTTP 502') or title.strip() == '502':
        return dict(report, status='site_gateway_error')
    if 'доступ ограничен' in title.casefold():
        return dict(report, status='site_security_check')
    queries = parse_qs(parts.query).get('q', [])
    if not queries:
        return dict(report, status='search_query_lost')
    if len(queries) != 1 or ' '.join(queries[0].casefold().split()) not in {'кирпич б/у', 'кирпич бу'}:
        return dict(report, status='search_query_changed')
    if parts.path.strip('/').split('/')[0] != 'stavropolskiy_kray':
        return dict(report, status='search_region_not_verified')
    if 'ставропольском крае' not in title.casefold():
        return dict(report, status='search_region_not_verified')
    if 'кирпич' not in title.casefold() or 'кирпич' not in snapshot.casefold():
        return dict(report, status='search_results_not_verified')
    return dict(report, status='search_page_observed')


def probe(browser_factory):
    with browser_factory() as browser:
        browser.call('browser_navigate', {'url': SEARCH_URL})
        # A fixed pause may leave the SPA's generic loading title visible.
        # Wait for the requested heading, then independently assess the result.
        # No challenge clicks, captcha solver, proxy rotation or task retries.
        try:
            browser.call('browser_wait_for', {'text': '«Кирпич б/у»'})
        except TimeoutError:
            # Preserve the actual site error, lost query or incomplete page.
            pass
        text = browser.call('browser_snapshot', {})
        url = re.search(r'^- Page URL: (.+)$', text, re.M)
        title = re.search(r'^- Page Title: (.+)$', text, re.M)
        if not url or not title:
            return {'ok': False, 'status': 'observation_missing', 'model_calls': 0,
                    'verified_listings': []}
        report = assess_page(url.group(1), title.group(1), text)
        report['observed_title'] = title.group(1)[:300]
        # Keep only the task-related query, never tracking parameters or tokens.
        parts = urlsplit(url.group(1))
        report['observed_path'] = parts.path
        report['observed_query'] = parse_qs(parts.query).get('q', [])[:2]
        return report
