"""Read-only inventory; output contains counts and hashes, never file contents."""
import hashlib
import json

SOURCES = (
    ('company_documents', 'file_url'),
    ('supplier_documents', 'file_url'),
    ('project_documents', 'scan_url'),
    ('supplier_contract_versions', None),
)


def inventory(cur):
    report = {}
    for table, file_column in SOURCES:
        # Identifiers are from the fixed allowlist above, never caller input.
        cur.execute(f'SELECT to_jsonb(d)::text FROM {table} d ORDER BY id')
        digest = hashlib.sha256()
        count = 0
        for (encoded,) in cur:
            digest.update(encoded.encode('utf-8'))
            digest.update(b'\n')
            count += 1
        cur.execute(f'SELECT company_id,count(*) FROM {table} GROUP BY company_id ORDER BY company_id NULLS LAST')
        owners = [{'companyId': row[0], 'count': row[1]} for row in cur.fetchall()]
        reference = (f"d.{file_column}='/tenant-files/' || f.id || '/content'"
                     if file_column else 'd.source_file_id=f.id')
        missing = f"COALESCE(d.{file_column},'')=''" if file_column else 'd.source_file_id IS NULL'
        cur.execute(f"""SELECT
            count(*) FILTER (WHERE {missing}),
            count(*) FILTER (WHERE NOT ({missing}) AND f.id IS NULL),
            count(*) FILTER (WHERE f.id IS NOT NULL AND
                (d.company_id IS NULL OR f.company_id IS DISTINCT FROM d.company_id)),
            count(*) FILTER (WHERE f.id IS NOT NULL AND
                COALESCE(f.deletion_status,'active')<>'active')
            FROM {table} d LEFT JOIN file_ownership f ON {reference}""")
        empty, unresolved, conflict, inactive = cur.fetchone()
        report[table] = {'count': count, 'sha256': digest.hexdigest(), 'owners': owners,
                         'withoutFile': empty, 'unresolvedFileReference': unresolved,
                         'ownerNeedsReview': conflict, 'inactiveFile': inactive}
    return report


def main():
    import psycopg2
    from backend.db import DB_CONFIG
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    try:
        with conn, conn.cursor() as cur:
            print(json.dumps(inventory(cur), ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
