"""Authorized, latest reviewed originals offered for a new contract draft."""
from fastapi import HTTPException
from .contract_applicability import eligible_applicability


def reusable_contracts(cur, offer, identities, load_offer, user, header_id, header_mode, project_id=None):
    cur.execute('''SELECT c.* FROM supplier_contract_versions c
        JOIN supplier_offers o ON o.id=c.offer_id AND o.company_id=c.company_id
        JOIN file_ownership f ON f.id=c.source_file_id AND f.company_id=c.company_id
        WHERE c.company_id=%s AND o.supplier_id=%s AND c.offer_id<>%s
          AND COALESCE(f.deletion_status,'active')='active'
          AND (f.project_id IS NULL OR f.project_id=%s)
          AND NOT EXISTS (SELECT 1 FROM supplier_contract_versions newer
                          WHERE newer.offer_id=c.offer_id AND newer.version>c.version)
        ORDER BY c.reviewed_at DESC,c.id DESC LIMIT 100''',
        (offer['company_id'], offer['supplier_id'], offer['id'], project_id))
    rows = cur.fetchall()
    result = []
    seen = set()
    for row in rows:
        snapshot = row['snapshot_json']
        # Payment schedules belong to the original deal; never silently copy or drop them.
        if snapshot.get('paymentSchedule') or not eligible_applicability(snapshot, project_id):
            continue
        if any(snapshot.get(side, {}).get(key) != identities[side].get(key)
               for side, key in (('buyer','companyId'), ('payer','companyId'),
                                 ('supplier','supplierId'), ('buyer','inn'),
                                 ('payer','inn'), ('supplier','inn'))):
            continue
        try:
            load_offer(cur, row['offer_id'], user, 'read', header_id, header_mode)
        except HTTPException as error:
            if error.status_code in (403, 404):
                continue
            raise
        key = (row['source_file_id'], row['snapshot_hash'])
        if key in seen:
            continue
        seen.add(key)
        result.append({'id': row['id'], 'offerId': row['offer_id'],
                       'companyId': row['company_id'], 'version': row['version'],
                       'sourceFileId': row['source_file_id'], 'snapshot': snapshot})
    return result
