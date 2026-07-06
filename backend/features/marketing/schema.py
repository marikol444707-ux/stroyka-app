def ensure_marketing_schema(get_db):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS marketing_publications (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                status VARCHAR(80) NOT NULL DEFAULT 'Черновик',
                project_id INT,
                project_name TEXT,
                publication_url TEXT NOT NULL DEFAULT '',
                target_site BOOLEAN DEFAULT TRUE,
                target_max BOOLEAN DEFAULT FALSE,
                channel_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                utm_campaign VARCHAR(160),
                scheduled_at TIMESTAMP,
                queued_at TIMESTAMP,
                published_at TIMESTAMP,
                created_by VARCHAR(255),
                updated_by VARCHAR(255),
                metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_marketing_publications_status
                ON marketing_publications(status, id DESC);
            CREATE INDEX IF NOT EXISTS idx_marketing_publications_project
                ON marketing_publications(project_id);
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
