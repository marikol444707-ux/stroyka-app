"""Private, deterministic Telegram digest. No model calls or network access."""
import argparse
import hashlib
import html
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

try:
    from .jev_telegram_details import describe, is_vacancy
except ImportError:
    from jev_telegram_details import describe, is_vacancy

TOPIC_LABEL = 'Отделка, ремонт и строительство домов'
TOPIC = re.compile(
    r'отдел|ремонт|маляр|штукатур|шпакл|плиточ|покле|обои|стяжк|гипсокартон|'
    r'(?:строительств|постро|строим|строить).{0,40}(?:\bдом|коттедж)|'
    r'фундамент|кладк|каменщик|кров(?:л|ель)|крыш|каркасн|газобетон|\bижс\b|'
    r'монтаж\w*.{0,35}лес\w*|'
    r'перекрыт|электри|электромонтаж|проводк|сантех|отоплен|водоснабж|канализац|'
    r'строител(?!ьств)|бригад.{0,20}объект', re.I)
DEMAND = re.compile(r'нуж(?:ен|на|ны|но)|требу(?:ется|ются)|ищ(?:у|ем)|кто\s+(?:может|сможет)', re.I)
SERVICES = re.compile(
    r'выполня[ею]|оказыва|предлага[ею]|ищ[уе]м?\s+(?:заказ|работ)|'
    r'требуется\s+работа|ищу\s+работу|'
    r'\b(?:строим|построим)\s+(?:дома\b|коттеджи\b|ваш\s+дом)', re.I)
MATERIALS = re.compile(r'прод(?:ам|аем|аю)|в\s+продаже', re.I)


def classify(text):
    text = unicodedata.normalize('NFKC', text).casefold().replace('ё', 'е')
    if not TOPIC.search(text): return 'irrelevant'
    if SERVICES.search(text):
        if is_vacancy(text) and not re.search(r'ищу\s+работу|ищем\s+работу|требуется\s+работа', text):
            return 'review'
        return 'services'
    if MATERIALS.search(text): return 'materials'
    if is_vacancy(text): return 'vacancy'
    if DEMAND.search(text): return 'order'
    return 'review'


def fingerprint(text):
    normalized = ' '.join(unicodedata.normalize('NFKC', text).casefold().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def source_url(source, message_id):
    if not isinstance(message_id, int) or isinstance(message_id, bool) or message_id <= 0:
        raise ValueError('Invalid message id')
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}', str(source)):
        return 'https://t.me/{}/{}'.format(source, message_id)
    if re.fullmatch(r'-100[1-9][0-9]{2,}', str(source)):
        return 'https://t.me/c/{}/{}'.format(str(source)[4:], message_id)
    raise ValueError('Only Telegram channel usernames or channel IDs are supported')


def export_messages(data, source):
    source_url(source, 1)
    messages = data.get('messages')
    if not isinstance(messages, list) or len(messages) > 100000:
        raise ValueError('Invalid or oversized export')
    result = []
    for row in messages:
        if not isinstance(row, dict): raise ValueError('Invalid message')
        if row.get('type') != 'message': continue
        text = row.get('text', '')
        if isinstance(text, list):
            text = ''.join(part if isinstance(part, str) else str(part.get('text', ''))
                           for part in text if isinstance(part, (str, dict)))
        if not isinstance(text, str) or len(text) > 65536:
            raise ValueError('Invalid message text')
        result.append({'id': row['id'], 'source': source, 'date': row.get('date', ''),
                       'text': text, 'url': source_url(source, row['id'])})
    return result


def digest(messages):
    groups = {}
    counts = {'services': 0, 'materials': 0, 'irrelevant': 0}
    for row in messages:
        category = classify(row['text'])
        if category in counts:
            counts[category] += 1
            continue
        key = fingerprint(row['text'])
        item = groups.setdefault(key, {'text': row['text'], 'category': category, 'originals': [], **describe(row['text'])})
        original = {k: row.get(k, '') for k in ('source', 'id', 'date', 'url')}
        if original not in item['originals']: item['originals'].append(original)
    return {'topic': TOPIC_LABEL, 'orders': [x for x in groups.values() if x['category'] == 'order'],
            'review': [x for x in groups.values() if x['category'] == 'review'],
            'vacancies': [x for x in groups.values() if x['category'] == 'vacancy'], 'excluded': counts}


