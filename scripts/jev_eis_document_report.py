"""Evidence-first reports; sources and deterministic checks remain authoritative."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
try:
    from scripts.jev_eis_document_formats import extract
except ImportError:
    from jev_eis_document_formats import extract

CATEGORIES={
 'scope':('Что выполнить',r'предмет.{0,40}контракт|подрядчик обязуется|состав работ|описание объекта'),
 'schedule':('Сроки работ',r'срок.{0,50}выполн|календарных дней|окончание работ|начало работ'),
 'payment':('Оплата',r'опла[тч].{0,100}(дн|после|прием|приём|срок)|безналичн'),
 'advance':('Аванс',r'аванс|предоплат'),
 'warranty':('Гарантия',r'гарантийн.{0,50}(срок|обяз|лет|месяц)'),
 'security':('Обеспечения',r'обеспечени.{0,60}(заявк|контракт|гарантийн)'),
 'penalties':('Штрафы и пени',r'штраф|неустойк|пеня|пени'),
 'qualification':('Требования к участнику',r'членств.{0,30}(сро|саморег)|членом.{0,80}саморегулируем|\bСРО\b|лицензи|опыт.{0,50}(работ|контракт)|требования к участникам'),
}


def validate_findings(payload,evidence):
    known={x['id']:x for x in evidence};accepted=[];rejected=0
    if not isinstance(payload,dict) or not isinstance(payload.get('findings'),list):raise ValueError('Invalid review schema')
    for finding in payload['findings'][:20]:
        refs=finding.get('evidence',[]) if isinstance(finding,dict) else []
        if (not isinstance(finding,dict) or finding.get('category') not in CATEGORIES
            or not isinstance(finding.get('summary'),str) or not 1<=len(finding['summary'])<=1000
            or not isinstance(refs,list) or not 1<=len(refs)<=8):rejected+=1;continue
        valid=all(isinstance(ref,dict) and ref.get('id') in known and isinstance(ref.get('quote'),str)
                  and 10<=len(ref['quote'])<=1000 and ref['quote'] in known[ref['id']]['text']
                  and known[ref['id']]['category']==finding['category'] for ref in refs)
        if valid:
            quoted=' '.join(ref['quote'] for ref in refs)
            valid=set(re.findall(r'\d+(?:[.,]\d+)*',finding['summary']))<=set(re.findall(r'\d+(?:[.,]\d+)*',quoted))
        if not valid:rejected+=1;continue
        accepted.append({'category':finding['category'],'summary':finding['summary'],'evidence':refs,'status':'ai_requires_review'})
    return {'findings':accepted,'rejected':rejected}


def select_evidence(units,document_id):
    selected=[]
    for category,(_,pattern) in CATEGORIES.items():
        matching=[]
        for unit in units:
            text=unit['text']
            if unit.get('ocr') or not re.search(pattern,text,re.I):continue
            if category=='qualification' and re.search(r'лиценз.{0,100}банк|банк.{0,100}лиценз|банковск',text,re.I):continue
            if category=='payment' and re.search(r'субподряд|соисполнител|обеспечени|оплат.{0,20}труда|накладн.{0,20}расход',text,re.I):continue
            score=bool(re.search(r'составляет|размер|окончание работ|начало работ|лет|процент|саморегулируем',text,re.I))+bool(re.search(r'\d',text))
            matching.append((score,unit))
        for _,unit in sorted(matching,key=lambda x:-x[0])[:4]:
            selected.append({'id':unit['id']+':'+category,'category':category,'source':document_id,'locator':unit['locator'],'text':unit['text'][:2200],'ocr':False})
    return selected


def card_facts(text):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    facts={}
    for key,label in [('object','Объект закупки'),('price','Начальная цена'),('application_deadline','Дата и время окончания срока подачи заявок')]:
        try:facts[key]=lines[lines.index(label)+1]
        except (ValueError,IndexError):facts[key]='не извлечено'
    return facts


def review(snapshot):
    snapshot=Path(snapshot);manifest=json.loads((snapshot/'manifest.json').read_text())
    result={'notice_number':manifest['notice_number'],'notice_url':manifest['notice_url'],
            'retrieved_at':manifest['retrieved_at'],'snapshot_consistent':manifest['snapshot_consistent'],
            'revision_label':manifest['revision_label'],'card':card_facts(manifest.get('card_text','')),'documents':[],'evidence':[],
            'issues':list(manifest['issues']),'findings':[],'ai_status':'not_run',
            'company_eligibility':'не проверено: профиль компании не предоставлен',
            'estimate_complete_check':False,'notices':[]}
    result['evidence'].append({'id':'card:scope','category':'scope','source':'card','locator':'объект закупки','text':result['card']['object'],'ocr':False})
    audits=[]
    for document in manifest['documents']:
        record=dict(document)
        if document['status']=='downloaded':
            try:
                rel=Path(document['path'])
                if rel.is_absolute() or '..' in rel.parts or rel.parts[0]!='originals':raise ValueError('Unsafe original path')
                path=snapshot/rel
                if hashlib.sha256(path.read_bytes()).hexdigest()!=document['sha256']:raise ValueError('Original checksum mismatch')
                extracted=extract(path,document['id'],assets=snapshot/'previews');record.update(extracted)
                result['evidence'].extend(select_evidence(extracted['units'],document['id']))
                result['notices'].extend(extracted['notices'])
                audits.extend({'source':document['id'],**x} for x in extracted['formula_audit'])
                result['issues'].extend(document['name']+': '+issue for issue in extracted['issues'])
            except Exception as exc:
                record.update(status='read_failed',error_type=type(exc).__name__)
                result['issues'].append(document['name']+': '+type(exc).__name__)
        result['documents'].append(record)
    result['notices']=list(dict.fromkeys(result['notices']))
    result['formula_audit']=audits
    result['formula_counts']=dict(Counter(x['status'] for x in audits))
    result['complete_text_extraction']=bool(result['documents']) and all(x.get('status')=='read' for x in result['documents'])
    result['overall_status']='sources_ready' if result['complete_text_extraction'] and result['snapshot_consistent'] else 'partial'
    (snapshot/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    render(snapshot,result)
    return result


def render(snapshot,report):
    snapshot=Path(snapshot);docs={x['id']:x for x in report['documents']};docs['card']={'name':'Карточка ЕИС','url':report['notice_url']};evidence={x['id']:x for x in report['evidence']}
    escape=html.escape
    title='Разбор закупки № '+report['notice_number']
    md=['# '+title,'','Снимок оригиналов: '+report['retrieved_at'],
        '','**Это предварительный разбор. Допуск компании к участию и полная проверка сметы не выполнены.**','',
        '[Карточка ЕИС]('+report['notice_url']+')','','## Файлы','']
    card=report.get('card',{})
    md+=['','**Работы:** '+card.get('object','не извлечено'),'','**Начальная цена:** '+card.get('price','не извлечено'),'','**Подача заявки до:** '+card.get('application_deadline','не извлечено'),'']
    blocks=['<h1>'+escape(title)+'</h1><p>Снимок: '+escape(report['retrieved_at'])+'</p>',
            '<p class="notice">Предварительный разбор. Допуск компании к участию и полная проверка сметы не выполнены.</p>',
            '<p><a href="'+escape(report['notice_url'],quote=True)+'">Карточка ЕИС</a></p>']
    blocks.append('<article><h2>'+escape(card.get('object','Описание работ не извлечено'))+'</h2><p>Начальная цена: '+escape(card.get('price','не извлечено'))+'<br>Подача заявки до: '+escape(card.get('application_deadline','не извлечено'))+'</p></article>')
    blocks.append('<details><summary>Документы · '+str(len(report['documents']))+'</summary>')
    for doc in report['documents']:
        state={'read':'Прочитан','partial':'Прочитан частично','read_failed':'Не удалось прочитать','download_failed':'Не удалось скачать'}.get(doc.get('status'),doc.get('status','не прочитан'));original=doc.get('path')
        md.append('- '+doc['name']+' — '+state+'; SHA-256: `'+doc.get('sha256','нет')+'`. [ЕИС]('+doc['url']+')')
        blocks.append('<article><strong>'+escape(doc['name'])+'</strong><p>'+escape(state)+' · '+str(doc.get('bytes',0))+' байт</p><a href="'+escape(doc['url'],quote=True)+'">Открыть в ЕИС</a>'+((' · <a href="'+escape(original,quote=True)+'">Сохранённый оригинал</a>') if original else '')+'</article>')
    blocks.append('</details>')
    downloaded=sum(d.get('path') is not None for d in report['documents'])
    members=[m for d in report['documents'] for m in d.get('members',[])]
    failed=sum(m['status']=='read_failed' or not m['text_units'] for m in members)
    partial=sum(m['status']=='partial' and bool(m['text_units']) for m in members)
    coverage='Оригиналы: '+str(downloaded)+'/'+str(len(report['documents']))+'. Файлы в архивах: '+str(len(members))+'. Частично: '+str(partial)+'. Не удалось разобрать: '+str(failed)+'.'
    blocks.append('<article><strong>Полнота разбора</strong><p>'+escape(coverage)+'</p><p>Чтение файлов не подтверждает правильность расчётов и возможность участия.</p></article>')
    md+=['',coverage,'','## Краткий разбор','']
    blocks.append('<h2>Краткий разбор</h2>')
    if report.get('ai_status')!='grounded':
        md.append('ИИ-разбор не выполнен. Ниже — найденные фрагменты условий с источниками.')
        blocks.append('<p>ИИ-разбор не выполнен. Ниже приведены фрагменты условий с источниками.</p>')
    for finding in report['findings']:
        label=CATEGORIES[finding['category']][0]
        md+=['### '+label,'',finding['summary'],'']
        refs=[]
        for ref in finding['evidence']:
            unit=evidence[ref['id']];doc=docs[unit['source']]
            md.append('> '+ref['quote'].replace('\n',' ')+' — '+doc['name']+', '+unit['locator'])
            refs.append('<blockquote>'+escape(ref['quote'])+'<footer>'+escape(doc['name']+' · '+unit['locator'])+'</footer></blockquote>')
        blocks.append('<article><h3>'+escape(label)+'</h3><p>'+escape(finding['summary'])+'</p>'+''.join(refs)+'</article>')
    categories_found={f['category'] for f in report['findings']}
    for category,(label,_) in CATEGORIES.items():
        if category not in categories_found:
            missing=label+': условие не установлено по извлечённым фрагментам. Проверьте оригиналы.'
            blocks.append('<p class="notice">'+escape(missing)+'</p>');md+=['',missing]
    blocks.append('<h2>Что требует проверки</h2>')
    counts=report['formula_counts']
    formula_note=('Проверены простые формулы: '+str(counts.get('matched',0))+'. Остались без проверки: '+str(sum(v for k,v in counts.items() if k not in {'matched','mismatch'}))+'. Расхождения: '+str(counts.get('mismatch',0))+'.') if counts else 'Формулы для пересчёта не найдены.'
    notes=[report['company_eligibility'],'Проверка сметы: полная экспертиза не выполнена. '+formula_note]
    notes+=list(dict.fromkeys(report['issues']))
    notes+=report.get('notices',[])
    if not report['snapshot_consistent']:notes.append('Редакция изменилась во время чтения — повторите сбор документов.')
    md+=['','## Что требует проверки','']+['- '+x for x in notes]
    blocks.append('<details><summary>Ограничения и замечания · '+str(len(notes))+'</summary>'+''.join('<p class="notice">'+escape(x)+'</p>' for x in notes)+'</details>')
    visuals=[v for d in report['documents'] for v in d.get('visuals',[])]
    if visuals:
        blocks.append('<h2>Изображения для сверки</h2><p>OCR не подтверждает правильность формулы, цифр и расчётов. Сверьте изображение с оригиналом.</p>')
        md+=['','## Изображения для сверки','','OCR не подтверждает правильность формул и цифр.']
        for visual in visuals:
            path=visual.get('path');source=visual['source']+' · '+visual['locator']
            if path and re.fullmatch(r'previews/[a-f0-9]{64}\.png',path):
                blocks.append('<details><summary>'+escape(source)+'</summary><a href="'+path+'"><img loading="lazy" src="'+path+'" alt="Изображение из документа"></a><p>'+escape(visual.get('text','') or 'Текст не распознан. Сверьте изображение.')+'</p></details>')
                md+=['','['+source+']('+path+') — требует сверки']

    md+=['','## Фрагменты оригиналов','']
    blocks.append('<h2>Фрагменты оригиналов</h2>')
    for key,(label,_) in CATEGORIES.items():
        matching=[x for x in report['evidence'] if x['category']==key]
        if not matching:continue
        md+=['### '+label,'']
        inner=[]
        for unit in matching:
            doc=docs[unit['source']];tag=' · OCR, требует сверки' if unit['ocr'] else ''
            md+=['**'+doc['name']+' · '+unit['locator']+tag+'**','',unit['text'],'']
            inner.append('<article><strong>'+escape(doc['name']+' · '+unit['locator']+tag)+'</strong><p>'+escape(unit['text']).replace('\n','<br>')+'</p></article>')
        blocks.append('<details><summary>'+escape(label)+' · '+str(len(matching))+' фрагментов</summary>'+''.join(inner)+'</details>')
    (snapshot/'report.md').write_text('\n'.join(md))
    style='body{margin:0;background:#f4f5f7;color:#202830;font:16px/1.6 system-ui,sans-serif}main{max-width:900px;margin:auto;padding:24px}h1{font-size:clamp(23px,5vw,34px)}h2{margin-top:32px}article>h2{font-size:20px;line-height:1.4;margin:0 0 12px}article,details{background:white;border:1px solid #e0e4e8;border-radius:14px;padding:18px;margin:12px 0;overflow-wrap:anywhere}a{color:#b74b00}blockquote{border-left:3px solid #ed8a35;padding-left:14px;margin:12px 0}footer{color:#66727d;font-size:13px}.notice{background:#fff3dd;padding:14px;border-radius:12px}summary{cursor:pointer;font-weight:650}p{white-space:pre-wrap}img{max-width:100%;height:auto;background:white} @media(max-width:600px){main{padding:14px}article{padding:14px}}'
    (snapshot/'report.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src \'self\' data:"><title>'+escape(title)+'</title><style>'+style+'</style><main>'+''.join(blocks)+'</main></html>')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('snapshot');parser.add_argument('--apply-model',action='store_true');args=parser.parse_args()
    if args.apply_model:
        root=Path(args.snapshot);result=json.loads((root/'review.json').read_text());response=json.loads((root/'model-response.json').read_text())
        if response.get('ok'):
            validated=validate_findings(response.get('review'),result['evidence']);result['findings']=validated['findings']
            result['ai_status']='grounded' if result['findings'] else 'partial'
            result['ai_rejected_findings']=validated['rejected']
            if validated['rejected']:result['issues'].append('Отклонены неподтверждённые выводы ИИ: '+str(validated['rejected']))
        else:
            result['ai_status']='unavailable';result['issues'].append('ИИ-разбор недоступен; исходные фрагменты сохранены')
        result['overall_status']='review_ready' if result['complete_text_extraction'] and result['snapshot_consistent'] and result['ai_status']=='grounded' else 'partial'
        (root/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));render(root,result)
    else:result=review(args.snapshot)
    print(json.dumps({'status':result['overall_status'],'documents':len(result['documents']),'evidence':len(result['evidence']),'formulas':result['formula_counts'],'issues':result['issues']},ensure_ascii=False))
