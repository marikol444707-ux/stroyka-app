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
            """
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
