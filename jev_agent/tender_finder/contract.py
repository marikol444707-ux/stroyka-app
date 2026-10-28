"""Explicit v2 validation only; does not replace or guess the deployed v1 bridge.

Date-only bounds use Europe/Moscow start/end of day. Exact amounts are Decimal;
canonical reports use decimal strings. Company ownership must come from the
caller's protected configuration/authentication, never from request JSON.
"""
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from zoneinfo import ZoneInfo

from .catalog import BY_ID, normalized_text, resolve_topic

REGION = 'Ставропольский край'
PROVIDERS = ('B2B-Center', 'Росэлторг', 'Фабрикант', 'ЭТП ГПБ', 'Сбер А',
             'ТЭК-Торг', 'Торги Федерации', 'Р-ТЕНДЕР')
REGIMES = ('44-ФЗ', '223-ФЗ', '615-ПП', 'commercial')
MAX_REQUEST_BYTES = 32768
MAX_PHRASES = 20
MAX_STRING = 80
MAX_RESULTS = 50
MAX_PRICE = Decimal('1000000000000')
MOSCOW = ZoneInfo('Europe/Moscow')
FIELDS = frozenset(('version', 'request_id', 'region', 'sources', 'commercial_sources',
                    'legal_regimes', 'topics', 'keywords', 'exclude_keywords', 'active_only',
                    'deadline_from', 'deadline_to', 'price_min_rub', 'price_max_rub', 'limit'))
COMPANY_FIELDS = frozenset(('companyId', 'company_id', 'targetCompanyId', 'ownerId', 'owner_id'))


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str


class InvalidRequest(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__('invalid_request')

    def as_dict(self):
        return {'status': 'rejected', 'reason': 'invalid_request',
                'errors': [vars(issue) for issue in self.issues]}


def fail(field, code, message):
    raise InvalidRequest([Issue(field, code, message)])


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(key, 'duplicate_field', 'Поле JSON повторяется.')
        result[key] = value
    return result


def parse_v2_request(raw):
    if isinstance(raw, str):
        try:
            raw = raw.encode('utf-8')
        except UnicodeError:
            fail('$', 'invalid_encoding', 'Требуется UTF-8.')
    if not isinstance(raw, bytes):
        fail('$', 'invalid_json', 'Требуется JSON.')
    if len(raw) > MAX_REQUEST_BYTES:
        fail('$', 'request_too_large', 'Превышен размер запроса 32 КиБ.')
    def constant(_):
        fail('$', 'nonfinite_number', 'NaN и бесконечность не допускаются.')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_float=Decimal, parse_constant=constant)
    except InvalidRequest:
        raise
    except (UnicodeError, ValueError, RecursionError):
        fail('$', 'invalid_json', 'Некорректный JSON UTF-8.')
    return validate_v2_request(value)


def _strings(payload, field, *, default=None, nonempty=False, limit=MAX_PHRASES):
    value = payload.get(field, default if default is not None else [])
    if type(value) is not list or len(value) > limit or (nonempty and not value):
        fail(field, 'invalid_list', 'Ожидается непустой ограниченный список.' if nonempty else 'Некорректный список.')
    result = {}
    for item in value:
        if not isinstance(item, str):
            fail(field, 'invalid_string', 'Элементы списка должны быть строками.')
        item = ' '.join(item.split())
        if not 2 <= len(item) <= MAX_STRING or any(ord(char) < 32 for char in item):
            fail(field, 'invalid_string_length', 'Длина фразы: от 2 до 80 символов.')
        result.setdefault(normalized_text(item), item)
    return tuple(result[key] for key in sorted(result))


