def ensure_agent_jobs_schema(get_db):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_jobs (
                id BIGSERIAL PRIMARY KEY,
                owner_scope VARCHAR(20) NOT NULL DEFAULT 'company',
                company_id INT NOT NULL,
                project_id INT,
                project_scope_id INT GENERATED ALWAYS AS (COALESCE(project_id,0)) STORED,
                requested_by_user_id INT,
                requested_by_role VARCHAR(100) NOT NULL DEFAULT '',
                job_type VARCHAR(80) NOT NULL,
                idempotency_key VARCHAR(180) NOT NULL,
                correlation_id VARCHAR(80) NOT NULL,
                payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                status VARCHAR(30) NOT NULL DEFAULT 'queued',
                priority INT NOT NULL DEFAULT 5,
                attempts INT NOT NULL DEFAULT 0,
                max_attempts INT NOT NULL DEFAULT 3,
                run_after TIMESTAMP NOT NULL DEFAULT NOW(),
                locked_at TIMESTAMP,
                locked_by VARCHAR(120),
                heartbeat_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                last_error TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT ck_agent_jobs_owner CHECK (
                    owner_scope='company' AND company_id>0
                ),
                CONSTRAINT ck_agent_jobs_status CHECK (
                    status IN ('queued','running','succeeded','failed','cancelled')
                ),
                CONSTRAINT ck_agent_jobs_priority CHECK (priority BETWEEN 1 AND 10),
                CONSTRAINT ck_agent_jobs_attempts CHECK (
                    attempts>=0 AND max_attempts BETWEEN 1 AND 10
                ),
                CONSTRAINT uq_agent_jobs_idempotency
                    UNIQUE (company_id, project_scope_id, job_type, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_agent_jobs_claim
                ON agent_jobs(status, run_after, priority, id)
                WHERE status='queued';
            CREATE INDEX IF NOT EXISTS idx_agent_jobs_owner
                ON agent_jobs(company_id, project_id, created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_agent_jobs_correlation
                ON agent_jobs(correlation_id);
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
