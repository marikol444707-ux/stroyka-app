"""Plain-text completion preview. Never sends Telegram messages or uses LLMs."""
from decimal import Decimal, InvalidOperation
import re

from .contract import MOSCOW
from .evidence import parse_deadline
from .reporting import official_url
from .state import Scope

REASONS={
    'work_region_unverified':'место работ не подтверждено', 'customer_unknown':'заказчик не подтверждён',
    'topic_unverified':'вид работ требует проверки','legal_regime_unknown':'правовой режим не указан',
    'deadline_unknown':'срок не указан','active_status_unknown':'приём заявок не подтверждён',
    'currency_unverified_for_ruble_filter':'валюта не подтверждена','price_unknown':'цена не указана',
    'source_check_incomplete':'источник проверен не полностью','duplicate_identity_conflict':'конфликт данных одного номера',
    'keyword_not_verified_in_evidence':'ключевые слова не подтверждены в описании',
}
SOURCE_STATUS={'not_tested':'не проверен','ok_empty':'проверенная выдача пуста',
               'ok_with_results':'получена выдача','partial':'проверен частично','error':'ошибка проверки',
               'unavailable':'недоступен','blocked_by_login_or_captcha':'требует входа или CAPTCHA'}


def _line(value, limit=300):
    return re.sub(r'[\x00-\x20\x7f]+',' ',value if isinstance(value,str) else '').strip()[:limit]


def _money(row):
    if row.get('currency')!='RUB' or row.get('price_rub') is None:return 'не указана в подтверждённой валюте RUB'
    try:
        value=Decimal(row['price_rub'])
        if not value.is_finite() or not 0<=value<=Decimal('1000000000000'):return 'требует проверки'
        return f'{value:,.2f} ₽'.replace(',',' ').replace('.',',')
    except (InvalidOperation,ValueError,TypeError):return 'требует проверки'


def render_report(report, scope, *, max_chars=3500):
    """Bounded preview for a protected owner; send as plain text, no parse_mode.

    Omitted cards/links are disclosed. This is not a Telegram delivery receipt.
    """
    if (type(scope) is not Scope or type(report) is not dict or type(report.get('company_id')) is not int
            or report['company_id']!=scope.company_id or report.get('schema_version')!=2):
        raise ValueError('authorized_report_required')
    if report.get('protected_scope')!=scope.key():raise ValueError('authorized_report_required')
    if type(max_chars) is not int or not 1000<=max_chars<=4000:raise ValueError('invalid_preview_size')
    tenders=report.get('tenders',[]);links=report.get('unverified_links',[])
    lines=[{'failed':'Проверка не завершена.','partial':'Результат неполный.',
            'completed':'Результат проверки.'}.get(report.get('status'),'Статус требует проверки.'),
           f"Запрос: {_line(report.get('request_id'),64)}",
           f'Карточек: {len(tenders)}; отдельно ссылок из выдачи ЕИС: {len(links)}.',
           f"Исключено при проверке: {report.get('excluded_count',0)}."]
    if report.get('reason') in ('execution_interrupted','execution_failed','execution_not_completed','runtime_changed'):
        lines.append('Причина: '+{'execution_interrupted':'выполнение прервано; повторный поиск не запускался.',
            'execution_failed':'ошибка выполнения; требуется проверка.',
            'execution_not_completed':'выполнение не завершено.',
            'runtime_changed':'версия установленного CLI не совпадает с проверенной.'}[report['reason']])
    if not tenders and not links:lines.append('Подходящие карточки не подтверждены. Это не доказывает отсутствие закупок.')
    blocks=[]
    for row in tenders:
        if not official_url(row.get('source'),row.get('url')):continue
        deadline=parse_deadline(row.get('deadline'))
        block=[_line(row.get('title')),f"Источник: {_line(row.get('source'))}",
               f'Цена: {_money(row)}',
               'Подача до: '+(deadline.astimezone(MOSCOW).strftime('%d.%m.%Y %H:%M МСК') if deadline else 'не указана')]
        if row.get('organizer'):block.append('Организатор: '+_line(row['organizer']))
        if row.get('customer'):block.append('Заказчик: '+_line(row['customer']))
        reasons=row.get('reasons',[])
        if reasons:block.append('Проверить: '+', '.join(dict.fromkeys(REASONS.get(reason,'данные первоисточника') for reason in reasons)))
        elif row.get('needs_manual_review'):block.append('Требует проверки первоисточника.')
        block.append(row['url']);blocks.append('\n'.join(block))
    for link in links:
        if official_url(link.get('source'),link.get('url')):
            blocks.append('ЕИС: ссылка из выдачи; карточка, сумма и срок не проверены.\n'+link['url'])
    sources=['Источники:']
    for source in report.get('sources_status',[]):
        status=SOURCE_STATUS.get(source.get('status'),'статус неизвестен')
        if source.get('error_code')=='unsupported_regime':status='этот режим не поддерживается установленной командой'
        sources.append(_line(source.get('source'))+': '+status)
    footer=['\n'.join(sources),
            'Охват ограничен проверенными запросами и страницами; полнота рынка не подтверждена.']
    if report.get('unapplied_filters'):footer.append('Часть фильтров не подтверждена для всех источников; неизвестные данные требуют проверки.')
    if report.get('adapter_preexcluded_counts'):footer.append('Часть выдачи отсеяна исходным адаптером; карточки этих исключений недоступны.')
    if report.get('normalization_issues'):footer.append('Есть ошибки получения или проверки данных источников.')
    tail='\n'.join(footer)
    head='\n'.join(lines)
    selected=[]
    for block in blocks:
        # Reserve a short truncation notice, and never cut a procedure URL.
        candidate='\n\n'.join([head,*selected,block,tail])
        if len(candidate)>max_chars-100:break
        selected.append(block)
    omitted=len(blocks)-len(selected)+report.get('omitted_by_limit',0)
    if omitted:tail=f'В этом сообщении не показано записей: {omitted}.\n'+tail
    text='\n\n'.join([head,*selected,tail])
    if len(text)>max_chars:
        # Large source/warning sets cannot silently erase the size bound.
        raise ValueError('preview_metadata_exceeds_size_limit')
    return text
