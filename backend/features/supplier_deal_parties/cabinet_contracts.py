"""Read-only addressed contracts; never exposes the buyer's general archive."""
from typing import Annotated, Optional
import psycopg2.extras
from fastapi import Depends, HTTPException, Query, Response
from ..supplier_access.service import supplier_offer_visibility_filter
from ..supplier_team import policy
from .publication import supplier_version_visible


def register_cabinet_contracts(app, deps):
    @app.get('/supplier-cabinet/contracts')
    def listing(response: Response, before: Annotated[Optional[int], Query(gt=0)] = None,
                user: dict = Depends(deps['get_current_user'])):
        response.headers['Cache-Control'] = 'private, no-store'
        if user.get('role') != 'поставщик':
            raise HTTPException(403, 'Раздел доступен поставщику')
        conn = deps['get_db']()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            ids = deps['current_supplier_ids'](cur, user)
            if not ids:
                return {'items': [], 'nextCursor': None}
            offer_scope, offer_params = supplier_offer_visibility_filter(ids, user.get('id'))
            if policy.enabled():
                standalone_scope, standalone_params = (
                    policy.offer_policy(user.get('id'), 'team_offer') if policy.customer_assignments_enabled()
                    else policy.leader_policy(user.get('id'), 's.id'))
            else:
                standalone_scope, standalone_params = 'TRUE', []
            cur.execute('''WITH visible AS (SELECT v.id,v.company_id,v.source_file_id,v.version,v.snapshot_json,
                    COALESCE(r.archived,FALSE) AS archived, r.id AS registry_id
                FROM supplier_contract_versions v
                JOIN file_ownership f ON f.id=v.source_file_id AND f.company_id=v.company_id
                    AND COALESCE(f.deletion_status,'active')='active'
                LEFT JOIN supplier_contract_registry_versions m ON m.contract_version_id=v.id AND m.company_id=v.company_id
                LEFT JOIN supplier_contract_registry r ON r.id=m.registry_id AND r.company_id=m.company_id
                WHERE (
                    EXISTS (SELECT 1 FROM supplier_offers
                        WHERE supplier_offers.id=v.offer_id AND supplier_offers.company_id=v.company_id
                        AND ''' + supplier_version_visible('v') + offer_scope + ''')
                    OR (v.offer_id IS NULL AND f.project_id IS NULL AND EXISTS (
                        SELECT 1 FROM supplier_contract_registry team_offer
                        JOIN suppliers s ON s.id=team_offer.supplier_id
                        WHERE team_offer.id=r.id AND team_offer.company_id=v.company_id
                            AND s.id=ANY(%s) AND v.snapshot_json #>> '{supplier,supplierId}'=s.id::text
                            AND ''' + standalone_scope + ''')))
                ), latest AS (SELECT DISTINCT ON (COALESCE('r'||registry_id::text,'v'||id::text)) *
                    FROM visible ORDER BY COALESCE('r'||registry_id::text,'v'||id::text),id DESC)
                SELECT * FROM latest WHERE (%s::bigint IS NULL OR id<%s) ORDER BY id DESC LIMIT 51''',
                offer_params + [ids] + standalone_params + [before, before])
            rows = cur.fetchall()
            items = []
            for row in rows[:50]:
                snapshot = row['snapshot_json']
                # Return only the addressed document summary, not internal provenance/review data.
                items.append({'id': row['id'], 'companyId': row['company_id'],
                    'customer': snapshot.get('buyer', {}).get('fullName') or 'Заказчик',
                    'number': snapshot.get('number', ''), 'date': snapshot.get('date', ''),
                    'version': row['version'], 'archived': row['archived'],
                    'fileUrl': f"/tenant-files/{row['source_file_id']}/content",
                    'addenda': [{'number': a.get('number', ''), 'date': a.get('date', ''),
                        'fileUrl': f"/tenant-files/{a['sourceFileId']}/content"}
                        for a in snapshot.get('addenda', [])]})
            return {'items': items, 'nextCursor': rows[49]['id'] if len(rows)>50 else None}
        finally:
            cur.close()
            conn.close()
