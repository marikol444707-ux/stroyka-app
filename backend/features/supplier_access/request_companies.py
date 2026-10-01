"""Frozen requester identity for already authorized supplier request rows."""

from .rfq_requester_snapshot import validate_rfq_requester_snapshot


def attach_requester_identity(cursor, rows):
    rows = [dict(row) for row in rows]
    ids = sorted({row['id'] for row in rows if row.get('id')})
    if not ids:
        return rows
    cursor.execute('''SELECT request.id AS request_id,request.company_id,request.project,
                             request.requester_snapshot_json,company.name
                        FROM supply_requests request
                        JOIN companies company ON company.id=request.company_id
                       WHERE request.id=ANY(%s)''', (ids,))
    identities = {}
    for record in cursor.fetchall():
        identity = {'companyName': record.get('name') or ''}
        if record.get('requester_snapshot_json'):
            snapshot = validate_rfq_requester_snapshot(
                record['requester_snapshot_json'],
                request_id=record['request_id'],
                company_id=record['company_id'],
                project_name=record['project'],
            )
            identity = {
                'companyName': snapshot['companyName'],
                'deliveryAddress': snapshot['deliveryAddress'],
                'contactName': snapshot['contactName'],
                'contactEmail': snapshot['contactEmail'],
                'contactPhone': snapshot['contactPhone'],
            }
        identities[record['request_id']] = identity
    return [dict(row, **identities.get(row.get('id'), {'companyName': ''})) for row in rows]
