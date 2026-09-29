"""Explicit read grant for the source of a saved, visible supplier contract."""
from .service import supplier_offer_visibility_filter
from ..supplier_deal_parties.publication import supplier_version_visible


def supplier_contract_file_visible(cur, user, row, supplier_ids):
    scope, params = supplier_offer_visibility_filter(supplier_ids, user.get('id'))
    cur.execute('''SELECT supplier_offers.id FROM supplier_offers
        WHERE supplier_offers.company_id=%s
          AND EXISTS (
              SELECT 1 FROM supplier_contract_versions v
              WHERE v.offer_id=supplier_offers.id
                AND v.company_id=supplier_offers.company_id
                AND (v.source_file_id=%s OR EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(v.snapshot_json->'addenda','[]'::jsonb)) a WHERE a->>'sourceFileId'=%s))
                AND ''' + supplier_version_visible('v') + '''
          )
          AND (%s::int IS NULL OR EXISTS (
              SELECT 1 FROM supply_requests r JOIN projects p
                ON p.company_id=r.company_id AND p.name=r.project
              WHERE r.id=supplier_offers.request_id AND r.company_id=supplier_offers.company_id
                AND p.id=%s
          ))''' + scope + ' LIMIT 1',
        [row['company_id'], row['id'], str(row['id']), row.get('project_id'), row.get('project_id')] + params)
    return bool(cur.fetchone()) or standalone_contract_file_visible(cur,user,row,supplier_ids)


def standalone_contract_file_visible(cur,user,row,supplier_ids):
    from ..supplier_team import policy
    if not supplier_ids or row.get('project_id'):
        return False
    if policy.enabled():
        if policy.customer_assignments_enabled():
            scope,params=policy.offer_policy(user.get('id'),'team_offer')
        else:
            scope,params=policy.leader_policy(user.get('id'),'s.id')
    else:
        scope,params='TRUE',[]
    cur.execute('''SELECT 1 FROM supplier_contract_registry team_offer
        JOIN suppliers s ON s.id=team_offer.supplier_id
        JOIN supplier_contract_registry_versions m ON m.registry_id=team_offer.id AND m.company_id=team_offer.company_id
        JOIN supplier_contract_versions v ON v.id=m.contract_version_id AND v.company_id=m.company_id
        WHERE v.offer_id IS NULL AND team_offer.company_id=%s AND s.id=ANY(%s)
          AND v.snapshot_json #>> '{supplier,supplierId}'=s.id::text
          AND (v.source_file_id=%s OR EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(v.snapshot_json->'addenda','[]'::jsonb)) a WHERE a->>'sourceFileId'=%s))
          AND '''+scope+' LIMIT 1',[row['company_id'],supplier_ids,row['id'],str(row['id'])]+params)
    return bool(cur.fetchone())
