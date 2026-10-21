"""Bounded public B2B-Center search. Unknown procedure regimes stay unconfirmed."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

HOST = 'www.b2b-center.ru'
BASE = 'https://' + HOST + '/app/next/market-search'
ROSELTORG_HOST = 'www.roseltorg.ru'
FABRIKANT_HOST = 'fabrikant.ru'
ETPGPB_HOST = 'etpgpb.ru'
SBER_HOST = 'www.sberbank-ast.ru'
SBER_PROCEDURE_HOST = 'utp.sberbank-ast.ru'
IMAGE = 'sha256:8c231608d909734fee19e3ce851ca1725fd6e4e84f20fb5f8a4288a06823ef0d'
MSK = timezone(timedelta(hours=3))
TERMS = ('Ставрополь', 'Ставропольский край', 'Невинномысск', 'Пятигорск', 'Кисловодск',
         'Ессентуки', 'Минеральные Воды', 'Михайловск', 'Будённовск', 'Георгиевск',
         'Железноводск', 'Лермонтов')
WORK = re.compile(r'строительн|строительств|отделоч|электромонтаж|фундамент|благоустрой|озелен|'
                  r'(?:капитальн\w*|текущ\w*)\s+ремонт|'
                  r'ремонт\w*\s+(?:помещен|здан|офис|кровл|фасад|магаз|объект)|'
                  r'монтаж\w*\s+.{0,35}(?:сет|систем|кабель|вентиляц)', re.I)
GOODS_ONLY = re.compile(r'\b(?:поставк\w*|приобретен\w*|закупк\w*)\b', re.I)
WORK_ACTION = re.compile(r'\b(?:выполнени\w*\s+работ|строительств\w*|(?:капитальн\w*|текущ\w*)\s+ремонт|ремонт\w*\s+(?:помещен|здан|офис|кровл|фасад|магаз|объект)|отделоч\w*\s+работ|монтаж\w*\s+(?:работ|сет|систем|кабель|вентиляц)|благоустройств\w*|озелен\w*)', re.I)
EQUIPMENT_REPAIR = re.compile(r'ремонт\w*\s+(?:оборудован|двигател|транспорт|станк|насос|датчик|преобразоват|тс\b|котельного\s+оборудован)', re.I)
REGION = re.compile(r'Ставропольск\w*\s+кра|Ставропол|Невинномысск|Пятигорск|Кисловодск|Ессентук|Минеральные\s+Воды|Михайловск|Буд[её]нновск', re.I)
EXCLUDED_LAW = re.compile(r'\b(?:44|223)\s*[-‑–]?\s*ФЗ\b|615\s*[-‑–]?\s*ПП', re.I)


def search_url(term):
    if not isinstance(term, str) or not 1 <= len(term) <= 64: raise ValueError('Invalid search term')
    # Parameters observed after submitting the public form, not protected filters.
    return BASE + '?' + urlencode(dict(q=term, company_type='2', include_firm_tree='false',
                                       sort='date_desc', trade='buy', show='actual'))


def sber_search_url(term, now=None):
    """Build the public Sber AST commercial-buyer search query."""
    if not isinstance(term, str) or not 1 <= len(term) <= 64:
        raise ValueError('Invalid search term')
    now = now or datetime.now(MSK)
    start = now.astimezone(MSK).date()
    end = start + timedelta(days=365)
    query = {
        'searchBarType': 'anyWord', 'pagenum': 0, 'mainInput': term,
        'sourceTerm': ['Торги коммерческих заказчиков'],
        'publicDate': {'startPublicDate': '', 'endPublicDate': ''},
        'requestEndDate': {'startRequestDate': start.strftime('%d.%m.%Y'),
                           'endRequestDate': end.strftime('%d.%m.%Y')},
    }
    return 'https://' + SBER_HOST + '/UnitedPurchaseList.html?' + urlencode(
        {'query': json.dumps(query, ensure_ascii=False, separators=(',', ':'))})


def sber_search_checks(observed, term, now=None, requested_url=None):
    now = now or datetime.now(MSK)
    parsed = urlsplit(observed.get('url', ''))
    requested = urlsplit(requested_url or observed.get('url', ''))
    params = parse_qs(requested.query)
    try:
        query = json.loads(params['query'][0])
    except (KeyError, IndexError, TypeError, ValueError):
        query = {}
    start = now.astimezone(MSK).date()
    end = start + timedelta(days=365)
    expected_range = '{} - {}'.format(start.strftime('%d.%m.%Y'), end.strftime('%d.%m.%Y'))
    page_state = observed.get('page_state', '')
    return {
        'official_search_page': parsed.scheme == 'https' and parsed.netloc == SBER_HOST and parsed.path == '/UnitedPurchaseList.html' and not parsed.fragment,
        'commercial_source_filter': query.get('sourceTerm') == ['Торги коммерческих заказчиков'] and 'Торги коммерческих заказчиков' in page_state,
        'query_filter': query.get('mainInput') == term and ('Строка поиска: ' + term) in page_state,
        'active_deadline_filter': query.get('requestEndDate') == {
            'startRequestDate': start.strftime('%d.%m.%Y'),
            'endRequestDate': end.strftime('%d.%m.%Y')} and expected_range in page_state,
        'page_zero': query.get('pagenum') == 0 and requested.scheme == 'https' and requested.netloc == SBER_HOST and requested.path == '/UnitedPurchaseList.html',
    }


def sber_row(card):
    """Normalize only visible cards in Sber's official commercial section."""
    if not isinstance(card, dict):
        raise ValueError('Invalid Sber procedure card')
    url = procedure_url({'source': 'Сбер А', 'url': card.get('url', '')})
    match = re.search(r'/([0-9]+)$', urlsplit(url).path)
    title = str(card.get('title') or '').strip()
    if not match or not title:
        raise ValueError('Incomplete Sber procedure card')
    place_match = REGION.search(title)
    return {
        'source': 'Сбер А', 'id': match.group(1), 'url': url,
        'title': title[:1500], 'organizer': str(card.get('organizer') or '')[:300],
        'procedure_type': str(card.get('procedure_type') or '')[:200],
        'region': place_match.group(0) if place_match else '',
        'place': title[:1500], 'region_scope': 'worksite',
        'regime': 'Коммерческая закупка', 'status': str(card.get('status') or '')[:200],
        'deadline': str(card.get('deadline') or ''),
        'price': str(card.get('price') or 'Цена не указана'),
    }


