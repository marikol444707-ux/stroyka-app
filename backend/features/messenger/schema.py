def ensure_messenger_schema(get_db):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messenger_accounts (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(40) NOT NULL,
                user_id INT,
                staff_id INT,
                external_user_id VARCHAR(120),
                chat_id VARCHAR(120),
                display_name VARCHAR(255),
                phone_hash VARCHAR(255),
                verified_at TIMESTAMP DEFAULT NOW(),
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_messenger_accounts_provider_user
                ON messenger_accounts(provider, external_user_id);
            CREATE INDEX IF NOT EXISTS idx_messenger_accounts_provider_chat
                ON messenger_accounts(provider, chat_id);
            CREATE INDEX IF NOT EXISTS idx_messenger_accounts_user
                ON messenger_accounts(user_id);
            CREATE INDEX IF NOT EXISTS idx_messenger_accounts_staff
                ON messenger_accounts(staff_id);

            CREATE TABLE IF NOT EXISTS max_invoice_drafts (
                id SERIAL PRIMARY KEY,
                draft_token VARCHAR(120) UNIQUE NOT NULL,
                provider VARCHAR(40) NOT NULL DEFAULT 'max',
                messenger_account_id INT,
                employee_source VARCHAR(40),
                employee_id INT,
                max_user_id VARCHAR(120),
                max_chat_id VARCHAR(120),
                source_type VARCHAR(100),
                source_id VARCHAR(255),
                project_name TEXT,
                location TEXT,
                payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                recognized BOOLEAN DEFAULT FALSE,
                recognition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                status VARCHAR(40) NOT NULL DEFAULT 'draft',
                warehouse_invoice_id INT,
                supplier_invoice_id INT,
                accounting_status VARCHAR(80),
                accounting_warning TEXT,
                reject_reason TEXT,
                expires_at TIMESTAMP,
                confirmed_at TIMESTAMP,
                rejected_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_max_invoice_drafts_token
                ON max_invoice_drafts(draft_token);
            CREATE INDEX IF NOT EXISTS idx_max_invoice_drafts_account
                ON max_invoice_drafts(messenger_account_id);
            CREATE INDEX IF NOT EXISTS idx_max_invoice_drafts_status
                ON max_invoice_drafts(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_max_invoice_drafts_provider_source_unique
                ON max_invoice_drafts(provider, source_id)
                WHERE source_id IS NOT NULL AND source_id <> '';

            CREATE TABLE IF NOT EXISTS messenger_outbox (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(40) NOT NULL,
                messenger_account_id INT,
                user_id INT,
                staff_id INT,
                external_user_id VARCHAR(120),
                chat_id VARCHAR(120),
                event_type VARCHAR(120) NOT NULL,
                entity_type VARCHAR(120),
                entity_id INT,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                actions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                status VARCHAR(40) NOT NULL DEFAULT 'queued',
                priority INT NOT NULL DEFAULT 5,
                attempts INT NOT NULL DEFAULT 0,
                provider_message_id VARCHAR(255),
                last_error TEXT,
                next_attempt_at TIMESTAMP,
                sent_at TIMESTAMP,
                failed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_messenger_outbox_provider_status
                ON messenger_outbox(provider, status, priority, id);
            CREATE INDEX IF NOT EXISTS idx_messenger_outbox_account
                ON messenger_outbox(messenger_account_id);
            CREATE INDEX IF NOT EXISTS idx_messenger_outbox_entity
                ON messenger_outbox(entity_type, entity_id);

            CREATE TABLE IF NOT EXISTS messenger_files (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(40) NOT NULL,
                messenger_account_id INT,
                user_id INT,
                staff_id INT,
                external_user_id VARCHAR(120),
                chat_id VARCHAR(120),
                file_token VARCHAR(255),
                source_id VARCHAR(255),
                project_name TEXT,
                context VARCHAR(120),
                original_filename TEXT,
                content_type VARCHAR(120),
                size_bytes INT DEFAULT 0,
                url TEXT NOT NULL DEFAULT '',
                storage VARCHAR(40),
                storage_key TEXT,
                entity_type VARCHAR(120),
                entity_id INT,
                metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_messenger_files_provider_account
                ON messenger_files(provider, messenger_account_id);
            CREATE INDEX IF NOT EXISTS idx_messenger_files_entity
                ON messenger_files(entity_type, entity_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_messenger_files_provider_file_token_unique
                ON messenger_files(provider, file_token)
                WHERE file_token IS NOT NULL AND file_token <> '';
            CREATE UNIQUE INDEX IF NOT EXISTS idx_messenger_files_provider_source_unique
                ON messenger_files(provider, source_id)
                WHERE source_id IS NOT NULL AND source_id <> '';
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
