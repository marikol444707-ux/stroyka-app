"""Read-only procurement attachment inventory; no URLs or business contents in output."""
import hashlib
import json
import re
from collections import Counter

SOURCES = {
    'supplier_offers': ('pdf_url',),
    'supplier_invoices': ('file_url', 'photo_url'),
    'supply_deliveries': ('document_url', 'photo_url'),
    'warehouse_invoices': ('photo_url', 'photo_urls'),
}


def attachments(row, fields):
    urls, malformed = [], 0
    for field in fields:
        value = row.get(field)
        if not value:
            continue
        if field == 'photo_urls':
            try:
                value = json.loads(value) if isinstance(value, str) else value
                if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                    raise ValueError('Expected string array')
                urls.extend(v.strip() for v in value if v.strip())
            except (ValueError, TypeError):
                malformed += 1
        elif isinstance(value, str):
            urls.append(value.strip())
        else:
            malformed += 1
    return list(dict.fromkeys(u for u in urls if u)), malformed


def inventory(cur):
    cur.execute('SELECT id,company_id,file_url,COALESCE(deletion_status,\'active\') FROM file_ownership')
    files = {}
    for file_id, owner, legacy, state in cur.fetchall():
        for key in (f'/tenant-files/{file_id}/content', legacy):
            if key:
                files.setdefault(key, []).append((file_id, owner, state))
    result = {}
    rows_by_table = {}
    for table, fields in SOURCES.items():
        cur.execute(f'SELECT to_jsonb(d)::text FROM {table} d ORDER BY id')
        digest, owners, counts = hashlib.sha256(), Counter(), Counter()
        rows = []
        for (encoded,) in cur:
            digest.update((encoded + '\n').encode('utf-8'))
            row = json.loads(encoded)
            rows.append(row)
            owners[row.get('company_id')] += 1
            urls, malformed = attachments(row, fields)
            counts['malformedAttachmentFields'] += malformed
            counts['withoutAttachments'] += not urls
            counts['uniqueReferencesWithinRecords'] += len(urls)
            for url in urls:
                matches = files.get(url, [])
                # Exact original URL matching is evidence, never permission to publish it.
                identities = {m[0] for m in matches}
                if len(identities) != 1:
                    counts['unresolvedOrAmbiguous'] += 1
                    continue
                _, owner, state = matches[0]
                counts['protectedReferences' if re.fullmatch(r'/tenant-files/[1-9][0-9]*/content', url) else 'legacyReferencesToReplace'] += 1
                counts['ownerMismatch'] += row.get('company_id') is None or row.get('company_id') != owner
                counts['inactiveFiles'] += state != 'active'
        rows_by_table[table] = {row['id']: row for row in rows}
        result[table] = {'count': len(rows), 'sha256': digest.hexdigest(),
                         'owners': [{'companyId': k, 'count': v} for k, v in owners.items()], **dict(counts)}
    links = (('supplier_invoices', 'offer_id', 'supplier_offers'),
             ('supply_deliveries', 'offer_id', 'supplier_offers'),
             ('warehouse_invoices', 'supply_delivery_id', 'supply_deliveries'),
             ('warehouse_invoices', 'supplier_invoice_id', 'supplier_invoices'))
    for source, column, target in links:
        stats = Counter()
        for row in rows_by_table[source].values():
            target_id = row.get(column)
            if not target_id:
                stats['unlinked'] += 1
                continue
            parent = rows_by_table[target].get(target_id)
            stats['linked'] += 1
            if not parent or row.get('company_id') is None or parent.get('company_id') != row['company_id']:
                stats['missingOrForeignParent'] += 1
        result[source].setdefault('links', {})[column] = dict(stats)
    return result


if __name__ == '__main__':
    import psycopg2
    from backend.db import DB_CONFIG
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    try:
        with conn, conn.cursor() as cursor:
            print(json.dumps(inventory(cursor), ensure_ascii=False, indent=2))
    finally:
        conn.close()