def _deadline(payload, field, *, end=False):
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 40:
        fail(field, 'invalid_deadline', 'Требуется ISO-дата или время с часовым поясом.')
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            result = datetime.combine(date.fromisoformat(value), time.max if end else time.min, MOSCOW)
        else:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})', value):
                raise ValueError()
            if not value.endswith('Z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
                raise ValueError()
            result = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(MOSCOW)
        return result
    except (ValueError, OverflowError):
        fail(field, 'invalid_deadline', 'Некорректная ISO-дата; время должно содержать часовой пояс.')


def _price(payload, field):
    value = payload.get(field)
    if value is None:
        return None
    if type(value) not in (int, float, Decimal):
        fail(field, 'invalid_price', 'Цена должна быть числом в рублях.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > MAX_PRICE:
            raise InvalidOperation()
        rounded = amount.quantize(Decimal('0.01'))
        if rounded != amount:
            raise InvalidOperation()
        return rounded
    except (InvalidOperation, ValueError):
        fail(field, 'invalid_price', 'Допускается конечная неотрицательная цена до 1 трлн ₽ с точностью до копейки.')


@dataclass(frozen=True)
class SearchRequest:
    request_id: str
    sources: tuple[str, ...]
    commercial_sources: tuple[str, ...]
    legal_regimes: tuple[str, ...]
    topic_ids: tuple[str, ...]
    keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    active_only: bool
    deadline_from: datetime | None
    deadline_to: datetime | None
    price_min_rub: Decimal | None
    price_max_rub: Decimal | None
    limit: int

    def canonical_payload(self):
        return {'version': 2, 'request_id': self.request_id, 'region': REGION,
                'sources': list(self.sources), 'commercial_sources': list(self.commercial_sources),
                'legal_regimes': list(self.legal_regimes), 'topics': list(self.topic_ids),
                'keywords': list(self.keywords), 'exclude_keywords': list(self.exclude_keywords),
                'active_only': self.active_only,
                'deadline_from': self.deadline_from.isoformat() if self.deadline_from else None,
                'deadline_to': self.deadline_to.isoformat() if self.deadline_to else None,
                'price_min_rub': str(self.price_min_rub) if self.price_min_rub is not None else None,
                'price_max_rub': str(self.price_max_rub) if self.price_max_rub is not None else None,
                'limit': self.limit}

    def company_profile(self, trusted_company_id):
        """CLI input, not an authorization decision or proof of filter coverage."""
        if type(trusted_company_id) is not int or trusted_company_id <= 0:
            fail('company', 'trusted_company_required', 'Организация должна быть задана защищённым контекстом.')
        if 'commercial' not in self.sources:
            fail('sources', 'commercial_not_requested', 'Запрос не включает коммерческий поиск.')
        phrases = {normalized_text(BY_ID[topic].query): BY_ID[topic].query for topic in self.topic_ids}
        for keyword in self.keywords:
            phrases.setdefault(normalized_text(keyword), keyword)
        return {'companyId': trusted_company_id, 'region': REGION,
                'searchTerms': [phrases[key] for key in sorted(phrases)],
                'sourceProviders': list(self.commercial_sources)}

    def fingerprint(self, trusted_company_id):
        # Include tenant identity even though it is never accepted from request JSON.
        if type(trusted_company_id) is not int or trusted_company_id <= 0:
            fail('company', 'trusted_company_required', 'Организация должна быть задана защищённым контекстом.')
        canonical = self.canonical_payload()
        for field in ('keywords', 'exclude_keywords'):
            canonical[field] = [normalized_text(item) for item in canonical[field]]
        payload = {'companyId': trusted_company_id, 'request': canonical}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()


def validate_v2_request(payload):
    if type(payload) is not dict or any(not isinstance(key, str) for key in payload):
        fail('$', 'invalid_object', 'Ожидается объект JSON.')
    if len(payload) > 32:
        fail('$', 'too_many_fields', 'Слишком много полей запроса.')
    issues = [Issue(key, 'untrusted_company_field' if key in COMPANY_FIELDS else 'unknown_field',
                    'Организацию нельзя задавать в запросе.' if key in COMPANY_FIELDS else 'Неизвестное поле.')
              for key in sorted(payload.keys() - FIELDS)]
    if issues:
        raise InvalidRequest(issues)
    if type(payload.get('version')) is not int or payload['version'] != 2:
        fail('version', 'v2_required', 'Этот модуль обрабатывает только v2; действующий контракт v1 здесь не подменяется.')
    request_id = payload.get('request_id')
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', request_id):
        fail('request_id', 'invalid_request_id', 'ID: 1–64 латинских букв, цифр, дефисов или подчёркиваний.')
    if payload.get('region') != REGION:
        fail('region', 'unsupported_region', 'Пока поддерживается только Ставропольский край.')
    sources = _strings(payload, 'sources', nonempty=True, limit=2)
    if set(sources) - {'eis', 'commercial'}:
        fail('sources', 'unknown_source_group', 'Допустимы только eis и commercial.')
    selected = _strings(payload, 'commercial_sources', default=list(PROVIDERS) if 'commercial' in sources else [],
                        nonempty='commercial' in sources, limit=len(PROVIDERS))
    if set(selected) - set(PROVIDERS):
        fail('commercial_sources', 'unknown_provider', 'Неизвестная коммерческая площадка.')
    if selected and 'commercial' not in sources:
        fail('commercial_sources', 'source_group_mismatch', 'Площадки требуют группы commercial.')
    defaults = list(REGIMES[:-1]) if 'eis' in sources else []
    if 'commercial' in sources:
        defaults.append('commercial')
    regimes = _strings(payload, 'legal_regimes', default=defaults, nonempty=True, limit=4)
    if set(regimes) - set(REGIMES):
        fail('legal_regimes', 'unknown_legal_regime', 'Неизвестный правовой режим.')
    # A commercial platform may also carry regulated tenders. Source group is
    # not a legal regime; deployed adapter coverage must be reported separately.
    if ('commercial' in regimes and 'commercial' not in sources) or (
            'eis' in sources and not any(regime != 'commercial' for regime in regimes)):
        fail('legal_regimes', 'source_group_mismatch', 'Правовые режимы должны соответствовать выбранным группам источников.')
    topics = _strings(payload, 'topics', nonempty=True)
    topic_ids = set()
    for topic in topics:
        resolved = resolve_topic(topic)
        if resolved is None:
            fail('topics', 'unknown_topic', 'Неизвестное направление; произвольные фразы задаются в keywords.')
        topic_ids.add(resolved)
    keywords = _strings(payload, 'keywords')
    excluded = _strings(payload, 'exclude_keywords')
    phrases = {normalized_text(BY_ID[topic].query) for topic in topic_ids} | {normalized_text(item) for item in keywords}
    if len(phrases) > MAX_PHRASES:
        fail('keywords', 'search_plan_too_broad', 'Общее число фраз направлений и keywords не должно превышать 20.')
    active_only = payload.get('active_only', True)
    limit = payload.get('limit', MAX_RESULTS)
    if type(active_only) is not bool:
        fail('active_only', 'invalid_boolean', 'Требуется true или false.')
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        fail('limit', 'invalid_limit', 'Число карточек: от 1 до 50.')
    start = _deadline(payload, 'deadline_from')
    end = _deadline(payload, 'deadline_to', end=True)
    minimum = _price(payload, 'price_min_rub')
    maximum = _price(payload, 'price_max_rub')
    if start is not None and end is not None and start > end:
        fail('deadline_to', 'inverted_deadlines', 'Конец периода раньше начала.')
    if minimum is not None and maximum is not None and minimum > maximum:
        fail('price_max_rub', 'inverted_prices', 'Максимальная цена меньше минимальной.')
    return SearchRequest(request_id, tuple(sorted(sources)), tuple(sorted(selected)), tuple(sorted(regimes)),
                         tuple(sorted(topic_ids)), keywords, excluded, active_only, start, end, minimum, maximum, limit)
