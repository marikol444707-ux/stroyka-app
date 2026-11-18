"""Common stored identity evidence for the audit and exact contract selection."""

REFERENCE_EVIDENCE_SQL = """SELECT bc.id,bc.company_id,bc.project_id,bc.contractor_id,bc.status,
            bc.party_snapshot_json,bc.party_snapshot_hash,p.company_id AS project_company_id,
            u.id AS user_id,u.active AS user_active,s.id AS staff_id,
            ARRAY(SELECT m.id FROM user_company_roles m
                WHERE m.user_id=u.id AND m.company_id=bc.company_id AND m.active IS TRUE
                ORDER BY m.id) AS membership_ids,
            ARRAY(SELECT DISTINCT m.role FROM user_company_roles m
                WHERE m.user_id=u.id AND m.company_id=bc.company_id AND m.active IS TRUE
                ORDER BY m.role) AS membership_roles,
            ARRAY(SELECT DISTINCT m.user_id FROM user_company_roles m
                WHERE m.staff_id=s.id AND m.company_id=bc.company_id AND m.active IS TRUE
                ORDER BY m.user_id) AS staff_user_ids
        FROM brigade_contracts bc
        LEFT JOIN projects p ON p.id=bc.project_id
        LEFT JOIN users u ON u.id=bc.contractor_id
        LEFT JOIN staff s ON s.id=bc.contractor_id AND s.company_id=bc.company_id
"""
