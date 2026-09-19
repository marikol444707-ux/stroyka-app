"""Company display names for already authorized supplier request rows only."""


def attach_request_company_names(cursor, rows):
    rows = [dict(row) for row in rows]
    ids = sorted({row['companyId'] for row in rows if row.get('companyId')})
    if not ids:
        return rows
    cursor.execute('SELECT id,name FROM companies WHERE id=ANY(%s)', (ids,))
    names = {row['id']: row['name'] for row in cursor.fetchall()}
    return [dict(row, companyName=names.get(row.get('companyId')) or '') for row in rows]
