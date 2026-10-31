"""One bounded commercial run using operator-bound read-only source adapters.

Adapters discover AND freshly inspect primary cards/documents. Merely having a
name in the inventory cannot produce an 'empty' or successful source result.
No default network, model, messaging, login, schedules or installation callbacks.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import time
from zoneinfo import ZoneInfo

from .model import Candidate, Document, Profile, aware
from .model import public_url
from .policy import assess
from .registry import compare, deduplicate, digest, registry
from .sources import source_registry, LIMITATION_LABELS
from ..state import RequestConflict


@dataclass(frozen=True)
class SourceResult:
    status: str  # checked / partial / unavailable / login_required / captcha / error
    candidates: tuple[Candidate, ...] = ()
    # Captures from a successfully read listing page prove an empty search.
    listings: tuple = ()
    limitations: tuple[str, ...] = ()
    primary_captures: tuple = ()
    attachment_statuses: tuple = ()


def _profile(profile):
    return {'regions': list(profile.regions), 'minimum_rub': str(profile.minimum_rub),
            'legal_entity': profile.legal_entity, 'qualifications': sorted(profile.qualifications),
            'queries':list(profile.queries),'exclude_keywords':list(profile.exclude_keywords)}


def run(request_id, scope, directory, *, adapters, sources=None, profile=Profile(),
        clock=lambda: datetime.now(timezone.utc),monotonic=time.monotonic):
    """adapters[source_id](profile, started_at) -> SourceResult; trusted bindings.

    A protected registry directory must be provisioned explicitly by the caller.
    Existing v2 queue/schema/signatures/tool registration remain unchanged.
    """
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', request_id):
        raise ValueError('bounded_request_id_required')
    profile.validate()
    if not callable(monotonic):raise ValueError('protected_monotonic_clock_required')
    sources = source_registry() if sources is None else sources
    if set(adapters) - set(sources): raise ValueError('registered_sources_required')
    for key, source in sources.items():
        if source.id != key: raise ValueError('source_identity_conflict')
    fingerprint = digest({'profile': _profile(profile),
                          'sources': [(key, value.hosts) for key, value in sorted(sources.items())]})
    hosts = {key: source.hosts for key, source in sources.items()}
    with registry(directory, scope) as (previous, save):
        requests = {} if previous is None else previous['requests']
        if request_id in requests:
            old = requests[request_id]
            if old['fingerprint'] != fingerprint: raise RequestConflict('commercial_request_conflict')
            if old['status'] != 'completed':
                return {'request_id': request_id, 'status': 'interrupted', 'search_repeated': False,
                        'reason': 'previous_run_not_committed_requires_review'}
            return old['report']
        if len(requests) >= 1000: raise ValueError('commercial_registry_retention_review_required')
        started = clock()
        deadline=monotonic()+600
        if not aware(started): raise ValueError('aware_clock_required')
        records = {} if previous is None else previous['records']
        history = [] if previous is None else previous['history']
        # A crash after a search starts must not silently execute the same run
        # again. Baseline availability is separate from the running reservation.
        requests[request_id] = {'fingerprint': fingerprint, 'status': 'running'}
        save({'records': records, 'history': history, 'requests': requests,
              'baseline_established': bool(previous and previous.get('baseline_established'))})
        rows, coverage = [], []
        for key, source in sources.items():
            status, cards, documents, limitations, attachments = 'not_connected', set(), set(), (), ()
            adapter = adapters.get(key)
            if adapter is not None and source.hosts and monotonic()>=deadline:
                status='not_checked_due_budget';limitations=('read_budget_exhausted',)
            elif adapter is not None and source.hosts:
                try:
                    output = adapter(profile, started)
                    completed = clock()
                    if not aware(completed) or completed < started: raise ValueError('invalid_run_clock')
                    if (type(output) is not SourceResult or output.status not in (
                            'checked', 'partial', 'unavailable', 'login_required', 'captcha', 'error','robots_disallow','policy_not_verified')
                            or len(output.candidates) > 100 or len(output.listings) > 50
                            or len(output.primary_captures)>100 or len(output.attachment_statuses)>800):
                        raise ValueError('bounded_source_result_required')
                    if type(output.limitations) is not tuple or set(output.limitations)-set(LIMITATION_LABELS):
                        raise ValueError('fixed_source_limitations_required')
                    limitations=output.limitations
                    from urllib.parse import urlsplit
                    for entry in output.attachment_statuses:
                        if (type(entry) is not dict or set(entry)!={'url','name','status'}
                                or not public_url(entry['url']) or urlsplit(entry['url']).hostname not in hosts[key]
                                or type(entry['name']) is not str or not 1<=len(entry['name'])<=300
                                or entry['status'] not in ('text','needs_review_or_ocr','encrypted','login_required',
                                                          'captcha','unavailable','not_verified','robots_disallow','policy_not_verified')):
                            raise ValueError('bounded_attachment_status_required')
                    attachments=output.attachment_statuses
                    assessed = []
                    for candidate in output.candidates:
                        if candidate.source != key: raise ValueError('source_candidate_mismatch')
                        row = assess(candidate, completed, hosts, profile, run_started_at=started)
                        assessed.append(row)
                    from urllib.parse import urlsplit
                    for listing in output.listings:
                        if (type(listing) is not Document or listing.source != key
                                or listing.kind != 'card' or urlsplit(listing.url).hostname not in hosts[key]
                                or not started <= listing.checked_at <= completed):
                            raise ValueError('fresh_listing_evidence_required')
                    for capture in output.primary_captures:
                        if (type(capture) is not Document or capture.kind!='card' or capture.source!=key
                                or urlsplit(capture.url).hostname not in hosts[key]
                                or not started<=capture.checked_at<=completed):
                            raise ValueError('fresh_primary_capture_required')
                    captures = [doc for candidate in output.candidates for doc in candidate.documents
                                if started <= doc.checked_at <= completed]
                    captures.extend(output.primary_captures)
                    cards = {doc.url for doc in captures if doc.kind == 'card'}
                    documents = {(doc.url, doc.sha256) for doc in captures
                                 if doc.kind not in ('card', 'aggregator')}
                    status = output.status
                    if status=='checked' and limitations:status='partial'
                    if status == 'checked' and not output.listings:
                        # Individual cards do not establish complete source coverage.
                        status = 'partial'
                    rows.extend(assessed)
                except Exception:
                    # Source errors may contain tokens/URLs. Emit fixed codes only.
                    status, cards, documents = 'error', set(), set()
            coverage.append({'source': key, 'name': source.name, 'status': status,
                             'primary_cards': len(cards), 'documents': len(documents),
                             'limitations':list(limitations),'attachments':list(attachments)})
        # Unconfirmed rediscovery cannot erase last verified values. It remains
        # visible in this report while history keeps the last primary observation.
        rows = deduplicate(rows)
        observed = [row for row in rows if any(e.get('kind') == 'card'
                    and started <= datetime.fromisoformat(e['checked_at'])
                    for entries in row['evidence'].values() for e in entries)]
        comparison = previous if previous and previous.get('baseline_established') else None
        merged, additions, changes, baseline = compare(observed, comparison)
        # Include preserved records omitted due to outages; absence != closure.
        merged = {**records, **merged}
        sections = {name: [] for name in ('priority', 'postpayment', 'changes', 'qualifications',
                                          'unconfirmed', 'adjacent', 'excluded')}
        for row in rows: sections[row['bucket']].append(row)
        sections['changes'] = changes
        new_confirmed = [merged[key] for key in additions
                         if merged[key]['bucket'] in ('priority', 'postpayment', 'adjacent')]
        report = {'format': 3, 'request_id': request_id, 'status': 'completed',
                  'baseline': baseline, 'new_confirmed_count': len(new_confirmed),
                  'new_keys': additions, 'change_count': len(changes),
                  'started_at': started.astimezone(ZoneInfo('Europe/Moscow')).isoformat(),
                  'completed_at': clock().astimezone(ZoneInfo('Europe/Moscow')).isoformat(),
                  'profile': _profile(profile), 'sections': sections, 'coverage': coverage,
                  'sources_complete': all(row['status'] == 'checked' for row in coverage),
                  'read_only_sources': True, 'notifications_sent': False,
                  'source_text_is_untrusted_data': True}
        requests[request_id] = {'fingerprint': fingerprint, 'status': 'completed', 'report': report}
        save({'records': merged, 'history': history + changes, 'requests': requests,
              'baseline_established': bool(observed) or bool(previous and previous.get('baseline_established'))})
        return report


def render(report):
    """Plain text output. Source text cannot inject Telegram HTML/Markdown."""
    lines = [f"Подтверждённых новых кандидатов: {report['new_confirmed_count']}. "
             f"Существенных изменений: {report['change_count']}."]
    if report['baseline']: lines.append('Первый базовый сбор: находки не объявляются новыми.')
    headings = (('priority', 'Активные прямые закупки с подходящей оплатой'),
                ('postpayment', 'Активные закупки с постоплатой'),
                ('changes', 'Изменения известных закупок'),
                ('qualifications', 'Квалификации и бездатные приглашения'),
                ('adjacent', 'Текущий ремонт и модернизация'),
                ('unconfirmed', 'Неподтверждённые находки'), ('excluded', 'Исключённые находки'))
    for key, title in headings:
        lines.append('\n' + title)
        rows = report['sections'][key]
        if not rows: lines.append('Нет подтверждённых находок.' if key != 'changes' else 'Нет изменений.')
        for row in rows:
            if key == 'changes':
                lines.append(f"{row['number']}: {row['field']}: {row['before']} → {row['after']}")
                continue
            values = row['values']
            lines.append(f"№ {row['number']}: {values.get('title', 'Не удалось проверить')}")
            for field, label in (('organizer', 'Организатор'), ('counterparty', 'Контрагент'), ('work_address', 'Объект'),
                                 ('work_scope', 'Работы'), ('price', 'Бюджет'), ('currency', 'Валюта'),
                                 ('vat', 'НДС'), ('stage', 'Этап'), ('deadline', 'Дедлайн'), ('payment', 'Оплата'),
                                 ('advance_conditions', 'Условия аванса'), ('payment_period', 'Срок расчёта'),
                                 ('customer_materials', 'Материалы заказчика'), ('security', 'Обеспечение'),
                                 ('guarantee', 'Банковская гарантия'), ('retention', 'Удержания'),
                                 ('construction_period', 'Срок строительства'), ('design_period', 'Срок проектирования'),
                                 ('experience', 'Опыт'), ('construction_sro', 'Строительная СРО'),
                                 ('design_sro', 'Проектная СРО'), ('fire_license', 'Лицензия МЧС'),
                                 ('accreditation', 'Аккредитация'), ('site_visit', 'Осмотр'),
                                 ('submission', 'Подача'), ('documents', 'Документы'), ('requirements', 'Требования')):
                missing = row['evidence'][field][0].get('missing', 'Не удалось проверить')
                lines.append(f"{label}: {values.get(field, missing)}")
                for evidence in row['evidence'][field]:
                    if 'value' in evidence:
                        lines.append(f"  Источник: {evidence['document']}, {evidence['locator']}; "
                                     f"{evidence['url']}; проверено {evidence['checked_at']}")
            lines.extend(row['links'])
            lines.extend('Риск: ' + risk for risk in row['risks'] + row['exclusions'])
    lines.append('\nОбъём поиска')
    for source in report['coverage']:
        lines.append(f"{source['name']}: {source['status']}; "
                     f"карточек {source['primary_cards']}, документов {source['documents']}")
        lines.extend('Ограничение: '+LIMITATION_LABELS[item] for item in source.get('limitations',()))
        for attachment in source.get('attachments',()):
            lines.append(attachment['name']+': '+attachment['status']+'; '+attachment['url'])
    return '\n'.join(lines)
