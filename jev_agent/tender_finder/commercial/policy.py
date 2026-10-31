"""Deterministic direct-contract and financing triage; no invented economics."""
from datetime import datetime, timedelta
from decimal import Decimal

from .model import FIELDS, Profile


def assess(candidate, now, hosts, profile=Profile(), *, run_started_at=None):
    profile.validate()
    docs = candidate.validate(now, hosts)
    start = run_started_at or now - timedelta(hours=1)
    if start > now:
        raise ValueError('invalid_run_window')
    evidence, values, conflicts = {}, {}, []
    for name in sorted(FIELDS):
        rows = []
        for fact in candidate.facts.get(name, ()):
            if fact.missing:
                rows.append({'missing': fact.missing})
                continue
            doc = docs[fact.document]
            rows.append({'value': fact.value, 'url': doc.url, 'document': doc.name,
                         'locator': fact.locator, 'quote': fact.quote,
                         'checked_at': doc.checked_at.isoformat(), 'sha256': doc.sha256,
                         'kind': doc.kind,'complete':doc.complete})
        evidence[name] = rows or [{'missing': 'Не удалось проверить'}]
        # Aggregator claims never establish facts. Stale captures remain visible,
        # but cannot override a new primary page or establish current acceptance.
        primary = [row for row in rows if 'value' in row and row['kind'] != 'aggregator'
                   and row['complete']
                   and start <= datetime.fromisoformat(row['checked_at']) <= now]
        if name == 'stage':
            primary = [row for row in primary if row['kind'] == 'card']
            if primary:
                latest = max(datetime.fromisoformat(row['checked_at']) for row in primary)
                primary = [row for row in primary if datetime.fromisoformat(row['checked_at']) == latest]
        distinct = {row['value'] for row in primary}
        if len(distinct) > 1:
            conflicts.append(name)
        elif distinct:
            values[name] = next(iter(distinct))

    cards = [doc for doc in docs.values() if doc.kind == 'card' and start <= doc.checked_at <= now]
    risks, exclusions = [], []
    incomplete_documents=any(not doc.complete for doc in docs.values())
    inaccessible_documents=any(fact.missing=='Не удалось проверить' for fact in candidate.facts.get('documents',()))
    if incomplete_documents:risks.append('Неполный текст документа: требуется проверка или OCR')
    if inaccessible_documents:risks.append('Документ с условиями не удалось проверить')
    searchable = ' '.join(values.get(name,'') for name in ('title','work_scope')).casefold().replace('ё','е')
    if any(word.casefold().replace('ё','е') in searchable for word in profile.exclude_keywords):
        exclusions.append('Совпадение со словами исключения')
    if not cards: risks.append('Первичная карточка в этом запуске не проверена')
    if conflicts: risks.append('Противоречия источников: ' + ', '.join(conflicts))
    region = values.get('work_region')
    if region and region not in profile.regions: exclusions.append('Работы вне выбранных регионов')
    if not region or not values.get('work_address'): risks.append('Место выполнения работ не подтверждено')
    role = values.get('role')
    direct = (role == 'owner' or role == 'authorized_operator' and values.get('authority') == 'confirmed')
    if role == 'general_contractor': exclusions.append('Предложение субподряда от генподрядчика')
    if not direct or not values.get('counterparty'):
        risks.append('Прямой договор не подтверждён')
    if values.get('regime') in ('44-ФЗ', '223-ФЗ', '615-ПП'):
        exclusions.append('Регулируемая закупка: отдельно по поручению')
    elif values.get('regime') != 'commercial': risks.append('Коммерческий характер закупки не подтверждён')
    kind = values.get('kind')
    if kind in ('goods', 'equipment_rental', 'maintenance', 'design_only', 'other'):
        exclusions.append('Нецелевой состав работ')
    if not kind or not values.get('work_scope'): risks.append('Состав ремонтных работ не подтверждён')
    price = values.get('price')
    if price is None:
        risks.append('Бюджет: Требует уточнения')
    elif values.get('currency') != 'RUB':
        risks.append('Бюджет не подтверждён в рублях; конвертация не выполнялась')
    elif Decimal(price) < profile.minimum_rub:
        exclusions.append('Бюджет ниже ориентира')
    stage = values.get('stage')
    if stage in ('suspended', 'cancelled', 'closed', 'archive'):
        exclusions.append('Процедура не принимает предложения')
    if not stage: risks.append('Актуальный этап не подтверждён')
    deadline = values.get('deadline')
    expired = False
    if stage == 'accepting':
        if deadline:
            try:
                parsed = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                if parsed.utcoffset() is None: raise ValueError()
                if parsed <= now:
                    expired = True
                    risks.append('Дедлайн истёк при статусе активного приёма')
            except ValueError:
                risks.append('Точное время или часовой пояс дедлайна не подтверждены')
        else:
            risks.append('Дедлайн не подтверждён')

    eligibility = {}
    for qualification in ('construction_sro', 'design_sro', 'fire_license'):
        requirement = values.get(qualification)
        eligibility[qualification] = ('Не требуется' if requirement == 'not_required' else
            'Не удалось проверить' if requirement in (None, 'unknown') else
            'Требует уточнения для выбранного юридического лица' if not profile.legal_entity else
            'Подтверждено профилем' if qualification in profile.qualifications else
            'Требование не подтверждено профилем')
        if requirement == 'required' and eligibility[qualification] != 'Подтверждено профилем':
            risks.append(qualification + ': ' + eligibility[qualification])
    payment = values.get('payment')
    financing = ('advance' if payment == 'advance' and values.get('advance_conditions') else
                 'customer_materials' if values.get('customer_materials') == 'yes' else
                 'staged' if payment == 'staged' and values.get('payment_period') else
                 'postpayment' if payment == 'postpayment' else 'unknown')
    if payment == 'advance' and not values.get('advance_conditions'):
        risks.append('Условия получения и зачёта аванса не проверены')
    if financing == 'unknown': risks.append('Финансирование: Требует уточнения')
    if financing == 'postpayment': risks.append('Потребуются оборотные средства; кассовый разрыв не рассчитан')

    # Missing price/deadline is visible, never a synthetic zero or exclusion.
    critical = ('title', 'counterparty', 'work_region', 'work_address', 'work_scope', 'kind', 'regime', 'stage')
    confirmed = (bool(cards) and direct and all(name in values for name in critical) and not conflicts and not expired
                 and not incomplete_documents and not inaccessible_documents)
    bucket = ('excluded' if exclusions else 'unconfirmed' if not confirmed else
              'qualifications' if stage in ('qualification', 'standing') else
              'adjacent' if kind in ('current_repair', 'engineering_modernization') else
              'postpayment' if financing == 'postpayment' else
              'priority' if financing in ('advance', 'customer_materials', 'staged') else 'unconfirmed')
    return {'source': candidate.source, 'number': candidate.number,
            'links': sorted({doc.url for doc in docs.values()}), 'values': values,
            'evidence': evidence, 'conflicts': conflicts, 'bucket': bucket,
            'direct_contract_confirmed': direct and bool(values.get('counterparty')),
            'financing': financing, 'risks': risks, 'exclusions': exclusions,
            'eligibility': eligibility, 'checked_at': now.isoformat()}