def tender_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != HOST or parsed.query or
        not re.fullmatch(r'/(?:app/market-next|market)/[a-zA-Z0-9_-]+/tender-[0-9]+/', parsed.path)):
        raise ValueError('Unexpected procedure URL')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def procedure_url(row):
    """Validate and canonicalize links from each explicitly supported source."""
    parsed = urlsplit(row.get('url', ''))
    if parsed.scheme != 'https' or parsed.query or parsed.fragment:
        raise ValueError('Unexpected procedure URL')
    provider = row.get('source')
    # Older in-process callers may supply a B2B URL without the display label;
    # infer only this one provider from its exact HTTPS host.
    if provider is None and parsed.netloc == HOST:
        provider = 'B2B-Center'
    if provider == 'B2B-Center':
        return tender_url(row['url'])
    if provider == 'Фабрикант' and parsed.netloc in ('www.fabrikant.ru', 'fabrikant.ru') and re.fullmatch(
            r'/v2/trades/procedure/view/[A-Za-z0-9_-]+', parsed.path):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    if provider == 'Росэлторг' and parsed.netloc == ROSELTORG_HOST and re.fullmatch(
            r'/procedure/[A-Za-z0-9_-]+/[0-9]+', parsed.path):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    if provider == 'ЭТП ГПБ' and parsed.netloc == ETPGPB_HOST and re.fullmatch(
            r'/procedures/[A-Za-z0-9_-]+/[A-Za-z0-9._-]+/?', parsed.path):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    if provider == 'Сбер А' and parsed.netloc == SBER_PROCEDURE_HOST and re.fullmatch(
            r'/VIP/NBT/PurchaseView/[0-9]+/[0-9]+/[0-9]+/[0-9]+', parsed.path):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    raise ValueError('Unexpected procedure URL')


def search_checks(observed, term):
    parsed = urlsplit(observed.get('url', ''))
    params = parse_qs(parsed.query)
    tabs = observed.get('selected', [])
    visible_state = observed.get('page_state', '')
    actual = next((re.search(r'^Актуально\s*•\s*([\d\s]+)$', x) for x in tabs if x.startswith('Актуально')), None)
    if actual is None:
        actual = re.search(r'Актуально\s*•\s*([\d\s]+)', visible_state)
    count = int(re.sub(r'\s', '', actual.group(1))) if actual else None
    return {
        'public_search_url': parsed.scheme == 'https' and parsed.netloc == HOST and parsed.path.rstrip('/') == '/app/next/market-search',
        'query_in_url': params.get('q') == [term],
        'buy_mode_in_url': params.get('trade') == ['buy'] and params.get('show') == ['actual'],
        'rendered_query': observed.get('query') == term,
        'procurement_tab': 'Объявления о закупках' in tabs or 'Объявления о закупках' in visible_state,
        'active_results_tab': count is not None,
        'rows_match_count': (bool(observed.get('rows')) if count else not observed.get('rows')) if count is not None else False,
    }


