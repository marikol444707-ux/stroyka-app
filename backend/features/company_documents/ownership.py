"""Recover archive ownership only from an exact active company-file reference."""


def recover_ownership(cur, *, apply=False):
    cur.execute("""SELECT d.id, f.company_id FROM company_documents d
        JOIN file_ownership f ON d.file_url='/tenant-files/' || f.id || '/content'
        WHERE d.company_id IS NULL AND f.company_id IS NOT NULL
          AND f.project_id IS NULL AND f.context='company-documents'
          AND COALESCE(f.deletion_status,'active')='active'
        ORDER BY d.id""")
    candidates = cur.fetchall()
    updated = []
    if apply:
        for document_id, company_id in candidates:
            cur.execute("""UPDATE company_documents d SET company_id=%s
                WHERE d.id=%s AND d.company_id IS NULL AND EXISTS (
                    SELECT 1 FROM file_ownership f
                    WHERE d.file_url='/tenant-files/' || f.id || '/content'
                      AND f.company_id=%s AND f.project_id IS NULL
                      AND f.context='company-documents'
                      AND COALESCE(f.deletion_status,'active')='active')
                RETURNING d.id""", (company_id, document_id, company_id))
            row = cur.fetchone()
            if row:
                updated.append(row[0])
    return {'candidates': [{'documentId': d, 'companyId': c} for d, c in candidates],
            'updated': updated}