def render_html(report):
    esc = lambda value: html.escape(str(value), quote=True)
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<title>{} — подборка</title><style>'.format(esc(TOPIC_LABEL)),
             'body{font:16px system-ui;margin:24px auto;padding:0 16px;max-width:850px;color:#202936;background:#f5f7fa}',
             'article{padding:18px;background:white;border:1px solid #dce2e9;border-radius:12px;margin:12px 0}',
             'p{white-space:pre-wrap;overflow-wrap:anywhere}a{display:block;margin:8px 0;color:#155cc2}',
             '.tag{display:inline-block;background:#eaf1fc;color:#264d80;border-radius:16px;padding:4px 10px;margin:6px 5px 6px 0}',
             'dl{display:grid;grid-template-columns:120px minmax(0,1fr);gap:8px;font-size:15px}dt{color:#586778}dd{margin:0;overflow-wrap:anywhere}',
             '@media(max-width:480px){dl{grid-template-columns:1fr;gap:4px}dd{margin-bottom:10px}}',
             '</style><h1>{}</h1>'.format(esc(TOPIC_LABEL)),
             '<p>Подборка по ключевым словам. Актуальность, условия и заказчика проверяйте по оригиналу.</p>']
    if 'retention_days' in report:
        parts.append('<p>Новых заказов: {}. Новых на просмотр: {}. История — {} дней после последнего появления; это не подтверждение актуальности заказа.</p>'.format(
            report['new_orders'], report['new_review'], report['retention_days']))
        parts.append('<p>Новых вакансий: {}.</p>'.format(report.get('new_vacancies', 0)))
    for source in report.get('sources', []):
        if source['status'] != 'ok':
            parts.append('<p>Источник {}: {}</p>'.format(esc(source['label']), esc(source['status'])))
        elif source.get('may_have_more'):
            parts.append('<p>Источник {}: обработана порция, остались сообщения для следующего запуска.</p>'.format(esc(source['label'])))
    for key, title in (('orders', 'Вероятные заказы'), ('vacancies', 'Вакансии'), ('review', 'Нужно посмотреть')):
        items = report.get(key, [])
        parts.append('<h2>{} · {}</h2>'.format(title, len(items)))
        if not items: parts.append('<p>Подходящих сообщений нет.</p>')
        for item in items:
            parts.append('<article>')
            if 'is_new' in item:
                parts.append('<strong>{}</strong>'.format('Новое объявление' if item['is_new'] else 'Уже встречалось'))
            details = describe(item['text'])
            parts.append('<h3>{}</h3>'.format(esc(details['headline'])))
            parts.append('<div>{}</div>'.format(''.join('<span class="tag">{}</span>'.format(esc(tag)) for tag in details['tags'])))
            parts.append('<dl>')
            for field, label in (('place', 'Место в тексте'), ('volume', 'Объём'), ('budget', 'Бюджет / оплата'), ('deadline', 'Срок')):
                value = '; '.join(details['fields'][field]) or 'Не указано явно'
                parts.append('<dt>{}</dt><dd>{}</dd>'.format(label, esc(value)))
            parts.append('</dl><details><summary>Текст объявления</summary><p>{}</p></details>'.format(esc(item['text'])))
            for original in item['originals']:
                label = '{} · {}'.format(original['source'], original['date'])
                url = str(original['url'])
                if re.fullmatch(r'https://t\.me/(?:[A-Za-z][A-Za-z0-9_]{4,31}|c/[1-9][0-9]*)/[1-9][0-9]*', url):
                    parts.append('<a rel="noreferrer" href="{}">{}</a>'.format(esc(url), esc(label)))
                else: parts.append('<p>{}</p>'.format(esc(label)))
            parts.append('</article>')
    parts.append('<p>Отсеяно: реклама услуг — {}; продажа — {}; другие темы — {}.</p>'.format(
        report['excluded']['services'], report['excluded']['materials'], report['excluded']['irrelevant']))
    return ''.join(parts) + '</html>'


def private_directory(path):
    path = Path(path).expanduser()
    if path.is_symlink(): raise ValueError('Symlink directory is not permitted')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('Directory must be owned by current user and mode 700')
    return path


def write_private(path, text):
    path = Path(path)
    parent = private_directory(path.parent)
    fd, temporary = tempfile.mkstemp(dir=str(parent), prefix='.telegram-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def load_json(path, limit=32 * 1024 * 1024, private=False):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(str(path), flags), 'rb') as stream:
        import stat
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode): raise ValueError('Regular file required')
        if private and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise ValueError('Private file must be owned by current user and mode 600')
        raw = stream.read(limit + 1)
        if len(raw) > limit: raise ValueError('Input too large')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', required=True, help='Telegram Desktop JSON export')
    parser.add_argument('--source', required=True, help='Exact username or -100 channel ID')
    parser.add_argument('--output', required=True, help='Private directory outside repository')
    args = parser.parse_args()
    report = digest(export_messages(load_json(args.export), args.source))
    output = private_directory(args.output)
    try:
        from .jev_telegram_history import save_batch
    except ImportError:
        from jev_telegram_history import save_batch
    print(json.dumps(save_batch(output, report, {}), ensure_ascii=False))


if __name__ == '__main__': main()