def verify_search(observed, term):
    return all(search_checks(observed, term).values())


def assess(row, now):
    result = dict(row, decision='review', reasons=[])
    try:
        result['url'] = procedure_url(row)
        if row.get('source') == 'B2B-Center' and not result['url'].endswith('/tender-' + str(row['id']) + '/'):
            raise ValueError('Procedure identity mismatch')
        if row.get('source') == 'Росэлторг' and urlsplit(result['url']).path.split('/')[2] != str(row['id']):
            raise ValueError('Procedure identity mismatch')
    except (KeyError, ValueError):
        return dict(result, decision='excluded', reasons=['invalid_source'])
    if not WORK.search(row.get('title', '')):
        return dict(result, decision='excluded', reasons=['not_construction_work'])
    if GOODS_ONLY.search(row.get('title', '')) and not WORK_ACTION.search(row.get('title', '')):
        return dict(result, decision='excluded', reasons=['goods_purchase_not_work'])
    if EQUIPMENT_REPAIR.search(row.get('title', '')):
        return dict(result, decision='excluded', reasons=['equipment_repair_not_building_work'])
    procedure_type = row.get('procedure_type', '')
    if row.get('source') == 'Сбер А':
        if re.search(r'продаж|реализац|аренд', procedure_type, re.I):
            return dict(result, decision='excluded', reasons=['sale_not_procurement'])
        if not re.search(r'закуп|поставк|подряд|запрос предложений', procedure_type, re.I):
            result['reasons'].append('procedure_type_unknown')
    place = '' if row.get('region_scope') == 'customer_region_filter' else row.get('place', row.get('region', ''))
    if not REGION.search(place):
        if REGION.search(row.get('title', '')):
            result['reasons'].append('place_conflict_needs_review')
        elif place:
            return dict(result, decision='excluded', reasons=['other_region'])
        else: result['reasons'].append('work_location_unknown')
    try:
        found = re.search(r'\b\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}\b', row.get('deadline', ''))
        deadline = datetime.strptime(found.group(), '%d.%m.%Y %H:%M').replace(tzinfo=MSK)
        if deadline <= now: return dict(result, decision='excluded', reasons=['deadline_expired'])
        result['deadline_msk'] = deadline.isoformat()
    except (AttributeError, ValueError): result['reasons'].append('deadline_unknown')
    regime = row.get('regime', '')
    if EXCLUDED_LAW.search(regime): return dict(result, decision='excluded', reasons=['regulated_procurement'])
    if not re.fullmatch(r'коммерческ(?:ая|ие)(?:\s+закупк[аи])?', regime.strip(), re.I):
        result['reasons'].append('procurement_regime_unknown')
    if not result['reasons']: result['decision'] = 'confirmed'
    return result


def build_report(rows, sources, now=None):
    now = now or datetime.now(timezone.utc)
    unique = {}
    for row in rows:
        key = str(row.get('source', '')) + ':' + str(row.get('id', ''))
        if key: unique.setdefault(key, row)
    assessed = [assess(row, now) for row in unique.values()]
    excluded = {}
    for row in assessed:
        if row['decision'] == 'excluded':
            reason = row['reasons'][0] if row['reasons'] else 'other'
            excluded[reason] = excluded.get(reason, 0) + 1
    return {'generated_at': now.isoformat(), 'region': 'Ставропольский край',
            'coverage': 'Первые страницы B2B-Center по 12 городам, Росэлторга, Фабриканта, публичный поиск ЭТП ГПБ и Сбер А по региону и сроку; охват неполный',
            'sources': sources, 'confirmed': [x for x in assessed if x['decision'] == 'confirmed'],
            'review': [x for x in assessed if x['decision'] == 'review'],
            'excluded': excluded,
            'ok': bool(sources) and all(x.get('ok') for x in sources), 'model_calls': 0}


