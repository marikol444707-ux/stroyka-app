def ensure_assignments_schema(get_db):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_task_reports (
                id SERIAL PRIMARY KEY,
                task_id INT NOT NULL,
                report_text TEXT,
                status VARCHAR(100) DEFAULT 'Отчет отправлен',
                author_id INT,
                author_name VARCHAR(255),
                author_role VARCHAR(100),
                owner_scope TEXT,
                company_id INT,
                project_id INT,
                CONSTRAINT ck_ai_task_reports_owner_scope CHECK (
                    (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
                    (owner_scope='company' AND company_id IS NOT NULL AND project_id IS NOT NULL) OR
                    (owner_scope='platform' AND company_id IS NULL AND project_id IS NULL)
                ),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_ai_task_reports_task_id ON ai_task_reports(task_id);
            CREATE INDEX IF NOT EXISTS idx_ai_task_reports_created ON ai_task_reports(created_at);

            CREATE TABLE IF NOT EXISTS ai_task_attachments (
                id SERIAL PRIMARY KEY,
                report_id INT NOT NULL,
                task_id INT NOT NULL,
                file_url TEXT,
                file_type VARCHAR(100),
                file_name VARCHAR(255),
                source VARCHAR(100),
                owner_scope TEXT,
                company_id INT,
                project_id INT,
                CONSTRAINT ck_ai_task_attachments_owner_scope CHECK (
                    (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
                    (owner_scope='company' AND company_id IS NOT NULL AND project_id IS NOT NULL) OR
                    (owner_scope='platform' AND company_id IS NULL AND project_id IS NULL)
                ),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_ai_task_attachments_report_id ON ai_task_attachments(report_id);
            CREATE INDEX IF NOT EXISTS idx_ai_task_attachments_task_id ON ai_task_attachments(task_id);

            ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS created_by TEXT;
            ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS created_by_id INT;
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
