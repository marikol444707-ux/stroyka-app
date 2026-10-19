"""Bounded read-only collection from an explicit channel allowlist; no login automation."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path

try:
    from .jev_telegram import digest, load_json, private_directory, render_html, source_url, write_private
except ImportError:
    from jev_telegram import digest, load_json, private_directory, render_html, source_url, write_private


async def collect(client, sources, cursors, limit=100):
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20 or not 1 <= limit <= 200:
        raise ValueError('Configure 1–20 allowed channels and limit 1–200')
    seen = set()
    for source in sources:
        channel = source['id']
        if not isinstance(channel, int) or not str(channel).startswith('-100'):
            raise ValueError('Only numeric group/channel IDs, no personal dialogs')
        source_url(channel, 1)
        if channel in seen: raise ValueError('Duplicate channel')
        seen.add(channel)
        cursor = cursors.get(str(channel), 0)
        if type(cursor) is not int or cursor < 0: raise ValueError('Invalid cursor')
    if not await client.is_user_authorized():
        return {'ok': False, 'status': 'not_authorized'}, dict(cursors)
    rows, statuses, updated = [], [], dict(cursors)
    for source in sources:
        channel = source['id']
        cursor = cursors.get(str(channel), 0)
        kwargs = {'min_id': cursor, 'reverse': True, 'limit': limit}
        if not cursor: kwargs['offset_date'] = datetime.now(timezone.utc) - timedelta(days=7)
        batch, high = [], cursor
        try:
            count = 0
            entity = channel
            if source.get('username'):
                # Resolve only this approved source, then verify the exact ID.
                import re
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}', source['username']):
                    raise ValueError('Invalid source username')
                from telethon import utils
                entity = await client.get_input_entity(source['username'])
                if utils.get_peer_id(entity) != channel:
                    raise ValueError('Source identity changed')
            async for message in client.iter_messages(entity, **kwargs):
                count += 1
                if type(message.id) is not int or message.id <= high:
                    raise ValueError('Unexpected message order')
                high = message.id
                text = message.message or ''
                if len(text) > 65536: raise ValueError('Message too large')
                if text:
                    batch.append({'id': message.id, 'text': text, 'source': source.get('label', str(channel)),
                                  'date': message.date.isoformat() if message.date else '',
                                  'url': source_url(channel, message.id)})
            rows.extend(batch)
            updated[str(channel)] = high
            statuses.append({'label': source.get('label', str(channel)), 'status': 'ok',
                             'read': count, 'may_have_more': count == limit})
        except Exception as exc:
            seconds = getattr(exc, 'seconds', None)
            statuses.append({'label': source.get('label', str(channel)),
                             'status': 'retry_after' if isinstance(seconds, int) else 'source_failed',
                             **({'retry_after': max(1, seconds)} if isinstance(seconds, int) else {})})
            # Retain old cursor and discard incomplete batch; don't skip messages.
    report = digest(rows)
    report.update(ok=all(s['status'] == 'ok' for s in statuses),
                  status='complete' if all(s['status'] == 'ok' for s in statuses) else 'partial', sources=statuses)
    return report, updated


async def run(config_path, state_path):
    config = load_json(config_path, limit=65536, private=True)
    state = private_directory(state_path)
    session = state / 'account.session'
    if not session.is_file() or session.is_symlink() or session.stat().st_mode & 0o077:
        return {'ok': False, 'status': 'not_authorized'}
    if session.stat().st_uid != os.geteuid(): raise ValueError('Session owner mismatch')
    from telethon import TelegramClient
    # No start/sign_in, dialog enumeration, joins, downloads or sends.
    client = TelegramClient(str(session), config['api_id'], config['api_hash'],
                            flood_sleep_threshold=0, request_retries=0,
                            connection_retries=0, timeout=15)
    client.session.save_entities = False
    await client.connect()
    try:
        checkpoint = state / 'cursor.json'
        cursors = load_json(checkpoint, private=True) if checkpoint.exists() else {}
        report, updated = await asyncio.wait_for(collect(client, config['sources'], cursors), timeout=50)
        if report.get('status') == 'not_authorized': return report
        # Immutable run directories preserve previous unviewed batches and make
        # replay safe if writing the checkpoint fails. No duplicate notifications.
        import tempfile
        output = Path(tempfile.mkdtemp(prefix='digest-', dir=str(state)))
        write_private(output / 'report.json', json.dumps(report, ensure_ascii=False, indent=2))
        write_private(output / 'report.html', render_html(report))
        write_private(checkpoint, json.dumps(updated))
        return {'ok': report['ok'], 'status': report['status'], 'report': str(output / 'report.html'),
                'orders': len(report['orders']), 'review': len(report['review']), 'sources': report['sources']}
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--state', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    state = private_directory(args.state)
    fd = os.open(str(state / 'collector.lock'), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return {'ok': False, 'status': 'busy'}
        return asyncio.run(run(args.config, state))


if __name__ == '__main__':
    try: result = main()
    except Exception as exc: result = {'ok': False, 'status': 'collection_failed', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