class RoseltorgCards:
    """Read the public search_ajax fragments and retain only first-party cards."""
    def parse(self, body):
        import html as html_lib
        markers=list(re.finditer(r'<div\b[^>]*class="[^"]*\bsearch-results__item\b',body))
        rows=[]
        for index,marker in enumerate(markers):
            fragment=body[marker.start():markers[index+1].start() if index+1<len(markers) else len(body)]
            links=re.findall(r'<a\b[^>]*href="(/procedure/[A-Za-z0-9_-]+/[0-9]+)"[^>]*>(.*?)</a>',fragment,re.S|re.I)
            if not links: continue
            path,anchor=links[0]
            procedure_id=path.split('/')[2]
            text=' '.join(html_lib.unescape(re.sub(r'<[^>]*>',' ',fragment)).split())
            if 'Ставропольский край' not in text: continue
            # The selected public section combines commercial and 223-FZ lots.
            # Keep the regime unconfirmed until the original record distinguishes it.
            regime=''
            deadline_match=re.search(r'Окончание приема заявок\s*(\d{2}\.\d{2}\.\d{4})\s*в\s*(\d{2}:\d{2})',text)
            status_match=re.search(r'\b(Прием заявок|Ожидание приема заявок)\b',text,re.I)
            title=' '.join(html_lib.unescape(re.sub(r'<[^>]*>',' ',anchor)).split())
            rows.append({'source':'Росэлторг','id':procedure_id,'url':'https://'+ROSELTORG_HOST+path,
                         'title':title[:1500], 'region':'Ставропольский край',
                         'region_scope':'customer_region_filter', 'regime':regime,
                         'status':status_match.group(1) if status_match else '',
                         'deadline':deadline_match.group(1)+' '+deadline_match.group(2) if deadline_match else ''})
        return rows


def public_get(url):
    request=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; StroykaJev/1.0)',
                                 'Accept':'text/html,application/xhtml+xml'})
    with urlopen(request,timeout=15) as response:
        if response.status != 200 or 'text/html' not in response.headers.get('Content-Type',''):
            raise RuntimeError('Public source did not return HTML')
        return response.geturl(), response.read().decode('utf-8','replace')


def public_get_json(url):
    """Read JSON only from the requested first-party ETP GPB API host."""
    request = Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; StroykaJev/1.0)',
                                    'Accept':'application/json'})
    with urlopen(request, timeout=15) as response:
        landed = response.geturl()
        parsed = urlsplit(landed)
        if (response.status != 200 or parsed.scheme != 'https' or
                parsed.netloc != ETPGPB_HOST or not parsed.path.startswith('/api/v2/') or
                'application/json' not in response.headers.get('Content-Type','')):
            raise RuntimeError('Public source did not return first-party JSON')
        return landed, json.loads(response.read().decode('utf-8'))


def rosel_source():
    """Open commercial+223 section search, restricted to Stavropol and open stages."""
    base='https://'+ROSELTORG_HOST+'/procedures/search_ajax'
    parser=RoseltorgCards()
    terms=('Ставрополь','строительство','капитальный ремонт','ремонт','благоустройство','отделочные работы','монтаж')
    rows=[]; sources=[]
    for term in terms:
        params=[('sale','1'),('source[]','2'),('region[]','26'),('status[]','0'),('status[]','5'),('query_field',term)]
        url=base+'?'+urlencode(params)
        try:
            landed,body=public_get(url)
            found=parser.parse(body)
            landed_parts=urlsplit(landed); landed_params=parse_qs(landed_parts.query)
            valid=(landed_parts.netloc==ROSELTORG_HOST and landed_parts.path=='/procedures/search_ajax' and
                   landed_params.get('sale')==['1'] and landed_params.get('source[]')==['2'] and
                   landed_params.get('region[]')==['26'] and set(landed_params.get('status[]',[]))=={'0','5'} and
                   landed_params.get('query_field')==[term] and
                   ('search-results__item' in body or 'search-autocomplete__no-result' in body))
            sources.append({'provider':'Росэлторг','query':term,'ok':valid,
                            'status':'observed_first_page' if valid else 'unexpected_redirect',
                            'rows':len(found),'url':url})
            if valid: rows.extend(found)
        except Exception as exc:
            sources.append({'provider':'Росэлторг','query':term,'ok':False,
                            'status':'source_unavailable','error_type':type(exc).__name__,'rows':0})
            break
    return rows,sources


