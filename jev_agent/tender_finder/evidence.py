"""Conservative binding of pinned discovery fields to the evidence policy.

No fetches. Listing fields are observations, not verified full procedure cards.
In particular organizer/customer and customer/worksite regions are independent.
Upstream 'confirmed' never overrides this module's checks.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import re
from urllib.parse import parse_qs, urlsplit

from jev_agent.server_runtime.scripts.jev_commercial_search import (
    EQUIPMENT_REPAIR, GOODS_ONLY, WORK_ACTION, procedure_url)

from .catalog import TOPICS, normalized_text
from .contract import MAX_PRICE, MOSCOW, REGION, SearchRequest
from .discovery import PROVIDER_LABELS
from .reporting import SourceOutcome, TenderEvidence, aware, build_report, official_url
from .state import Scope


def parse_price(value):
    """Only an exact amount with explicit RUB label. No currency conversion."""
    if not isinstance(value,str) or len(value)>160:
        return None,None
    text=' '.join(value.split())
    match=re.fullmatch(r'((?:[0-9]{1,3}(?: [0-9]{3})+|[0-9]+)(?:[.,][0-9]{1,2})?)\s*(?:₽|руб\.?|рублей|RUB)',text,re.I)
    if not match:
        return None,None
    amount=Decimal(match[1].replace(' ','').replace(',','.'))
    return (amount,'RUB') if amount <= MAX_PRICE else (None,None)


def parse_deadline(value):
    if not isinstance(value,str) or len(value)>160:
        return None
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if aware(result):return result
    except ValueError:
        pass
    # The reviewed adapters normalize these fields as Moscow time, not local
    # workstation time. Date-only and unrecognized free text stay unknown.
    if re.fullmatch(r'[0-9]{2}\.[0-9]{2}\.[0-9]{4} [0-9]{2}:[0-9]{2}(?: МСК)?',value):
        try:return datetime.strptime(value.removesuffix(' МСК'),'%d.%m.%Y %H:%M').replace(tzinfo=MOSCOW)
        except ValueError:pass
    return None


def match_topics(title):
    text=normalized_text(title)
    return tuple(topic.id for topic in TOPICS if any(
        re.search(r'(?<!\w)'+re.escape(normalized_text(phrase))+r'(?!\w)',text)
        for phrase in (topic.name,topic.query,*topic.aliases)))


def commercial_card(row, checked_at):
    if type(row) is not dict:
        raise ValueError('invalid_listing_row')
    source=row.get('source');identifier=row.get('id');title=row.get('title')
    if (source not in set(PROVIDER_LABELS.values()) or type(identifier) not in (str,int)
            or not str(identifier) or len(str(identifier))>128 or not isinstance(title,str)
            or not title.strip() or len(title)>1000):
        raise ValueError('invalid_listing_identity')
    url=procedure_url(row)
    if source=='B2B-Center' and not url.endswith('/tender-'+str(identifier)+'/'):
        raise ValueError('procedure_identity_conflict')
    if source=='Росэлторг' and urlsplit(url).path.split('/')[2] != str(identifier):
        raise ValueError('procedure_identity_conflict')
    if source=='ТЭК-Торг' and urlsplit(url).path.rsplit('/',1)[-1] != str(row.get('procedure_record_id')):
        raise ValueError('procedure_identity_conflict')
    if source=='Р-ТЕНДЕР' and parse_qs(urlsplit(url).query).get('LotCard.lotEntity') != ['LT:'+str(row.get('procedure_record_id'))]:
        raise ValueError('procedure_identity_conflict')
    price,currency=parse_price(row.get('price'))
    deadline=parse_deadline(row.get('deadline'))
    derived=parse_deadline(row.get('deadline_msk'))
    if derived is not None:
        deadline=derived if deadline is None or deadline==derived else None
    regime_text=normalized_text(row.get('regime','')) if isinstance(row.get('regime',''),str) else ''
    regime={'коммерческая закупка':'commercial','коммерческие закупки':'commercial',
            'коммерческая':'commercial','коммерческие':'commercial',
            '44-фз':'44-ФЗ','223-фз':'223-ФЗ','615-пп':'615-ПП'}.get(regime_text)
    status_text=normalized_text(row.get('status','')) if isinstance(row.get('status',''),str) else ''
    # Do not turn a future deadline or upstream decision into accepting status.
    status={'прием заявок':'accepting','подача заявок':'accepting',
            'завершена':'closed','завершено':'closed','отменена':'closed'}.get(status_text,'unknown')
    def optional(name,limit):
        value=row.get(name)
        return value.strip() if isinstance(value,str) and 0<len(value.strip())<=limit else None
    # No pinned listing adapter has a separately verified customer/address field.
    # Even Sber's region_scope=worksite can be derived from its title.
    return TenderEvidence(source,str(identifier),url,title.strip(),checked_at,
        organizer=optional('organizer',1000),work_location=optional('place',2000),
        location_basis='customer_region' if row.get('region_scope')=='customer_region_filter' else 'unknown',
        price_rub=price,currency=currency,raw_price=optional('price',160),deadline=deadline,
        legal_regime=regime,status=status,matched_topics=match_topics(title))


def evidence_report(request, scope, discovery, *, started_at, completed_at):
    if type(request) is not SearchRequest or type(scope) is not Scope:
        raise ValueError('protected_normalized_context_required')
    scope.key()
    if (type(discovery) is not dict or discovery.get('request_id')!=request.request_id
            or type(discovery.get('company_id')) is not int or discovery['company_id']!=scope.company_id):
        raise ValueError('discovery_scope_mismatch')
    if not aware(started_at) or not aware(completed_at) or completed_at<started_at:
        raise ValueError('invalid_report_clock')
    outputs=discovery.get('outputs')
    if type(outputs) is not list or len(outputs)>21:
        raise ValueError('invalid_discovery_outputs')
    source_rows=defaultdict(list);cards=[];issues=[];links=[];eis_outputs=[];preexcluded={};excluded=[]
    invalid_sources=set();unknown_invalid_source=False
    for output in outputs:
        raw=output.get('report')
        if output.get('source')=='eis':
            eis_outputs.append(output)
            if type(raw) is dict:
                for link in raw.get('notice_links',[]):
                    if official_url('eis:44-ФЗ',link):
                        links.append({'source':'eis:44-ФЗ','url':link,'query':output.get('query'),
                                      'title':None,'price_rub':None,'deadline':None,'needs_manual_review':True})
            continue
        if output.get('source')!='commercial':raise ValueError('unexpected_discovery_group')
        if type(raw) is not dict:
            issues.append({'source':'commercial','code':output.get('code') or 'invalid_response'})
            continue
        for source_row in raw.get('sources',[]):
            label=source_row.get('provider')
            source=PROVIDER_LABELS.get(label) if isinstance(label,str) else None
            if source not in request.commercial_sources:
                issues.append({'source':'commercial','code':'unexpected_source_label'});continue
            source_rows[source].append(source_row)
        for field in ('confirmed','review'):
            for row in raw.get(field,[]):
                try:
                    card=commercial_card(row,completed_at)
                    if card.source not in request.commercial_sources:raise ValueError('unrequested_source')
                    reason=('equipment_repair_not_building_work' if EQUIPMENT_REPAIR.search(card.title) else
                            'goods_purchase_not_work' if GOODS_ONLY.search(card.title) and not WORK_ACTION.search(card.title) else None)
                    if reason:
                        excluded.append({'source':card.source,'external_id':card.external_id,'reasons':[reason]})
                        continue
                    cards.append(card)
                except (ValueError,KeyError,TypeError):
                    issues.append({'source':'commercial','code':'invalid_listing_row'})
                    source=row.get('source') if type(row) is dict else None
                    if isinstance(source,str) and source in request.commercial_sources:invalid_sources.add(source)
                    else:unknown_invalid_source=True
        counts=raw.get('excluded',{})
        if type(counts) is not dict:
            issues.append({'source':'commercial','code':'invalid_adapter_exclusion_counts'})
            counts={}
        for reason,count in counts.items():
            if isinstance(reason,str) and re.fullmatch('[a-z_]{1,64}',reason) and type(count) is int and 0<=count<=10000:
                preexcluded[reason]=preexcluded.get(reason,0)+count
    outcomes=[]
    for source in request.commercial_sources:
        observed=source_rows[source]
        urls=[row['url'] for row in observed if official_url(source,row.get('url'))]
        count=len({card.external_id for card in cards if card.source==source})
        success=(bool(observed) and bool(urls) and all(row.get('ok') is True for row in observed)
                 and source not in invalid_sources and not unknown_invalid_source)
        if not observed and not count:
            outcomes.append(SourceOutcome(source,'not_tested'))
            continue
        outcomes.append(SourceOutcome(source,'ok_with_results' if count else 'ok_empty',
            checked_at=completed_at,url=urls[0],queries_checked=len(observed),pages_checked=len(observed),matched_count=count)
            if success else SourceOutcome(source,'error',checked_at=completed_at,url=urls[0] if urls else None,
                queries_checked=max(1,len(observed)),matched_count=count,
                error_code='invalid_response' if source in invalid_sources or unknown_invalid_source else 'coverage_unverified'))
    if 'eis' in request.sources:
        for regime in request.legal_regimes:
            if regime=='commercial':continue
            source='eis:'+regime
            if regime!='44-ФЗ' or not eis_outputs:
                outcomes.append(SourceOutcome(source,'not_tested',error_code='unsupported_regime' if regime!='44-ФЗ' else 'not_tested'))
                continue
            urls=[out['report']['url'] for out in eis_outputs if type(out.get('report')) is dict
                  and official_url(source,out['report'].get('url'))]
            count=len({link['url'] for link in links})
            success=bool(urls) and all(out.get('status')=='completed' for out in eis_outputs)
            outcomes.append(SourceOutcome(source,'ok_with_results' if count else 'ok_empty',checked_at=completed_at,
                url=urls[0],queries_checked=len(eis_outputs),pages_checked=len(eis_outputs),matched_count=count)
                if success else SourceOutcome(source,'error',checked_at=completed_at,url=urls[0] if urls else None,
                    queries_checked=len(eis_outputs),matched_count=count,error_code='coverage_unverified'))
    value=build_report(request,scope.company_id,outcomes,cards,started_at=started_at,completed_at=completed_at)
    value.update(unverified_links=list({link['url']:link for link in links}.values()),normalization_issues=issues,
                 adapter_preexcluded_counts=preexcluded,discovery_status=discovery.get('status'),
                 card_acceptance_complete=False,telegram_delivery_verified=False,protected_scope=scope.key())
    value['excluded'].extend(excluded)
    value['excluded_count']+=len(excluded)
    if links:value['warnings'].append('Ссылки ЕИС получены из выдачи; содержание карточек, суммы и сроки ещё не проверены.')
    if issues:value['warnings'].append('Часть данных источников неполна или отклонена при проверке формата.')
    if preexcluded:value['warnings'].append('Исходный адаптер уже отсеял часть выдачи; индивидуальные карточки этих исключений недоступны.')
    if issues or links or preexcluded:
        if value['status']=='completed':value['status']='partial'
    return value
