"""Account-local exact-text history; checkpoint and history commit together."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile

try:
    from .jev_telegram import classify, describe, fingerprint, load_json, private_directory, render_html, write_private
except ImportError:
    from jev_telegram import classify, describe, fingerprint, load_json, private_directory, render_html, write_private

MAX_CARDS = 5000
MAX_ORIGINALS = 50000
RETENTION_DAYS = 30


def database(state):
    path = private_directory(state) / 'history.sqlite3'
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('History must be a private regular file owned by the current user')
    finally:
        os.close(fd)
    connection = sqlite3.connect(str(path), timeout=5)
    connection.execute('PRAGMA foreign_keys=ON')
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS cards (
            fingerprint TEXT PRIMARY KEY, text TEXT NOT NULL, category TEXT NOT NULL,
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS originals (
            fingerprint TEXT NOT NULL REFERENCES cards(fingerprint) ON DELETE CASCADE,
            url TEXT NOT NULL, source TEXT NOT NULL, message_id INTEGER NOT NULL, date TEXT NOT NULL,
            PRIMARY KEY(fingerprint,url));
        CREATE TABLE IF NOT EXISTS cursors (source TEXT PRIMARY KEY, message_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    return connection


def read_cursors(state):
    state = private_directory(state)
    if (state / 'history.sqlite3').exists():
        conn = database(state)
        try:
            if conn.execute("SELECT 1 FROM metadata WHERE key='checkpoint_initialized'").fetchone():
                return dict(conn.execute('SELECT source,message_id FROM cursors'))
        finally:
            conn.close()
    legacy = state / 'cursor.json'
    return load_json(legacy, private=True) if legacy.exists() else {}


def save_batch(state, batch, cursors, now=None):
    """Save report before atomically advancing source positions. Caller serializes collection."""
    state = private_directory(state)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError('Timezone-aware time required')
    stamp = now.astimezone(timezone.utc).isoformat()
    cutoff = (now.astimezone(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    conn, output = database(state), None
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM cards WHERE last_seen < ?', (cutoff,))
        new_keys = set()
        for category, key in (('order', 'orders'), ('review', 'review'), ('vacancy', 'vacancies')):
            for item in batch.get(key, []):
                identity = fingerprint(item['text'])
                exists = conn.execute('SELECT 1 FROM cards WHERE fingerprint=?', (identity,)).fetchone()
                if not exists:
                    new_keys.add(identity)
                    conn.execute('INSERT INTO cards VALUES (?,?,?,?,?)',
                                 (identity, item['text'], category, stamp, stamp))
                else:
                    conn.execute('UPDATE cards SET last_seen=? WHERE fingerprint=?', (stamp, identity))
                for original in item['originals']:
                    conn.execute('INSERT OR IGNORE INTO originals VALUES (?,?,?,?,?)',
                                 (identity, original['url'], original['source'], original['id'], original['date']))
        if conn.execute('SELECT count(*) FROM cards').fetchone()[0] > MAX_CARDS:
            raise ValueError('History card limit reached; checkpoint unchanged')
        if conn.execute('SELECT count(*) FROM originals').fetchone()[0] > MAX_ORIGINALS:
            raise ValueError('History original limit reached; checkpoint unchanged')
        report = dict(batch, orders=[], review=[], vacancies=[], retention_days=RETENTION_DAYS,
                      generated_at=stamp, new_orders=0, new_review=0, new_vacancies=0)
        originals = {}
        for identity, url, source, message_id, date in conn.execute(
                'SELECT fingerprint,url,source,message_id,date FROM originals ORDER BY date,url'):
            originals.setdefault(identity, []).append({'url': url, 'source': source, 'id': message_id, 'date': date})
        for identity, text, category, first, last in conn.execute(
                'SELECT * FROM cards ORDER BY last_seen DESC,first_seen DESC,fingerprint'):
            # Rules may have improved since this card was saved; do not mark it
            # new or move its timestamps merely because its labels changed.
            category = classify(text)
            key = {'order': 'orders', 'review': 'review', 'vacancy': 'vacancies'}.get(category)
            if key is None: continue
            is_new = identity in new_keys
            report[key].append({'text': text, 'category': category, 'is_new': is_new,
                                'first_seen': first, 'last_seen': last, 'originals': originals.get(identity, []), **describe(text)})
            if is_new: report['new_' + key] += 1
        cursor_batches = []
        if not conn.execute("SELECT 1 FROM metadata WHERE key='checkpoint_initialized'").fetchone():
            legacy = state / 'cursor.json'
            if legacy.exists(): cursor_batches.append(load_json(legacy, private=True))
        cursor_batches.append(cursors)
        for positions in cursor_batches:
            if not isinstance(positions, dict): raise ValueError('Invalid checkpoint')
            for source, message_id in positions.items():
                if not isinstance(source, str) or type(message_id) is not int or message_id < 0:
                    raise ValueError('Invalid checkpoint')
                previous = conn.execute('SELECT message_id FROM cursors WHERE source=?', (source,)).fetchone()
                if previous and previous[0] > message_id: raise ValueError('Stale checkpoint')
                conn.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)', (source, message_id))
        conn.execute("INSERT OR REPLACE INTO metadata VALUES ('checkpoint_initialized','1')")
        output = Path(tempfile.mkdtemp(prefix='digest-', dir=str(state)))
        write_private(output / 'report.json', json.dumps(report, ensure_ascii=False, indent=2))
        write_private(output / 'report.html', render_html(report))
        conn.commit()
        return {'ok': batch.get('ok', True), 'status': batch.get('status', 'complete'),
                'report': str(output / 'report.html'), 'json': str(output / 'report.json'),
                'orders': len(report['orders']), 'review': len(report['review']),
                'new_orders': report['new_orders'], 'new_review': report['new_review'],
                'vacancies': len(report['vacancies']), 'new_vacancies': report['new_vacancies'],
                'sources': report.get('sources', [])}
    except BaseException:
        conn.rollback()
        if output is not None: shutil.rmtree(output)
        raise
    finally:
        conn.close()