def fabrikant_source():
    """Public commercial section, filtered to active/awaiting lots and customer region."""
    params=[('section_ids[]','2'),('customer_region_ids[]','pKk-kBtsG0FOOt1jqZ-LRQ'),
            ('statuses[]','1'),('statuses[]','5')]
    url='https://www.fabrikant.ru/procedure/search/purchases?'+urlencode(params)
    try:
        landed,body=public_get(url)
        landed_parts=urlsplit(landed); landed_params=parse_qs(landed_parts.query)
        valid=(landed_parts.netloc in ('www.fabrikant.ru',FABRIKANT_HOST) and
               landed_parts.path=='/procedure/search/purchases' and
               landed_params.get('section_ids[]')==['2'] and
               landed_params.get('customer_region_ids[]')==['pKk-kBtsG0FOOt1jqZ-LRQ'] and
               set(landed_params.get('statuses[]',[]))=={'1','5'} and
               'Коммерческие закупки' in body and 'customer_region_ids' in body)
        normalized=body.replace('\\"','"')
        pattern=(r'"url":"https://(?:www\.)?fabrikant\.ru/v2/trades/procedure/view/([A-Za-z0-9_-]+)"'
                 r',"name":"(.*?)","lotId":\d+.*?'
                 r'"sectionEnum":"commercial","procedureNumber":(\d+)')
        rows=[]
        for match in re.finditer(pattern,normalized,re.S):
            slug,title,number=match.groups()
            title=title.replace('\\"','"').replace('\\\\','\\')
            rows.append({'source':'Фабрикант','id':number,'url':'https://'+FABRIKANT_HOST+
                         '/v2/trades/procedure/view/'+slug,'title':title,
                         'region':'','region_scope':'customer_region_filter',
                         'regime':'Коммерческая закупка'})
        source={'provider':'Фабрикант','query':'Ставропольский край · активные и ожидаемые',
                'ok':valid,'status':'observed_first_page' if valid else 'search_not_verified',
                'rows':len(rows),'url':url}
        return rows,[source]
    except Exception as exc:
        return [],[{'provider':'Фабрикант','query':'Ставропольский край · активные и ожидаемые',
                    'ok':False,'status':'source_unavailable','error_type':type(exc).__name__,'rows':0}]


def etpgpb_row(item):
    """Normalize one record from ETP GPB's public procedures API."""
    if not isinstance(item, dict) or not isinstance(item.get('attributes'), dict):
        raise ValueError('Invalid ETP GPB procedure record')
    attrs = item['attributes']
    path = attrs.get('rebranding_truncated_path') or attrs.get('truncated_path')
    if not isinstance(path, str) or not path.startswith('/procedures/'):
        raise ValueError('Missing ETP GPB public procedure path')
    public_url = 'https://' + ETPGPB_HOST + path
    procedure_url({'source': 'ЭТП ГПБ', 'url': public_url})
    deadline = attrs.get('end_registration')
    if deadline:
        parsed_deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
        if parsed_deadline.tzinfo is None:
            parsed_deadline = parsed_deadline.replace(tzinfo=MSK)
        deadline = parsed_deadline.astimezone(MSK).strftime('%d.%m.%Y %H:%M')
    category = str(attrs.get('section_category_name') or '').strip()
    # Only the unambiguously commercial section is confirmed. 223-FZ is
    # deliberately excluded by assess(); broad Торговый портал remains review.
    regime = {'Закупки.Бизнес': 'Коммерческая закупка',
              'Закупки.Бизнес223': '223-ФЗ',
              'Закупки.Гос44': '44-ФЗ'}.get(category, '')
    regions = attrs.get('lot_regions') or []
    if not isinstance(regions, list):
        regions = [str(regions)]
    return {
        'source': 'ЭТП ГПБ', 'id': str(item.get('id') or attrs.get('registry_number') or ''),
        'url': public_url,
        'title': str(attrs.get('title') or ''),
        'organizer': str(attrs.get('company_name') or ''),
        'region': ', '.join(str(region) for region in regions),
        'place': ', '.join(str(region) for region in regions),
        'region_scope': 'worksite', 'regime': regime,
        'section': category, 'status': str(attrs.get('stage') or ''),
        'deadline': deadline or '',
        'price': str(attrs.get('amount') or 'Цена не указана'),
    }


