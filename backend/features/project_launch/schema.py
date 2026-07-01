def ensure_project_launch_schema(get_db):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS counterparties (
            id SERIAL PRIMARY KEY,
            company_id INT DEFAULT 1,
            type TEXT DEFAULT 'customer',
            name TEXT,
            legal_form TEXT,
            inn TEXT,
            kpp TEXT,
            ogrn TEXT,
            legal_address TEXT,
            actual_address TEXT,
            phone TEXT,
            email TEXT,
            bank TEXT,
            bik TEXT,
            bank_account TEXT,
            corr_account TEXT,
            signer_name TEXT,
            signer_basis TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_counterparties_company ON counterparties(company_id);
        CREATE INDEX IF NOT EXISTS idx_counterparties_inn ON counterparties(inn);
        CREATE INDEX IF NOT EXISTS idx_counterparties_type ON counterparties(type);

        CREATE TABLE IF NOT EXISTS project_contract_terms (
            id SERIAL PRIMARY KEY,
            project_id INT,
            project_name TEXT,
            company_id INT DEFAULT 1,
            document_id INT,
            contract_number TEXT,
            contract_date DATE,
            counterparty_id INT,
            contract_sum NUMERIC(14,2) DEFAULT 0,
            advance_amount NUMERIC(14,2) DEFAULT 0,
            payment_terms_json JSONB DEFAULT '{}'::jsonb,
            work_start_date DATE,
            work_end_date DATE,
            acceptance_terms TEXT,
            warranty_terms TEXT,
            penalty_terms TEXT,
            change_order_terms TEXT,
            termination_terms TEXT,
            risk_summary TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_project_contract_terms_project ON project_contract_terms(project_name);
        CREATE INDEX IF NOT EXISTS idx_project_contract_terms_document ON project_contract_terms(document_id);

        CREATE TABLE IF NOT EXISTS project_launch_drafts (
            id SERIAL PRIMARY KEY,
            project_id INT,
            project_name TEXT,
            company_id INT DEFAULT 1,
            source_document_id INT,
            source_file_url TEXT,
            source_file_name TEXT,
            source_file_type TEXT,
            status TEXT DEFAULT 'draft',
            extracted_json JSONB DEFAULT '{}'::jsonb,
            project_patch_json JSONB DEFAULT '{}'::jsonb,
            counterparty_json JSONB DEFAULT '{}'::jsonb,
            contract_terms_json JSONB DEFAULT '{}'::jsonb,
            estimate_draft_json JSONB DEFAULT '{}'::jsonb,
            findings_json JSONB DEFAULT '[]'::jsonb,
            tasks_json JSONB DEFAULT '[]'::jsonb,
            confidence NUMERIC(5,2) DEFAULT 0,
            warnings_json JSONB DEFAULT '[]'::jsonb,
            created_by TEXT,
            created_by_id INT,
            created_at TIMESTAMP DEFAULT NOW(),
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            applied_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_project_launch_drafts_project ON project_launch_drafts(project_name);
        CREATE INDEX IF NOT EXISTS idx_project_launch_drafts_status ON project_launch_drafts(status);
        CREATE INDEX IF NOT EXISTS idx_project_launch_drafts_document ON project_launch_drafts(source_document_id);
    """)
    conn.commit()
    cur.close()
    conn.close()
