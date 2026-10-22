"""Read-only adapter for the public EIS procurement RSS search."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import argparse
from html.parser import HTMLParser
import hashlib
import json
import re
import ssl
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

EIS_HOST = 'zakupki.gov.ru'
EIS_RSS = 'https://zakupki.gov.ru/epz/order/extendedsearch/rss.html'
GOSUSLUGI_ROOT = 'https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer'
# SHA-256 of the official Russian Trusted Root CA certificate, distributed by Gosuslugi.
ROOT_SHA256 = 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31'
LAWS = {
    '44-ФЗ': {'fz44': 'on'},
    '223-ФЗ': {'fz223': 'on'},
    '615-ПП': {'ppRf615': 'on'},
}
TERMS = ('капитальный ремонт Ставрополь', 'строительство Ставрополь',
         'ремонт Ставропольский край')
CONSTRUCTION = re.compile(r'строительн|капитальн\w*\s+ремонт|ямочн\w*\s+ремонт|ремонт\w*.{0,50}(?:здан|помещен|фасад|кровл|дорог|моста|сооружен)|'
                          r'реконструкц|благоустройств|отделочн\w*\s+работ|монтаж\w*.{0,40}(?:систем|сет|здан|помещен)|выполнени\w*\s+работ', re.I)
NON_BUILDING = re.compile(r'автотранспорт|автомобил|легков\w*\s+автомобил|ремонт\w*.{0,35}(?:лифтов|машин|оборудован|насос|техник)', re.I)
STAVROPOL_REGION = re.compile(r'Ставропольск\w*\s+кра|(?:г\.?\s*)?(?:Ставропол|Пятигорск|Кисловодск|Ессентук|Минеральные\s+Воды|Невинномысск|Шпаковск|Нефтекумск|Новоселицк|Новоалександровск)', re.I)
OTHER_REGION = re.compile(r'Чеченск\w*\s+Республик|Северн\w*\s+Осети|Республик\w*\s+Дагестан|Кабардино-Балкарск\w*\s+Республик|Карачаево-Черкесск\w*\s+Республик', re.I)


class _TextAndLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links = [], []
        self._link_depth = 0
        self._link = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('br', 'p', 'div', 'li'):
            self.text.append(' ')
        if tag.lower() == 'a':
            self._link = {'href': dict(attrs).get('href', ''), 'text': []}
            self._link_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._link_depth:
            link = self._link
            link['text'] = ' '.join(' '.join(link['text']).split())
            self.links.append(link)
            self._link, self._link_depth = None, 0

    def handle_data(self, data):
        self.text.append(data)
        if self._link is not None:
            self._link['text'].append(data)


def build_url(term, law):
    if law not in LAWS or not isinstance(term, str) or not 1 <= len(term) <= 100:
        raise ValueError('Unsupported EIS query')
    params = [(key, value) for key, value in LAWS[law].items()]
    params.extend((('af', 'on'), ('searchString', term), ('searchStringPlace', '1'),
                   ('recordsPerPage', '_10'), ('pageNumber', '1')))
    return EIS_RSS + '?' + urlencode(params)


def _ssl_context():
    """Trust only the pinned official root for the EIS request; retain hostname checks."""
    request = Request(GOSUSLUGI_ROOT, headers={'User-Agent': 'Mozilla/5.0 StroykaJev/1.0'})
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError('Official certificate download failed')
        cert = response.read(8192)
    pem = cert.decode('ascii') if cert.startswith(b'-----BEGIN CERTIFICATE-----') else ssl.DER_cert_to_PEM_cert(cert)
    der = ssl.PEM_cert_to_DER_cert(pem)
    if hashlib.sha256(der).hexdigest() != ROOT_SHA256:
        raise RuntimeError('Official root certificate fingerprint mismatch')
    return ssl.create_default_context(cadata=pem)


def _safe_notice_url(url):
    parsed = urlsplit(url or '')
    if (parsed.scheme != 'https' or parsed.netloc.lower() != EIS_HOST or parsed.fragment or
            parsed.path != '/epz/order/notice/ea20/view/common-info.html' or
            not re.fullmatch(r'\d{19}', dict(x.split('=', 1) for x in parsed.query.split('&') if '=' in x).get('regNumber', ''))):
        return ''
    return url


def _field(raw, label, next_labels):
    text = re.sub(r'<br\s*/?>', ' ', raw, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = ' '.join(text.split())
    ending = '|'.join(re.escape(x) for x in next_labels)
    match = re.search(re.escape(label) + r'\s*(.*?)\s*(?=' + ending + r'\s*:|$)', text, re.I)
    return match.group(1).strip(' :') if match else ''


def parse_rss(payload, law, query):
    if law not in LAWS:
        raise ValueError('Unknown procurement law')
    root = ET.fromstring(payload)
    rows = []
    for item in root.findall('.//item'):
        raw_description = item.findtext('description') or ''
        parsed = _TextAndLinks()
        parsed.feed(raw_description)
        text = ' '.join(''.join(parsed.text).split())
        link = _safe_notice_url(item.findtext('link'))
        # RSS description contains the EIS direct notice link as well as its summary.
        if not link:
            link = next((_safe_notice_url(a['href']) for a in parsed.links if _safe_notice_url(a['href'])), '')
        match = re.search(r'№\s*(\d{19})', item.findtext('title') or '')
        if not match and link:
            match = re.search(r'[?&]regNumber=(\d{19})', link)
        if not (link and match):
            continue
        status_match = re.search(r'Этап закупки:\s*(Подача заявок|Ожидание подачи заявок|Подведение итогов|Закупка завершена)', text, re.I)
        object_name = _field(raw_description, 'Наименование объекта закупки',
                             ('Размещение выполняется по', 'Наименование Заказчика', 'Начальная цена контракта'))
        location = _field(raw_description, 'Место выполнения работ',
                          ('Место поставки товара', 'Срок исполнения', 'Начальная цена контракта'))
        if not location:
            location = _field(raw_description, 'Адрес объекта закупки',
                              ('Срок исполнения', 'Начальная цена контракта', 'Наименование Заказчика'))
        price = _field(raw_description, 'Начальная цена контракта',
                       ('Валюта', 'Размещено', 'Обновлено'))
        author = _TextAndLinks()
        author.feed(item.findtext('author') or '')
        summary_title = next((a['text'] for a in parsed.links
                              if a['text'] and not re.match(r'№?\s*\d{10,}', a['text'])), '')
        rows.append({
            'source': 'ЕИС', 'id': match.group(1), 'url': link,
            'title': object_name or summary_title or (item.findtext('title') or '').strip(),
            'object_name': object_name, 'organizer': ' '.join(''.join(author.text).split()),
            'region': '', 'place': location, 'region_scope': 'not_filtered',
            'regime': law, 'status': ' '.join(status_match.group(1).split()) if status_match else '',
            'deadline': '', 'price': price, 'search_query': query, 'evidence': text[:2000],
            'published_at': (parsedate_to_datetime(item.findtext('pubDate')).astimezone(timezone.utc).isoformat()
                             if item.findtext('pubDate') else ''),
        })
    return rows


def fetch_search(term, law, context=None):
    url = build_url(term, law)
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; StroykaJev/1.0)',
                                    'Accept': 'application/rss+xml,application/xml,text/xml'})
    with urlopen(request, context=context or _ssl_context(), timeout=25) as response:
        if response.status != 200 or 'xml' not in response.headers.get('Content-Type', '').lower():
            raise RuntimeError('EIS did not return RSS XML')
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise RuntimeError('EIS RSS response exceeded size limit')
    return parse_rss(payload, law, term)


def search_eis(terms=TERMS, laws=tuple(LAWS)):
    rows, sources = [], []
    try:
        context = _ssl_context()
    except Exception as exc:
        return rows, [{'provider': 'ЕИС', 'query': term, 'law': law,
                       'ok': False, 'status': 'source_unavailable',
                       'error_type': type(exc).__name__, 'rows': 0}
                      for law in laws for term in terms]
    for law in laws:
        for term in terms:
            url = build_url(term, law)
            try:
                found = fetch_search(term, law, context)
                rows.extend(found)
                sources.append({'provider': 'ЕИС', 'query': term, 'law': law,
                                'ok': True, 'status': 'observed_first_page',
                                'rows': len(found), 'url': url})
            except Exception as exc:
                sources.append({'provider': 'ЕИС', 'query': term, 'law': law,
                                'ok': False, 'status': 'source_unavailable',
                                'error_type': type(exc).__name__, 'rows': 0})
    unique = {}
    for row in rows:
        key = (row['regime'], row['id'])
        if key not in unique:
            unique[key] = row
            row['search_queries'] = [row['search_query']]
        elif row['search_query'] not in unique[key]['search_queries']:
            unique[key]['search_queries'].append(row['search_query'])
    return list(unique.values()), sources


def government_review_rows(rows):
    """Keep only construction opportunities; all require human confirmation."""
    candidates = []
    for row in rows:
        title = row.get('title', '')
        if NON_BUILDING.search(title) or OTHER_REGION.search(title) or not CONSTRUCTION.search(title):
            continue
        in_region = bool(STAVROPOL_REGION.search(title))
        candidates.append(dict(
            row,
            provider='ЕИС · ' + str(row.get('regime') or ''),
            region='Ставропольский край' if in_region else '',
            region_scope='object_name_only' if in_region else 'unknown',
            work_types=['Строительство / капитальный ремонт'],
            description='\n'.join(value for value in (
                'Заказчик: ' + str(row.get('organizer') or '') if row.get('organizer') else '',
                'Правовой режим: ' + str(row.get('regime') or ''),
                'Статус в ЕИС: ' + str(row.get('status') or '') if row.get('status') else '',
            ) if value),
            decision='review',
            reasons=(['government_procurement_manual_verification', 'deadline_and_documents_need_check']
                     if in_region else ['work_location_unknown', 'deadline_and_documents_need_check']),
        ))
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Write JSON report to this path; default is stdout')
    args = parser.parse_args()
    rows, sources = search_eis()
    # EIS is a public procurement register. Its 44-FZ/223-FZ/615-PP records are
    # deliberately kept outside the commercial-opportunity import pipeline.
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'region': 'Ставропольский край · регион проверяется вручную',
        'scope': 'Первые 10 открытых результатов по 3 запросам и 3 правовым режимам. ЕИС не подтвердил региональный фильтр; адрес работ и актуальность сверяются в оригинале.',
        'sources': sources,
        'candidates': government_review_rows(rows),
        'screened_out_non_construction': sum(1 for row in rows if NON_BUILDING.search(row.get('title', '')) or not CONSTRUCTION.search(row.get('title', ''))),
        'screened_out_other_region': sum(1 for row in rows if OTHER_REGION.search(row.get('title', ''))),
        'ok': bool(sources) and all(source.get('ok') for source in sources),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