def etpgpb_source(max_pages=5):
    """Read active public ETP GPB procedures for the Stavropol region.

    The endpoint and parameter format are the same as those used by the
    official page's procedures store (https://etpgpb.ru/procedures/).
    """
    api = 'https://' + ETPGPB_HOST + '/api/v2/'
    try:
        landed, regions_payload = public_get_json(api + 'regions/')
        parsed = urlsplit(landed)
        if parsed.scheme != 'https' or parsed.netloc != ETPGPB_HOST or parsed.path != '/api/v2/regions/':
            raise RuntimeError('Unexpected ETP GPB region endpoint')
        region_items = regions_payload.get('data') if isinstance(regions_payload, dict) else None
        if not isinstance(region_items, list):
            raise RuntimeError('Invalid ETP GPB region response')
        region_ids = [str(item.get('id')) for item in region_items
                      if isinstance(item, dict) and
                      (item.get('attributes') or {}).get('name') == 'Ставропольский край']
        if len(region_ids) != 1:
            raise RuntimeError('Stavropol region identifier is missing or ambiguous')

        rows = []
        api_params = []
        for page in range(1, max_pages + 1):
            params = [('page', str(page)), ('per', '100'),
                      ('procedure[stage][0]', 'accepting'),
                      ('procedure[regions][0]', region_ids[0])]
            url = api + 'procedures/?' + urlencode(params)
            landed, payload = public_get_json(url)
            parsed = urlsplit(landed)
            landed_params = parse_qs(parsed.query)
            valid_endpoint = (parsed.scheme == 'https' and parsed.netloc == ETPGPB_HOST and
                              parsed.path == '/api/v2/procedures/' and
                              landed_params.get('procedure[stage][0]') == ['accepting'] and
                              landed_params.get('procedure[regions][0]') == [region_ids[0]] and
                              landed_params.get('page') == [str(page)])
            if not valid_endpoint:
                raise RuntimeError('ETP GPB active region filter was not preserved')
            data = payload.get('data') if isinstance(payload, dict) else None
            meta = payload.get('meta') if isinstance(payload, dict) else None
            if not isinstance(data, list) or not isinstance(meta, dict):
                raise RuntimeError('Invalid ETP GPB procedures response')
            rows.extend(etpgpb_row(item) for item in data)
            api_params.append(url)
            total_pages = int(meta.get('total_pages') or 0)
            total_count = int(meta.get('total_count') or 0)
            if not data or page >= total_pages:
                break
        else:
            total_pages = int(meta.get('total_pages') or max_pages)
            total_count = int(meta.get('total_count') or 0)

        source = {'provider': 'ЭТП ГПБ', 'query': 'Ставропольский край · активные процедуры',
                  'ok': True, 'status': 'observed_first_pages' if rows else 'no_active_results',
                  'rows': len(rows), 'total_count': total_count,
                  'truncated': total_pages > max_pages, 'url': api_params[0] if api_params else api + 'procedures/'}
        return rows, [source]
    except Exception as exc:
        return [], [{'provider': 'ЭТП ГПБ', 'query': 'Ставропольский край · активные процедуры',
                     'ok': False, 'status': 'source_unavailable',
                     'error_type': type(exc).__name__, 'rows': 0}]


OBSERVE = r'''(()=>{const main=document.querySelector('main');const tabs=[...new Set([...document.querySelectorAll('[role="tab"],.cds-tab-v2')])];return {
url:location.href,title:document.title,query:main?.querySelector('input[name="q"]')?.value,
page_state:main?.innerText.slice(0,700)??document.body?.innerText.slice(0,700)??'',
all_tabs:tabs.slice(0,8).map(e=>e.innerText.trim()),
selected:tabs.filter(e=>e.getAttribute('aria-selected')==='true'||e.classList.contains('cds-tab-v2--selected')).map(e=>e.innerText.trim()),
highlights:[...main?.querySelectorAll('mark')??[]].map(e=>e.innerText),
rows:[...main?.querySelectorAll('.panel-procedure__card')??[]].slice(0,20).map(e=>({
id:e.querySelector('.panel-procedure__number-link')?.innerText.replace(/\D/g,''),
url:e.querySelector('.panel-procedure__number-link')?.href,
title:e.querySelector('.panel-procedure__dscr-main')?.innerText.slice(0,1500),
organizer:e.querySelector('.panel-procedure__dscr-branch')?.innerText.slice(0,300),
deadline:e.querySelector('.panel-procedure__dscr-date')?.innerText.slice(0,150),
price:e.querySelector('.panel-procedure__details-item-sum')?.innerText.slice(0,300),
region:e.querySelector('.panel-procedure__details-item-region')?.innerText.slice(0,300)})).filter(e=>e.id&&e.title)};})()'''


SBER_OBSERVE = r'''(()=>({url:location.href,title:document.title,
query:document.querySelector('input[name="mainInput"]')?.value||'',
page_state:document.body?.innerText.slice(0,1800)||'',
rows:[...document.querySelectorAll('.purchase-card')].slice(0,20).map(e=>({
url:e.querySelector('.purchase-card__purchcode')?.href||'',
id:e.querySelector('.purchase-card__purchcode')?.innerText||'',
title:e.querySelector('.purchase-object__content')?.innerText||'',
organizer:e.querySelector('.purchase-organizer__content')?.innerText||'',
procedure_type:e.querySelector('.purchase-card__type__purchaseType')?.innerText||'',
source:e.querySelector('.purchase-card__type__purchaseSource .accent-link__title')?.innerText||'',
status:e.querySelector('.purchase-card__stage')?.innerText||'',
deadline:e.getAttribute('request-date')||'',price:e.querySelector('.amount-item__value')?.innerText||''
})).filter(e=>e.url&&e.title)}))()'''


