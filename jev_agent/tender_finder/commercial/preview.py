"""Bounded, scope-checked Telegram preview; full evidence remains in report JSON."""
import re

from ..state import Scope


def render_preview(report,scope,*,max_chars=1800):
    if (type(scope) is not Scope or type(report) is not dict or report.get('schema_version')!=3
            or type(report.get('company_id')) is not int or report['company_id']!=scope.company_id
            or report.get('protected_scope')!=scope.key()):
        raise ValueError('authorized_commercial_report_required')
    if type(max_chars) is not int or not 1000<=max_chars<=4000:raise ValueError('bounded_preview_required')
    def line(value,limit=160):return re.sub(r'[\x00-\x20\x7f]+',' ',str(value)).strip()[:limit]
    coverage=report['coverage']
    lines=[f"Прямые коммерческие заказы. Запрос: {line(report['request_id'],64)}",
           f"Подтверждённых новых: {report['new_confirmed_count']}; изменений: {report['change_count']}.",
           f"Проверено источников: {sum(row['status']=='checked' for row in coverage)}/{len(coverage)}."]
    if report['baseline']:lines.append('Первый базовый сбор; находки не объявляются новыми.')
    inaccessible=[line(row['name'],60)+': '+line(row['status'],30) for row in coverage if row['status']!='checked']
    if inaccessible:lines.append('Ограничения: '+'; '.join(inaccessible[:4])+(' …' if len(inaccessible)>4 else ''))
    sections=report['sections'];shown=0
    total=sum(len(sections.get(key,[])) for key in ('priority','postpayment','adjacent','qualifications','unconfirmed'))
    suffix='\nПолные условия, доказательства и изменения — в сохранённом отчёте JEV.'
    for key,label in (('priority','Приоритет'),('postpayment','Постоплата'),('adjacent','Текущий ремонт/модернизация'),
                      ('qualifications','Квалификация'),('unconfirmed','Не подтверждено')):
        for row in sections.get(key,[]):
            values=row['values']
            block=f"\n{label}: {line(values.get('title',row['number']))}\n"+line(values.get('counterparty','Контрагент не подтверждён'))
            block+='\n'+line(values.get('work_address','Место работ требует уточнения'))
            block+='\nБюджет: '+line(values.get('price','Требует уточнения'),30)+' '+line(values.get('currency',''),10)
            block+='; срок: '+line(values.get('deadline','Требует уточнения'),40)
            block+='\nОплата: '+line(values.get('payment','Требует уточнения'),50)
            if row['risks']:block+='; риск: '+line(row['risks'][0],100)
            if row['links']:block+='\n'+line(row['links'][0],350)
            if len('\n'.join(lines)+block+suffix)+100>max_chars:continue
            lines.append(block);shown+=1
    lines.append(f'В превью {shown} из {total} находок; исключено {len(sections.get("excluded",[]))}.')
    if not total:lines.append('Подходящие заказы не подтверждены. Неполный доступ не доказывает их отсутствие.')
    text='\n'.join(lines)+suffix
    if len(text)>max_chars:raise ValueError('commercial_preview_size_limit')
    return text
