"""Conservative B2B-Center first-page/primary-card reader, not live-accepted.

Search URL/checks/notice identities reuse the existing reviewed implementation.
Primary fields use explicit text labels; unsupported markup stays unconfirmed.
The public browser transport is operator-bound. No login, downloads, model,
paid calls, source instructions, region inferred from organizer, or direct-role
inference. Primary parser still needs comparison against real captured pages.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
import time
from urllib.parse import urlsplit

from jev_agent.server_runtime.scripts.jev_commercial_search import search_url, search_checks, tender_url
from .model import Candidate, Document, Fact, aware, public_url
from .runner import SourceResult

HOST='www.b2b-center.ru'
LABELS={
    'Наименование закупки':'title', 'Название закупки':'title',
    'Организатор':'organizer', 'Организатор закупки':'organizer',
    'Сторона договора (заказчик)':'counterparty', 'Будущий контрагент':'counterparty',
    'Место выполнения работ':'work_address', 'Адрес выполнения работ':'work_address',
    'Адрес объекта':'work_address', 'Регион выполнения работ':'work_region',
    'Предмет закупки':'work_scope', 'Состав работ':'work_scope', 'Объем работ':'work_volume',
    'Объём работ':'work_volume', 'Начальная цена':'price', 'Бюджет':'price',
    'Текущий этап':'stage', 'Статус':'stage', 'Дата окончания подачи заявок':'deadline',
    'Дата окончания приема предложений':'deadline', 'Условия оплаты':'payment_period',
    'Срок выполнения работ':'construction_period', 'Обеспечение заявки':'security',
    'Банковская гарантия':'guarantee', 'Удержания':'retention',
    'Материалы заказчика':'customer_materials', 'Строительная СРО':'construction_sro',
    'Проектная СРО':'design_sro', 'Лицензия МЧС':'fire_license', 'Требования к опыту':'experience',
    'Осмотр объекта':'site_visit', 'Аккредитация':'accreditation', 'Способ подачи':'submission',
    'Правовой режим':'regime',
}
STAGES={'прием предложений':'accepting','приём предложений':'accepting',
        'прием заявок':'accepting','приём заявок':'accepting','квалификационный отбор':'qualification',
        'предварительный квалификационный отбор':'qualification','постоянный набор поставщиков':'standing',
        'приостановлено':'suspended','отменено':'cancelled','завершено':'closed','архив':'archive'}
LAWS={'коммерческая закупка':'commercial','44-фз':'44-ФЗ','223-фз':'223-ФЗ','615-пп':'615-ПП'}
LIMITS=('first_pages_only','primary_parser_not_live_verified','documents_not_read')


@dataclass(frozen=True)
class Observation:
    url: str
    status: str  # ok / captcha / login_required / unavailable
    checked_at: datetime
    text: str = ''
    search_state: dict | None = None


def fields(text):
    """Only explicit labeled lines. No fuzzy label/entity/property inference."""
    lines=text.splitlines(keepends=True)
    output=[]
    for index,line in enumerate(lines):
        content=line.strip()
        for label,name in LABELS.items():
            if content==label or content==label+':' or content.startswith(label+':'):
                value=content[len(label):].lstrip(':').strip()
                quote=line
                if not value and index+1<len(lines):
                    next_line=lines[index+1]
                    possible=next_line.strip()
                    if not possible or any(possible==label or possible.startswith(label+':') for label in LABELS):continue
                    value=possible;quote+=next_line
                if value and len(value)<=4000:
                    output.append((name,value,quote.rstrip('\r\n'),f'Строка {index+1}: {label}'))
                break
    return output


def _deadline(value):
    # No implicit MSK: an explicit zone in the source is mandatory.
    match=re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})\s*'
                       r'(?:\((МСК|MSK|UTC[+-]\d{2}:\d{2})\)|(МСК|MSK|UTC[+-]\d{2}:\d{2}))',value)
    if not match:return value
    day,month,year,hour,minute=map(int,match.groups()[:5])
    zone=match[6] or match[7]
    try:
        if zone in ('МСК','MSK'):offset=timedelta(hours=3)
        else:
            hours,minutes=map(int,zone[4:].split(':'))
            if hours>23 or minutes>59:return value
            offset=timedelta(hours=hours,minutes=minutes)*(1 if zone[3]=='+' else -1)
        return datetime(year,month,day,hour,minute,tzinfo=timezone(offset)).isoformat()
    except ValueError:return value


def parse_card(document):
    url=tender_url(document.url)
    number=re.search(r'/tender-([0-9]+)/$',url)[1]
    if not re.search(r'(?:Тендер|Закупка|Процедура|Запрос предложений|Запрос цен|Конкурс|Аукцион)\s*(?:№|номер)\s*'+re.escape(number)+r'(?![0-9])',
                     document.text,re.I):
        raise ValueError('independent_b2b_notice_number_required')
    facts={}
    def add(name,value,quote,locator):
        facts.setdefault(name,[]).append(Fact(value,document.id,quote,locator))
    for name,value,quote,locator in fields(document.text):
        folded=value.casefold().strip().rstrip('.')
        if folded in ('не указано','нет данных','не определено','требует уточнения'):
            facts.setdefault(name,[]).append(Fact(missing='Требует уточнения' if folded=='требует уточнения' else 'Не указано'))
        elif name=='stage':
            if folded in STAGES:add(name,STAGES[folded],quote,locator)
        elif name=='regime':
            if folded in LAWS:add(name,LAWS[folded],quote,locator)
        elif name=='deadline':add(name,_deadline(value),quote,locator)
        elif name=='price':
            amount=re.fullmatch(r'((?:[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+)(?:[.,][0-9]{1,2})?)\s*'
                                r'(₽|руб\.?|RUB|USD|EUR|€|\$)?\s*'
                                r'((?:с НДС|без НДС|в т\.ч\. НДС|НДС).*)?',value,re.I)
            if amount:
                text=re.sub(r'[ \u00a0\u202f]','',amount[1]).replace(',','.')
                if Decimal(text)<=Decimal('1e12'):
                    add('price',text,quote,locator)
                    if amount[2]:
                        currency={'€':'EUR','$':'USD','₽':'RUB','руб':'RUB','руб.':'RUB'}.get(amount[2].lower(),amount[2].upper())
                        add('currency',currency,quote,locator)
                    if amount[3]:add('vat',amount[3],quote,locator)
        elif name in ('construction_sro','design_sro','fire_license'):
            if folded in ('требуется','не требуется'):add(name,'required' if folded=='требуется' else 'not_required',quote,locator)
        elif name=='customer_materials':
            if folded in ('да','нет'):add(name,'yes' if folded=='да' else 'no',quote,locator)
        elif name=='work_region':
            matches=[region for region in ('Ставропольский край','Краснодарский край') if region.casefold() in folded]
            for region in matches or [value]:add(name,region,quote,locator)
        else:
            add(name,value,quote,locator)
            if name=='payment_period':
                if re.match(r'^постоплата(?:\s|$)',folded):add('payment','postpayment',quote,locator)
                elif re.match(r'^аванс\s+(?:[1-9][0-9]?|100)(?:[.,][0-9]{1,2})?\s*%',folded):
                    add('payment','advance',quote,locator);add('advance_conditions',value,quote,locator)
            elif name=='work_address':
                for region in ('Ставропольский край','Краснодарский край'):
                    if region.casefold() in folded:add('work_region',region,quote,locator)
            elif name=='work_scope':
                if re.match(r'^(?:выполнение работ (?:по )?)?капитальн\w* ремонт',folded):
                    add('kind','capital_repair',quote,locator)
                elif re.match(r'^(?:выполнение работ (?:по )?)?текущ\w* ремонт',folded):
                    add('kind','current_repair',quote,locator)
    # No role/authority inference from Organizer, Customer, brand or search tab.
    if any(len(values)>8 for values in facts.values()):raise ValueError('b2b_field_evidence_limit')
    return Candidate('b2b',number,(document,),{key:tuple(value) for key,value in facts.items()})


class B2BReader:
    def __init__(self,*,read,clock,monotonic=time.monotonic):
        if not all(callable(value) for value in (read,clock,monotonic)):raise ValueError('protected_b2b_reader_required')
        self.read,self.clock,self.monotonic=read,clock,monotonic

    def _capture(self,url,started,identifier):
        # Only generated public listing URLs or the previously reviewed notice
        # path family can reach the bound transport, never login/document URLs.
        if not public_url(url):raise ValueError('bounded_public_b2b_url_required')
        parsed=urlsplit(url)
        if parsed.path!='/app/next/market-search':tender_url(url)
        elif parsed.scheme!='https' or parsed.netloc!=HOST:raise ValueError('b2b_host_required')
        observed=self.read(url)
        if type(observed) is not Observation or observed.url!=url or not aware(observed.checked_at):
            raise ValueError('exact_b2b_observation_required')
        if not started<=observed.checked_at<=self.clock():raise ValueError('fresh_b2b_observation_required')
        if observed.status in ('captcha','login_required','unavailable'):return None,observed
        if observed.status!='ok':raise ValueError('public_b2b_capture_required')
        name='Выдача B2B-Center' if parsed.path=='/app/next/market-search' else 'Карточка B2B-Center'
        doc=Document(identifier,'b2b',url,name,'card',observed.checked_at,observed.text)
        return doc,observed

    def __call__(self,profile,started):
        profile.validate()
        terms=tuple(dict.fromkeys((*profile.queries,*profile.regions)))
        if len(terms)>20:raise ValueError('bounded_b2b_search_plan_required')
        listings,candidates,captures,seen=[],[],[],set();calls=0;partial=False
        deadline=self.monotonic()+180
        def exhausted():return calls>=40 or self.monotonic()>=deadline
        def finish(status,limitations=LIMITS):
            return SourceResult(status,tuple(candidates),tuple(listings),limitations,tuple(captures))
        for index,term in enumerate(terms):
            if exhausted():return finish('partial',(*LIMITS,'read_budget_exhausted'))
            url=search_url(term);calls+=1
            try:listing,observed=self._capture(url,started,f'b2b-listing-{index}')
            except Exception:
                return finish('error',(*LIMITS,'some_primary_cards_not_verified'))
            if listing is None:return finish(observed.status)
            state=observed.search_state
            if (type(state) is not dict or state.get('url')!=url or type(state.get('rows')) is not list
                    or len(state['rows'])>50 or not all(search_checks(state,term).values())):
                partial=True;continue
            listings.append(listing)
            for row in state['rows']:
                try:card_url=tender_url(row['url'])
                except (KeyError,ValueError,TypeError):partial=True;continue
                if card_url in seen:continue
                if exhausted():return finish('partial',(*LIMITS,'read_budget_exhausted'))
                seen.add(card_url);calls+=1
                try:card,page=self._capture(card_url,started,'b2b-card-'+str(len(seen)))
                except Exception:
                    return finish('error',(*LIMITS,'some_primary_cards_not_verified'))
                if card is None:return finish(page.status)
                captures.append(card)
                try:candidates.append(parse_card(card))
                except ValueError:partial=True
        limitations=(*LIMITS,'some_primary_cards_not_verified') if partial else LIMITS
        return finish('partial',limitations)