async def sber_source(call, now=None):
    """Read a few live, public Sber commercial searches in the browser."""
    now = now or datetime.now(MSK)
    terms = ('Ставрополь', 'капитальный ремонт', 'строительство')
    rows, sources = [], []
    for term in terms:
        url = sber_search_url(term, now)
        try:
            await call('Page.navigate', {'url': url})
            observed, previous, stable = {}, None, 0
            end = time.monotonic() + 8
            while time.monotonic() < end:
                await asyncio.sleep(.5)
                response = await call('Runtime.evaluate', {'expression': SBER_OBSERVE, 'returnByValue': True})
                if 'exceptionDetails' in response:
                    break
                observed = response.get('result', {}).get('value') or {}
                checks = sber_search_checks(observed, term, now, url)
                signature = json.dumps(observed, sort_keys=True)
                stable = stable + 1 if all(checks.values()) and signature == previous else 0
                previous = signature
                if stable >= 1:
                    break
            verified = stable >= 1
            found = []
            if verified:
                for card in observed.get('rows', []):
                    if card.get('source', '').strip() != 'Торги коммерческих заказчиков':
                        continue
                    try:
                        found.append(sber_row(card))
                    except (KeyError, ValueError):
                        continue
                rows.extend(found)
            sources.append({'provider': 'Сбер А', 'query': term, 'ok': verified,
                            'status': ('observed_first_page' if found else 'no_active_results') if verified else 'search_not_verified',
                            'rows': len(found), 'url': observed.get('url', url),
                            **({'failed_checks': [key for key, passed in checks.items() if not passed]} if not verified else {})})
            if not verified:
                break
        except Exception as exc:
            sources.append({'provider': 'Сбер А', 'query': term, 'ok': False,
                            'status': 'source_unavailable', 'error_type': type(exc).__name__, 'rows': 0})
            break
    return rows, sources


