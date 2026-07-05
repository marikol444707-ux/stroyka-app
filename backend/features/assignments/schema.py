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
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_ai_task_attachments_report_id ON ai_task_attachments(report_id);
            CREATE INDEX IF NOT EXISTS idx_ai_task_attachments_task_id ON ai_task_attachments(task_id);
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
