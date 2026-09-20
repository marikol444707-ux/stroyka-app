"""Explicit, operator-approved legacy document ownership assignment.

The caller controls the transaction and supplies the exact approved IDs.
Never run this automatically by matching project names.
"""


def assign_confirmed_documents(cur, *, company_id, project_id, project_name, document_ids):
    ids = list(document_ids)
    if (type(company_id) is not int or company_id <= 0
            or type(project_id) is not int or project_id <= 0
            or not isinstance(project_name, str) or not project_name.strip()
            or not ids or any(type(value) is not int or value <= 0 for value in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('Exact company, project and distinct document IDs required')
    cur.execute('SELECT company_id,name FROM projects WHERE id=%s FOR UPDATE', (project_id,))
    if cur.fetchone() != (company_id, project_name):
        raise ValueError('Approved project identity changed')
    cur.execute('SELECT id,project_name,company_id,project_id FROM project_documents '
                'WHERE id=ANY(%s) ORDER BY id FOR UPDATE', (sorted(ids),))
    rows = cur.fetchall()
    if {row[0] for row in rows} != set(ids):
        raise ValueError('Approved document set changed')
    for _, name, stored_company, stored_project in rows:
        if name != project_name or (stored_company, stored_project) not in (
                (None, None), (company_id, project_id)):
            raise ValueError('Document identity or existing owner conflicts with approval')
    cur.execute('UPDATE project_documents SET company_id=%s,project_id=%s '
                'WHERE id=ANY(%s) AND company_id IS NULL AND project_id IS NULL',
                (company_id, project_id, sorted(ids)))
    return len(rows)