async def worker():
    import os
    from urllib.request import urlopen
    import websockets
    scratch = tempfile.mkdtemp(prefix='commercial-')
    chrome = subprocess.Popen(['/usr/bin/google-chrome', '--headless=new', '--no-sandbox',
        '--disable-dev-shm-usage', '--remote-debugging-port=9229', '--user-data-dir='+scratch+'/chrome', 'about:blank'],
        env={'HOME': scratch, 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = []
        for _ in range(30):
            try:
                with urlopen('http://127.0.0.1:9229/json/list', timeout=1) as response:
                    targets = [x for x in json.load(response) if x.get('type') == 'page' and
                               not str(x.get('url', '')).startswith('chrome-extension://') and
                               x.get('webSocketDebuggerUrl', '').startswith('ws://127.0.0.1:9229/devtools/page/')]
                if targets: break
            except OSError: pass
            await asyncio.sleep(.2)
        if not targets: raise RuntimeError('Browser not ready')
        target = next((x for x in targets if x.get('url') == 'about:blank'), targets[0])
        endpoint = target['webSocketDebuggerUrl']
        if not endpoint.startswith('ws://127.0.0.1:9229/devtools/page/'): raise ValueError('Unexpected browser endpoint')
        rows, sources = [], []
        async with websockets.connect(endpoint, max_size=2*1024*1024) as socket:
            sequence = 0
            async def call(method, params):
                nonlocal sequence
                sequence += 1
                current = sequence
                await socket.send(json.dumps(dict(id=current, method=method, params=params)))
                while True:
                    reply = json.loads(await asyncio.wait_for(socket.recv(), 8))
                    if reply.get('id') == current:
                        if 'error' in reply: raise RuntimeError('Browser command failed')
                        return reply.get('result', {})
            for term in TERMS:
                await call('Page.navigate', {'url': search_url(term)})
                observed, previous, stable = {}, None, 0
                end = time.monotonic() + 12
                while time.monotonic() < end:
                    await asyncio.sleep(.6)
                    response = await call('Runtime.evaluate', {'expression': OBSERVE, 'returnByValue': True})
                    if 'exceptionDetails' in response:
                        observed = {'url': search_url(term), 'query': None, 'selected': [],
                                    'highlights': [], 'rows': [], 'evaluation_failed': True}
                        break
                    observed = response.get('result', {}).get('value') or {}
                    ready = verify_search(observed, term)
                    signature = json.dumps(observed, sort_keys=True)
                    stable = stable + 1 if ready and signature == previous else 0
                    previous = signature
                    if stable >= 2: break
                verified = stable >= 2
                source = {'provider':'B2B-Center','query': term, 'ok': verified, 'url': observed.get('url', search_url(term)),
                          'status': 'observed_first_page' if verified else 'search_not_verified',
                          'rows': len(observed.get('rows', [])) if verified else 0}
                if not verified:
                    checks = search_checks(observed, term)
                    source.update({'observed_query': observed.get('query'),
                                   'page_title': observed.get('title', '')[:160],
                                   'page_state': observed.get('page_state', ''),
                                   'visible_tabs': observed.get('all_tabs', []),
                                   'active_tabs': observed.get('selected', [])[:3],
                                   'failed_checks': [name for name, passed in checks.items() if not passed],
                                   'evaluation_failed': observed.get('evaluation_failed', False)})
                sources.append(source)
                if not verified:
                    break
                if verified:
                    for row in observed.get('rows', []):
                        try: row['url'] = tender_url(row['url'])
                        except (KeyError, ValueError): continue
                        row['source']='B2B-Center'
                        rows.append(row)
            sber_rows, sber_sources = await sber_source(call)
            rows.extend(sber_rows)
            sources.extend(sber_sources)
        rosel_rows,rosel_sources=rosel_source()
        fabrikant_rows,fabrikant_sources=fabrikant_source()
        gpb_rows, gpb_sources = etpgpb_source()
        rows.extend(rosel_rows);rows.extend(fabrikant_rows);rows.extend(gpb_rows)
        sources.extend(rosel_sources);sources.extend(fabrikant_sources);sources.extend(gpb_sources)
        return build_report(rows, sources)
    finally:
        chrome.terminate()
        try: chrome.wait(timeout=5)
        except subprocess.TimeoutExpired: chrome.kill(); chrome.wait(timeout=5)


def probe():
    name = 'stroyka-commercial-' + uuid4().hex
    command = ['docker', 'run', '--rm', '--name', name, '--user', '10001:10001', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--memory', '1g', '--pids-limit', '256', '--read-only',
               '--tmpfs', '/tmp:rw,nosuid,nodev,size=384m', '--network', 'bridge',
               '--mount', 'type=bind,src='+str(Path(__file__).resolve())+',dst=/commercial.py,readonly',
               '--entrypoint', 'python3', IMAGE, '/commercial.py', '--worker']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or (result.returncode and data.get('ok')):
            raise ValueError('Invalid runner response')
        return data
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)


def render(report):
    esc = lambda value: html.escape(str(value), quote=True)
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Строительные закупки — коммерческий поиск</title><style>body{font:16px system-ui;max-width:850px;margin:24px auto;padding:0 16px;background:#f4f6fa;color:#253047}article{background:white;padding:18px;margin:12px 0;border-radius:12px}p,a{overflow-wrap:anywhere}</style>',
             '<h1>Коммерческие закупки: поиск кандидатов</h1><p>'+esc(report['coverage'])+'</p>',
             '<p>Непроверенный правовой режим не означает коммерческую закупку. Место и условия требуют сверки в оригинале.</p>']
    for key, label in (('confirmed', 'Подтверждённые по полям источника'), ('review', 'Нужно проверить')):
        parts.append('<h2>{}: {}</h2>'.format(label, len(report[key])))
        for row in report[key]:
            parts.append('<article><h3>'+esc(row.get('title', ''))+'</h3>')
            parts.append('<p><b>Площадка:</b> '+esc(row.get('source','Не указана'))+'</p>')
            for field, title in (('organizer','Заказчик'),('region','Регион в выдаче'),('deadline','Подача до (МСК)'),('price','Цена')):
                parts.append('<p><b>{}:</b> {}</p>'.format(title, esc(row.get(field) or 'Не указано')))
            if row.get('region_scope') == 'customer_region_filter':
                parts.append('<p>Регион задан по заказчику; место выполнения работ нужно сверить в оригинале.</p>')
            parts.append('<p>Причины проверки: '+esc(', '.join(row['reasons']))+'</p>')
            parts.append('<a rel="noreferrer" href="'+esc(procedure_url(row))+'">Открыть оригинал</a></article>')
    for source in report['sources']:
        parts.append('<p>{}: {} · строк {}</p>'.format(esc(source['query']),esc(source['status']), source['rows']))
    return ''.join(parts)+'</html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--output', help='Private report directory outside repository')
    args = parser.parse_args()
    report = asyncio.run(worker()) if args.worker else probe()
    if args.output:
        try: from .jev_telegram import private_directory, write_private
        except ImportError: from jev_telegram import private_directory, write_private
        folder = private_directory(args.output)
        write_private(folder/'report.json', json.dumps(report, ensure_ascii=False, indent=2))
        write_private(folder/'report.html', render(report))
    return report


if __name__ == '__main__':
    try: result = main()
    except Exception as exc: result = {'ok': False, 'status': 'commercial_search_failed', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get('ok') else 1)
