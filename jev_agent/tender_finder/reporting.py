"""Evidence policy for normalized adapter output; no fetching, LLM, or side effects.

These DTOs are not a parser for arbitrary page JSON. The future bridge must bind
them to fetched source evidence and authenticated context. Unknown facts remain
review items. A source group is never used to infer a procedure's legal regime.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal
from itertools import islice
import re
from urllib.parse import urlsplit

from .catalog import BY_ID, normalized_text
from .contract import REGION, REGIMES, SearchRequest

HOSTS = {'B2B-Center': ('www.b2b-center.ru',), 'Росэлторг': ('www.roseltorg.ru',),
         'Фабрикант': ('fabrikant.ru', 'www.fabrikant.ru'), 'ЭТП ГПБ': ('etpgpb.ru',),
         'Сбер А': ('www.sberbank-ast.ru', 'utp.sberbank-ast.ru'),
         'ТЭК-Торг': ('www.tektorg.ru',), 'Торги Федерации': ('lk.fedtorgi.ru', 'etpp.ru'),
         'Р-ТЕНДЕР': ('etp.r-tender.ru',),
         **{'eis:' + regime: ('zakupki.gov.ru',) for regime in ('44-ФЗ', '223-ФЗ', '615-ПП')}}
STATUSES = frozenset(('not_tested', 'ok_with_results', 'ok_empty', 'partial', 'unavailable',
                      'blocked_by_login_or_captcha', 'error'))
FILTERS = frozenset(('region', 'topics', 'keywords', 'exclude_keywords', 'active_only',
                     'deadline_from', 'deadline_to', 'price_min_rub', 'price_max_rub', 'legal_regimes'))
ERROR_CODES = frozenset(('timeout', 'login_required', 'captcha', 'http_error', 'invalid_response',
                         'unsupported_regime', 'coverage_unverified', 'adapter_failed', 'not_tested'))


def aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def official_url(source, value):
    if not isinstance(source, str) or source not in HOSTS or not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return False
    if any(ord(char) < 33 for char in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and url.hostname in HOSTS[source] and url.port in (None, 443)
                and url.username is None and url.password is None and not url.fragment)
    except ValueError:
        return False


@dataclass(frozen=True)
class SourceOutcome:
    source: str
    status: str
    checked_at: datetime | None = None
    url: str | None = None
    queries_checked: int = 0
    pages_checked: int = 0
    matched_count: int = 0
    applied_filters: tuple[str, ...] = ()
    error_code: str | None = None

    def __post_init__(self):
        if not isinstance(self.source, str) or not isinstance(self.status, str) or self.source not in HOSTS or self.status not in STATUSES:
            raise ValueError('invalid_source_status')
        if any(type(value) is not int or not 0 <= value <= 10000 for value in (
                self.queries_checked, self.pages_checked, self.matched_count)):
            raise ValueError('invalid_source_counts')
        if type(self.applied_filters) is not tuple or any(not isinstance(item, str) for item in self.applied_filters):
            raise ValueError('invalid_source_filters')
        if set(self.applied_filters) - FILTERS or self.error_code is not None and self.error_code not in ERROR_CODES:
            raise ValueError('invalid_source_evidence')
        if self.url is not None and not official_url(self.source, self.url):
            raise ValueError('invalid_source_url')
        if self.status == 'not_tested':
            if self.checked_at is not None or self.queries_checked or self.pages_checked or self.matched_count or self.applied_filters:
                raise ValueError('unexecuted_source_cannot_claim_evidence')
        else:
            if not aware(self.checked_at) or not self.queries_checked:
                raise ValueError('source_check_evidence_required')
        if self.status in ('ok_empty', 'ok_with_results'):
            if (not official_url(self.source, self.url) or not self.pages_checked or self.error_code
                    or (self.status == 'ok_empty') != (self.matched_count == 0)):
                raise ValueError('contradictory_source_status')
        elif self.status != 'not_tested' and self.error_code is None:
            raise ValueError('source_failure_reason_required')

    def as_dict(self):
        value = asdict(self)
        value['checked_at'] = self.checked_at.isoformat() if self.checked_at else None
        return value


@dataclass(frozen=True)
class TenderEvidence:
    source: str
    external_id: str
    url: str
    title: str
    checked_at: datetime
    customer: str | None = None
    work_location: str | None = None
    work_region: str | None = None
    location_basis: str = 'unknown'
    price_rub: Decimal | None = None
    raw_price: str | None = None
    currency: str | None = None
    deadline: datetime | None = None
    status: str = 'unknown'
    legal_regime: str | None = None
    matched_topics: tuple[str, ...] = ()
    organizer: str | None = None

    def __post_init__(self):
        if not official_url(self.source, self.url) or not aware(self.checked_at):
            raise ValueError('tender_source_evidence_required')
        if not isinstance(self.external_id, str) or not 1 <= len(self.external_id) <= 128 or not isinstance(self.title, str) or not 1 <= len(self.title) <= 1000:
            raise ValueError('invalid_tender_identity')
        if self.location_basis not in ('unknown', 'customer_region', 'work_address', 'verified_work_region_filter'):
            raise ValueError('invalid_location_basis')
        if type(self.matched_topics) is not tuple or any(not isinstance(item, str) for item in self.matched_topics):
            raise ValueError('invalid_topic_evidence')
        if self.status not in ('unknown', 'accepting', 'closed') or set(self.matched_topics) - BY_ID.keys():
            raise ValueError('invalid_tender_classification')
        if self.legal_regime is not None and self.legal_regime not in REGIMES:
            raise ValueError('invalid_tender_legal_regime')
        if self.source.startswith('eis:') and self.legal_regime is not None and self.source[4:] != self.legal_regime:
            raise ValueError('eis_regime_mismatch')
        if self.deadline is not None and not aware(self.deadline):
            raise ValueError('tender_deadline_timezone_required')
        if self.price_rub is not None and (not isinstance(self.price_rub, Decimal) or not self.price_rub.is_finite() or self.price_rub < 0):
            raise ValueError('invalid_tender_price')
        if self.price_rub is not None and self.currency != 'RUB':
            raise ValueError('ruble_price_requires_confirmed_ruble_currency')
        for value, limit in ((self.customer, 1000), (self.organizer, 1000), (self.work_location, 2000),
                             (self.work_region, 80), (self.raw_price, 160), (self.currency, 3)):
            if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= limit):
                raise ValueError('invalid_tender_text_field')


def evaluate(card: TenderEvidence, request: SearchRequest, now: datetime):
    if not aware(now):
        raise ValueError('explicit_aware_clock_required')
    excluded = []
    review = []
    if card.location_basis in ('work_address', 'verified_work_region_filter') and card.work_region and (
            card.location_basis != 'work_address' or card.work_location):
        if card.work_region != REGION:
            excluded.append('other_work_region')
    else:
        review.append('work_region_unverified')
    if not card.customer:
        review.append('customer_unknown')
    if not set(card.matched_topics) & set(request.topic_ids):
        review.append('topic_unverified')
    text = normalized_text(card.title + ' ' + (card.work_location or ''))
    def contains(phrase):
        return re.search(r'(?<!\w)' + re.escape(normalized_text(phrase)) + r'(?!\w)', text) is not None
    if any(contains(phrase) for phrase in request.exclude_keywords):
        excluded.append('excluded_keyword')
    if request.keywords and not any(contains(phrase) for phrase in request.keywords):
        review.append('keyword_not_verified_in_evidence')
    if card.legal_regime is None:
        review.append('legal_regime_unknown')
    elif card.legal_regime not in request.legal_regimes:
        excluded.append('other_legal_regime')
    if card.deadline is None:
        review.append('deadline_unknown')
    else:
        if request.active_only and card.deadline <= now:
            excluded.append('deadline_expired')
        if request.deadline_from is not None and card.deadline < request.deadline_from:
            excluded.append('deadline_before_range')
        if request.deadline_to is not None and card.deadline > request.deadline_to:
            excluded.append('deadline_after_range')
    if request.active_only:
        if card.status == 'closed':
            excluded.append('closed')
        elif card.status != 'accepting':
            review.append('active_status_unknown')
    if card.currency != 'RUB':
        review.append('currency_unverified_for_ruble_filter')
    if card.price_rub is None:
        review.append('price_unknown')
    else:
        if request.price_min_rub is not None and card.price_rub < request.price_min_rub:
            excluded.append('price_below_range')
        if request.price_max_rub is not None and card.price_rub > request.price_max_rub:
            excluded.append('price_above_range')
    return ('excluded', tuple(excluded)) if excluded else ('review' if review else 'accepted', tuple(review))


def requested_filters(request):
    result = {'region', 'topics', 'legal_regimes'}
    for field in ('keywords', 'exclude_keywords', 'active_only', 'deadline_from', 'deadline_to'):
        if getattr(request, field):
            result.add(field)
    for field in ('price_min_rub', 'price_max_rub'):
        if getattr(request, field) is not None:
            result.add(field)
    return result


def build_report(request, trusted_company_id, outcomes, tenders, *, started_at, completed_at):
    fingerprint = request.fingerprint(trusted_company_id)
    if not aware(started_at) or not aware(completed_at) or completed_at < started_at:
        raise ValueError('invalid_report_clock')
    expected = set(request.commercial_sources)
    if 'eis' in request.sources:
        expected.update('eis:' + regime for regime in request.legal_regimes if regime != 'commercial')
    outcomes = list(islice(outcomes, 12))
    tenders = list(islice(tenders, 2001))
    if len(outcomes) > 11 or len(tenders) > 2000:
        raise ValueError('report_input_limit')
    statuses = {outcome.source: outcome for outcome in outcomes}
    if len(statuses) != len(outcomes) or set(statuses) - expected:
        raise ValueError('unexpected_or_duplicate_source')
    for source in expected - statuses.keys():
        statuses[source] = SourceOutcome(source, 'not_tested')
    if any(outcome.checked_at is not None and not started_at <= outcome.checked_at <= completed_at
           for outcome in statuses.values()):
        raise ValueError('source_check_outside_execution_window')
    identities = {}
    for card in tenders:
        identities.setdefault(card.source, set()).add(card.external_id)
    if any(source in statuses and len(ids) > statuses[source].matched_count
           for source, ids in identities.items()):
        raise ValueError('source_match_count_inconsistent')
    rows = []
    rejected = []
    deduplicated = 0
    seen = {}
    duplicate_conflict = False
    for card in tenders:
        if card.source not in expected:
            raise ValueError('unrequested_tender_source')
        if statuses[card.source].status in ('not_tested', 'ok_empty'):
            raise ValueError('tender_contradicts_source_status')
        if not started_at <= card.checked_at <= completed_at:
            raise ValueError('tender_check_outside_execution_window')
        key = (card.source, card.external_id)
        previous = seen.get(key)
        # Same ID with conflicting facts is retained for review, never merged by title.
        comparable = replace(card, checked_at=started_at)
        if previous == comparable:
            deduplicated += 1
            continue
        conflict = previous is not None
        if conflict:
            duplicate_conflict = True
            for row in rows:
                if row['source'] == card.source and row['external_id'] == card.external_id:
                    row['needs_manual_review'] = True
                    row['reasons'] = sorted(set(row['reasons']) | {'duplicate_identity_conflict'})
        else:
            seen[key] = comparable
        decision, reasons = evaluate(card, request, completed_at)
        if decision == 'excluded':
            rejected.append({'source': card.source, 'external_id': card.external_id, 'reasons': list(reasons)})
            continue
        if statuses[card.source].status not in ('ok_empty', 'ok_with_results'):
            decision = 'review'
            reasons = (*reasons, 'source_check_incomplete')
        value = asdict(card)
        value.update(checked_at=card.checked_at.isoformat(), deadline=card.deadline.isoformat() if card.deadline else None,
                     price_rub=str(card.price_rub) if card.price_rub is not None else None,
                     needs_manual_review=decision == 'review' or conflict,
                     reasons=sorted(set(reasons) | ({'duplicate_identity_conflict'} if conflict else set())))
        rows.append(value)
    good = [outcome for outcome in statuses.values() if outcome.status in ('ok_empty', 'ok_with_results')]
    verified = set.intersection(*(set(outcome.applied_filters) for outcome in statuses.values())) if statuses else set()
    unapplied = sorted(requested_filters(request) - verified)
    limited = len(rows) > request.limit
    missing = any(outcome.status not in ('ok_empty', 'ok_with_results') for outcome in statuses.values())
    uncertain = any(row['needs_manual_review'] for row in rows)
    status = 'failed' if not good and not rows else ('partial' if missing or uncertain or unapplied or duplicate_conflict or limited else 'completed')
    warnings = ['Охват ограничен проверенными запросами и страницами; полный охват рынка не подтверждён.']
    if status != 'completed' and not rows:
        warnings.append('Пустая выдача не доказывает отсутствие закупок: проверка неполна.')
    return {'schema_version': 2, 'request_id': request.request_id, 'company_id': trusted_company_id,
            'request_fingerprint': fingerprint, 'status': status,
            'started_at': started_at.isoformat(), 'completed_at': completed_at.isoformat(),
            'elapsed_seconds': (completed_at - started_at).total_seconds(),
            'filters': request.canonical_payload(), 'applied_filters': sorted(verified), 'unapplied_filters': unapplied,
            'sources_status': [statuses[source].as_dict() for source in sorted(statuses)],
            'tenders': rows[:request.limit], 'excluded': rejected, 'excluded_count': len(rejected),
            'deduplicated_count': deduplicated, 'omitted_by_limit': max(0, len(rows) - request.limit),
            'warnings': warnings,
            'errors': [{'source': outcome.source, 'code': outcome.error_code or 'not_tested'}
                       for outcome in statuses.values() if outcome.status not in ('ok_empty', 'ok_with_results')]}
