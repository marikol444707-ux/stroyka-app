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
 'payment':('Оплата',r'оплат.{0,100}(дн|после|прием|приём|срок)|безналичн'),
 'advance':('Аванс',r'аванс|предоплат'),
 'warranty':('Гарантия',r'гарантийн.{0,50}(срок|обяз|лет|месяц)'),
 'security':('Обеспечения',r'обеспечени.{0,60}(заявк|контракт|гарантийн)'),
 'penalties':('Штрафы и пени',r'штраф|неустойк|пеня|пени'),
 'qualification':('Требования к участнику',r'членств.{0,30}(сро|саморег)|лицензи|опыт.{0,50}(работ|контракт)|требования к участникам'),
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
            'estimate_complete_check':False}
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
                extracted=extract(path,document['id']);record.update(extracted)
                for unit in extracted['units']:
                    for category,(_,pattern) in CATEGORIES.items():
                        match=re.search(pattern,unit['text'],re.I)
                        if not match:continue
                        if category=='qualification' and re.search(r'банк|банковск',unit['text'],re.I):continue
                        if sum(x['category']==category and x['source']==document['id'] for x in result['evidence'])>=4:continue
                        start=max(0,match.start()-100);snippet=unit['text'][start:start+2200]
                        result['evidence'].append({'id':unit['id']+':'+category,'category':category,'source':document['id'],'locator':unit['locator'],'text':snippet,'ocr':unit['ocr']})
                audits.extend({'source':document['id'],**x} for x in extracted['formula_audit'])
                result['issues'].extend(document['name']+': '+issue for issue in extracted['issues'])
            except Exception as exc:
                record.update(status='read_failed',error_type=type(exc).__name__)
                result['issues'].append(document['name']+': '+type(exc).__name__)
        result['documents'].append(record)
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
    md+=['','## Краткий разбор','']
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
    blocks.append('<h2>Что требует проверки</h2>')
    counts=report['formula_counts']
    formula_note=('Проверены простые формулы: '+str(counts.get('matched',0))+'. Остались без проверки: '+str(counts.get('not_checked',0))+'. Расхождения: '+str(counts.get('mismatch',0))+'.') if counts else 'Формулы для пересчёта не найдены.'
    notes=[report['company_eligibility'],'Полная проверка сметы не выполнена. '+formula_note]
    notes+=report['issues']
    if not report['snapshot_consistent']:notes.append('Редакция изменилась во время чтения — повторите сбор документов.')
    md+=['','## Что требует проверки','']+['- '+x for x in notes]
    blocks+=['<p class="notice">'+escape(x)+'</p>' for x in notes]
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
    style='body{margin:0;background:#f4f5f7;color:#202830;font:16px/1.6 system-ui,sans-serif}main{max-width:900px;margin:auto;padding:24px}h1{font-size:clamp(23px,5vw,34px)}h2{margin-top:32px}article>h2{font-size:20px;line-height:1.4;margin:0 0 12px}article,details{background:white;border:1px solid #e0e4e8;border-radius:14px;padding:18px;margin:12px 0;overflow-wrap:anywhere}a{color:#b74b00}blockquote{border-left:3px solid #ed8a35;padding-left:14px;margin:12px 0}footer{color:#66727d;font-size:13px}.notice{background:#fff3dd;padding:14px;border-radius:12px}summary{cursor:pointer;font-weight:650}p{white-space:pre-wrap} @media(max-width:600px){main{padding:14px}article{padding:14px}}'
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
            if validated['rejected']:result['issues'].append('Отклонены выводы ИИ без точной подтверждающей цитаты: '+str(validated['rejected']))
        else:
            result['ai_status']='unavailable';result['issues'].append('ИИ-разбор недоступен; исходные фрагменты сохранены')
        result['overall_status']='review_ready' if result['complete_text_extraction'] and result['snapshot_consistent'] and result['ai_status']=='grounded' else 'partial'
        (root/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));render(root,result)
    else:result=review(args.snapshot)
    print(json.dumps({'status':result['overall_status'],'documents':len(result['documents']),'evidence':len(result['evidence']),'formulas':result['formula_counts'],'issues':result['issues']},ensure_ascii=False))
