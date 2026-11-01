"""Legacy bootstrap SQL as inert data; importing this module executes no DDL.

This batch also contains legacy data repairs. It is NOT a clean-schema runner.
No connection, credentials, seed accounts, migration execution or CLI lives here.
"""

LEGACY_SCHEMA_BATCH = """
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            client VARCHAR(255),
            status VARCHAR(100),
            budget FLOAT DEFAULT 0,
            deadline VARCHAR(50),
            progress INT DEFAULT 0,
            tasks TEXT[] DEFAULT '{}',
            pricelist_id INT
        );
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(100),
            email VARCHAR(255),
            status VARCHAR(100),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS materials (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT DEFAULT 0,
            price FLOAT DEFAULT 0,
            min_quantity FLOAT DEFAULT 0,
            project VARCHAR(255),
            category VARCHAR(255),
            work_package VARCHAR(255)
        );
        ALTER TABLE materials ADD COLUMN IF NOT EXISTS work_package VARCHAR(255);
        ALTER TABLE materials ALTER COLUMN name TYPE TEXT;
        CREATE TABLE IF NOT EXISTS warehouse_history (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL DEFAULT 1,
            material VARCHAR(255),
            type VARCHAR(50),
            quantity FLOAT,
            date VARCHAR(50),
            project VARCHAR(255),
            issued_to VARCHAR(255),
            issued_by VARCHAR(255),
            work_package VARCHAR(255),
            date_time VARCHAR(100)
        );
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS work_package VARCHAR(255);
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS unit VARCHAR(50);
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS source_type VARCHAR(100);
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS source_id INT;
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS source_invoice_id INT;
        ALTER TABLE warehouse_history ADD COLUMN IF NOT EXISTS source_invoice_line_index INT;
        ALTER TABLE warehouse_history ALTER COLUMN material TYPE TEXT;
        CREATE INDEX IF NOT EXISTS idx_warehouse_history_source_invoice
            ON warehouse_history(company_id, source_invoice_id, source_invoice_line_index)
            WHERE source_invoice_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS staff (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            role VARCHAR(100),
            phone VARCHAR(100),
            salary FLOAT DEFAULT 0,
            project VARCHAR(255),
            pay_type VARCHAR(50) DEFAULT 'оклад'
        );
        CREATE TABLE IF NOT EXISTS piecework (
            id SERIAL PRIMARY KEY,
            staff_id VARCHAR(50),
            description VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT,
            price_per_unit FLOAT,
            total FLOAT,
            project VARCHAR(255),
            date VARCHAR(50),
            comment TEXT,
            photo_url VARCHAR(255)
        );
        ALTER TABLE piecework ADD COLUMN IF NOT EXISTS work_journal_id INT;
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            role VARCHAR(100)
        );
        ALTER TABLE users ADD COLUMN IF NOT EXISTS project_id INT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS project_name VARCHAR(255);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(20);
        ALTER TABLE users ALTER COLUMN reset_token TYPE VARCHAR(128);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count INT DEFAULT 0;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(100);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(100);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_required BOOLEAN DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_secret VARCHAR(80);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_confirmed_at TIMESTAMP;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE users ADD COLUMN IF NOT EXISTS platform_account_id INT;
        UPDATE users SET two_factor_required=TRUE WHERE role IN ('директор','зам_директора','бухгалтер','system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin');
        UPDATE users SET active=TRUE WHERE active IS NULL;
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            session_hash VARCHAR(128) NOT NULL UNIQUE,
            ip VARCHAR(100),
            user_agent TEXT,
            two_factor_passed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_seen_at TIMESTAMP DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_hash_active ON user_sessions(session_hash) WHERE revoked_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            chat_type VARCHAR(50) DEFAULT 'company',
            project_id INT,
            author_id INT,
            author_name VARCHAR(255),
            author_role VARCHAR(100),
            text TEXT,
            photo_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_by JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS company_id INT;
        CREATE INDEX IF NOT EXISTS idx_messages_company_created_at ON messages(company_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_author_id ON messages(author_id);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_projects JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_packages JSONB DEFAULT '[]'::jsonb;
        CREATE TABLE IF NOT EXISTS tb_journal (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            master_name VARCHAR(255),
            instructor VARCHAR(255),
            instruction_type VARCHAR(100),
            program TEXT,
            instruction_text TEXT,
            participants_json TEXT,
            photo_url VARCHAR(500),
            date DATE,
            ai_filled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            work_package VARCHAR(100)
        );
        ALTER TABLE tb_journal ADD COLUMN IF NOT EXISTS program TEXT;
        ALTER TABLE tb_journal ADD COLUMN IF NOT EXISTS instruction_text TEXT;
        ALTER TABLE tb_journal ADD COLUMN IF NOT EXISTS participants_json TEXT;
        ALTER TABLE tb_journal ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500);
        ALTER TABLE tb_journal ADD COLUMN IF NOT EXISTS ai_filled BOOLEAN DEFAULT FALSE;
        CREATE TABLE IF NOT EXISTS warranty_defects (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            description TEXT,
            found_at DATE,
            reported_by VARCHAR(255),
            reporter_phone VARCHAR(50),
            status VARCHAR(50) DEFAULT 'Открыт',
            assigned_to VARCHAR(255),
            fix_notes TEXT,
            fixed_at DATE,
            photo_url TEXT,
            severity VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS warranty_start_date DATE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS warranty_end_date DATE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS warranty_contact VARCHAR(255);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_show_on_site BOOLEAN DEFAULT FALSE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_is_live BOOLEAN DEFAULT FALSE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_status VARCHAR(100) DEFAULT 'Черновик';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_title VARCHAR(255);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_category VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_location VARCHAR(255);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_area VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_year VARCHAR(20);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_stage VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_progress INT DEFAULT 0;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_price_label VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_term VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_summary TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_result TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_passport TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_tags JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_images JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_original_images JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_enhanced_images JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_main_image_url TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_ai_status VARCHAR(100) DEFAULT 'Не обработано';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_ai_notes TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS public_updated_at TIMESTAMP;
        CREATE TABLE IF NOT EXISTS site_price_rules (
            id SERIAL PRIMARY KEY,
            group_key VARCHAR(100) NOT NULL,
            item_key VARCHAR(100) NOT NULL,
            label VARCHAR(255) NOT NULL,
            value DOUBLE PRECISION DEFAULT 0,
            value_type VARCHAR(50) DEFAULT 'rate',
            unit VARCHAR(50) DEFAULT '',
            enabled BOOLEAN DEFAULT TRUE,
            sort_order INT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(group_key, item_key)
        );
        CREATE TABLE IF NOT EXISTS crm_leads (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(50),
            email VARCHAR(255),
            source VARCHAR(255),
            budget NUMERIC(14,2) DEFAULT 0,
            notes TEXT,
            stage VARCHAR(50) DEFAULT 'Новый',
            project_id INT,
            photo_url TEXT,
            created_by VARCHAR(255),
            created_at VARCHAR(50)
        );
	        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS project_id INT;
	        ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS photo_url TEXT;
        CREATE TABLE IF NOT EXISTS expense_reports (
            id SERIAL PRIMARY KEY,
            employee_id INT,
            employee_name VARCHAR(255),
            project_name VARCHAR(255),
            report_type VARCHAR(50) DEFAULT 'Авансовый отчёт',
            purpose TEXT,
            total_amount NUMERIC(14,2),
            issued_amount NUMERIC(14,2),
            spent_amount NUMERIC(14,2),
            balance NUMERIC(14,2),
            items_json TEXT,
            photo_url TEXT,
            date_from DATE,
            date_to DATE,
            status VARCHAR(50) DEFAULT 'На утверждении',
            approved_by VARCHAR(255),
            approved_at DATE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS supplier_invoices (
            id SERIAL PRIMARY KEY,
            company_id INT DEFAULT 1,
            supplier_id INT,
            supplier_name VARCHAR(255),
            project_name VARCHAR(255),
            invoice_number VARCHAR(100),
            invoice_date DATE,
            amount NUMERIC(14,2),
            vat_amount NUMERIC(14,2),
            description TEXT,
            file_url TEXT,
            photo_url TEXT,
            status VARCHAR(50) DEFAULT 'На утверждении',
            approved_by VARCHAR(255),
            approved_at DATE,
            paid_at DATE,
            paid_by VARCHAR(255),
            paid_note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS paid_amount NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS offer_id INT;
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS request_id INT;
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(100);
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS material_name VARCHAR(255);
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS work_package VARCHAR(100);
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS warehouse_invoice_id INT;
        CREATE TABLE IF NOT EXISTS inspection_orders (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            order_number VARCHAR(100),
            body VARCHAR(100),
            inspector VARCHAR(255),
            description TEXT,
            recommendations TEXT,
            deadline DATE,
            status VARCHAR(50) DEFAULT 'Открыто',
            photo_url TEXT,
            file_url TEXT,
            date DATE,
            response TEXT,
            response_date DATE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS document_versions (
            id SERIAL PRIMARY KEY,
            document_type VARCHAR(100),
            document_id INT,
            version_label VARCHAR(50),
            snapshot_json TEXT,
            changed_by VARCHAR(255),
            change_reason TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS file_ownership (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            project_id INT,
            file_url TEXT NOT NULL,
            storage_key TEXT,
            context VARCHAR(100) DEFAULT 'general',
            original_name TEXT,
            content_type VARCHAR(255),
            uploaded_by_id INT,
            uploaded_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_file_ownership_url ON file_ownership(file_url);
        CREATE INDEX IF NOT EXISTS idx_file_ownership_company_project ON file_ownership(company_id,project_id,id DESC);
        ALTER TABLE file_ownership ADD COLUMN IF NOT EXISTS deletion_status VARCHAR(30) DEFAULT 'active';
        ALTER TABLE file_ownership ADD COLUMN IF NOT EXISTS deletion_error TEXT;
        ALTER TABLE file_ownership ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMP;
        ALTER TABLE file_ownership ADD COLUMN IF NOT EXISTS retained_at TIMESTAMPTZ;
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            user_id INT,
            user_name VARCHAR(255),
            user_role VARCHAR(100),
            action VARCHAR(100),
            entity_type VARCHAR(100),
            entity_id INT,
            description TEXT,
            project_name VARCHAR(255),
            ip VARCHAR(50),
            owner_scope TEXT,
            company_id INT,
            project_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS owner_scope TEXT;
        ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS project_id INT;
        CREATE INDEX IF NOT EXISTS idx_audit_log_owner ON audit_log(owner_scope,company_id,project_id);
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_audit_log_owner_scope') THEN
                ALTER TABLE audit_log ADD CONSTRAINT ck_audit_log_owner_scope CHECK (
                    (owner_scope IS NULL AND company_id IS NULL AND project_id IS NULL) OR
                    (owner_scope='company' AND company_id IS NOT NULL) OR
                    (owner_scope IN ('platform','legacy') AND company_id IS NULL AND project_id IS NULL)
                );
            END IF;
        END $$;
        CREATE TABLE IF NOT EXISTS api_errors (
            id SERIAL PRIMARY KEY,
            method VARCHAR(20),
            path TEXT,
            status_code INT DEFAULT 500,
            error_type VARCHAR(255),
            error_message TEXT,
            user_id INT,
            user_name VARCHAR(255),
            user_role VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_api_errors_created_at ON api_errors(created_at DESC);
        CREATE TABLE IF NOT EXISTS pricelists (
            id SERIAL PRIMARY KEY,
            name TEXT,
            description TEXT,
            for_who VARCHAR(255),
            coefficient FLOAT DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS pricelist_items (
            id SERIAL PRIMARY KEY,
            pricelist_id INT,
            name TEXT,
            unit VARCHAR(50),
            price FLOAT DEFAULT 0,
            category TEXT,
            specialization TEXT
        );
        CREATE TABLE IF NOT EXISTS invite_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE,
            role VARCHAR(100),
            used BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(100),
            email VARCHAR(255),
            specialization VARCHAR(255),
            category VARCHAR(255),
            rating FLOAT DEFAULT 5.0,
            status VARCHAR(100)
        );
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS inn VARCHAR(50);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS kpp VARCHAR(50);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS ogrn VARCHAR(50);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS legal_address TEXT;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS actual_address TEXT;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS bank VARCHAR(255);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS bik VARCHAR(50);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS account VARCHAR(50);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS kor_account VARCHAR(50);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS director_name VARCHAR(255);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS director_position VARCHAR(255);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS contract_url VARCHAR(500);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS contract_number VARCHAR(100);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS contract_date DATE;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS license_url VARCHAR(500);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS price_url VARCHAR(500);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS website VARCHAR(255);
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS notes TEXT;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS user_id INT;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS registered_at TIMESTAMP;
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS source_type VARCHAR(100) DEFAULT '';
        ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS source_detail TEXT DEFAULT '';
        CREATE TABLE IF NOT EXISTS supplier_aliases (
            id SERIAL PRIMARY KEY,
            supplier_id INT,
            alias_name TEXT,
            alias_key TEXT,
            inn VARCHAR(50),
            kpp VARCHAR(50),
            ogrn VARCHAR(50),
            source VARCHAR(100),
            confidence FLOAT DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_supplier_aliases_supplier_id ON supplier_aliases(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_supplier_aliases_alias_key ON supplier_aliases(alias_key);
        CREATE INDEX IF NOT EXISTS idx_supplier_aliases_inn ON supplier_aliases(inn);
        CREATE INDEX IF NOT EXISTS idx_supplier_aliases_ogrn ON supplier_aliases(ogrn);
        ALTER TABLE supplier_aliases ADD COLUMN IF NOT EXISTS related_supplier_id INT;
        CREATE INDEX IF NOT EXISTS idx_supplier_aliases_related_supplier_id ON supplier_aliases(related_supplier_id);
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS supplier_id INT;
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS preset_name VARCHAR(255);
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS preset_category VARCHAR(255);
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS platform_account_id INT;
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS project_name VARCHAR(255);
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS assigned_projects JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS assigned_packages JSONB DEFAULT '[]'::jsonb;
        CREATE TABLE IF NOT EXISTS supplier_documents (
            id SERIAL PRIMARY KEY,
            supplier_id INT,
            doc_type VARCHAR(100),
            title VARCHAR(255),
            file_url VARCHAR(500),
            status VARCHAR(50) DEFAULT 'Загружен',
            signed_at DATE,
            expires_at DATE,
            notes TEXT,
            uploaded_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        -- NULL ownership is deliberate: old supplier documents are not shared
        -- with customers until their company is established from evidence.
        ALTER TABLE supplier_documents ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE supplier_documents ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;
        CREATE INDEX IF NOT EXISTS idx_supplier_documents_company_active
            ON supplier_documents (company_id, supplier_id, created_at DESC)
            WHERE archived_at IS NULL;
        CREATE TABLE IF NOT EXISTS supplier_invoice_templates (
            id SERIAL PRIMARY KEY,
            supplier_id INT,
            supplier_key TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            template_name TEXT,
            document_type TEXT,
            match_keywords TEXT,
            column_map TEXT,
            sample_json TEXT,
            active BOOLEAN DEFAULT TRUE,
            usage_count INT DEFAULT 0,
            last_used_at TIMESTAMP,
            updated_by TEXT,
            updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_supplier_invoice_templates_key ON supplier_invoice_templates(supplier_key);
        CREATE INDEX IF NOT EXISTS idx_supplier_invoice_templates_active ON supplier_invoice_templates(active);
        CREATE TABLE IF NOT EXISTS supply_requests (
            id SERIAL PRIMARY KEY,
            material_name VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50),
            project VARCHAR(255),
            created_by VARCHAR(255),
            date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'Новая',
            notes TEXT,
            selected_suppliers INT[] DEFAULT '{}'
        );
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS requested_by_role VARCHAR(50);
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS requested_by_id INT;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS urgency VARCHAR(50) DEFAULT 'обычная';
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS prorab_id INT;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS prorab_name VARCHAR(255);
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS prorab_confirmed_at TIMESTAMP;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS director_id INT;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS director_name VARCHAR(255);
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS director_approved_at TIMESTAMP;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS reject_reason TEXT;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS category VARCHAR(100);
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS items_json TEXT;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS work_package VARCHAR(100);
        -- Multi-tenancy подготовка (см. ONBOARDING — план «единый кабинет поставщика»)
        -- Пока не используется в коде, но колонки добавлены чтобы при миграции не делать ALTER большим таблицам
        CREATE TABLE IF NOT EXISTS platform_accounts (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            owner_name VARCHAR(255),
            contact_email VARCHAR(255),
            plan VARCHAR(50) DEFAULT 'demo',
            status VARCHAR(50) DEFAULT 'active',
            notes TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        INSERT INTO platform_accounts (id, name, owner_name, plan, status)
        VALUES (1, 'СтройКа', 'system_owner', 'pro', 'active')
        ON CONFLICT (id) DO NOTHING;
        SELECT setval(pg_get_serial_sequence('platform_accounts','id'), GREATEST((SELECT COALESCE(MAX(id), 1) FROM platform_accounts), 1), true);
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            short_name VARCHAR(255),
            inn VARCHAR(50),
            kpp VARCHAR(50),
            ogrn VARCHAR(50),
            legal_address TEXT,
            phone VARCHAR(100),
            email VARCHAR(255),
            logo_url VARCHAR(500),
            subdomain VARCHAR(100),
            plan VARCHAR(50) DEFAULT 'demo',
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        INSERT INTO companies (id, name, short_name, plan) VALUES (1, 'СтройКа', 'СтройКа', 'pro')
        ON CONFLICT (id) DO NOTHING;
        SELECT setval(pg_get_serial_sequence('companies','id'), GREATEST((SELECT COALESCE(MAX(id), 1) FROM companies), 1), true);
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS platform_account_id INT DEFAULT 1;
        UPDATE companies SET platform_account_id=1 WHERE platform_account_id IS NULL;
        -- SaaS-биллинг: расширение companies для управления подписками
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255);
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(100);
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_until DATE;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS plan_expires_at DATE;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS monthly_fee NUMERIC(10,2);
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'active';
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS suspended_reason TEXT;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS max_projects INT;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS max_users INT;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP;
        ALTER TABLE companies ADD COLUMN IF NOT EXISTS notes TEXT;
        -- Оплаты от компаний-клиентов (SaaS-выручка)
        CREATE TABLE IF NOT EXISTS company_payments (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            amount NUMERIC(10,2),
            payment_date DATE,
            method VARCHAR(50),
            invoice_number VARCHAR(100),
            status VARCHAR(50) DEFAULT 'paid',
            period_start DATE,
            period_end DATE,
            notes TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS platform_billing_documents (
            id SERIAL PRIMARY KEY,
            platform_account_id INT,
            company_id INT NOT NULL,
            document_type VARCHAR(50) DEFAULT 'invoice',
            number VARCHAR(100),
            status VARCHAR(50) DEFAULT 'draft',
            amount NUMERIC(10,2),
            currency VARCHAR(10) DEFAULT 'RUB',
            issue_date DATE,
            due_date DATE,
            period_start DATE,
            period_end DATE,
            payment_provider VARCHAR(50),
            payment_url TEXT,
            file_url TEXT,
            notes TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS platform_payment_events (
            id SERIAL PRIMARY KEY,
            provider VARCHAR(50),
            event_id VARCHAR(255),
            event_type VARCHAR(100),
            provider_status VARCHAR(100),
            platform_account_id INT,
            company_id INT,
            billing_document_id INT,
            amount NUMERIC(10,2),
            currency VARCHAR(10) DEFAULT 'RUB',
            trusted BOOLEAN DEFAULT FALSE,
            action_status VARCHAR(50) DEFAULT 'received',
            payload_json TEXT,
            notes TEXT,
            received_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP
        );
        ALTER TABLE platform_payment_events ADD COLUMN IF NOT EXISTS payment_id INT;
        ALTER TABLE platform_payment_events ADD COLUMN IF NOT EXISTS processed_by VARCHAR(255);
        CREATE INDEX IF NOT EXISTS idx_platform_payment_events_doc ON platform_payment_events (billing_document_id);
        CREATE INDEX IF NOT EXISTS idx_platform_payment_events_provider ON platform_payment_events (provider, event_id);
        CREATE INDEX IF NOT EXISTS idx_platform_payment_events_received_at ON platform_payment_events (received_at DESC);
        CREATE TABLE IF NOT EXISTS platform_followups (
            id SERIAL PRIMARY KEY,
            platform_account_id INT,
            company_id INT,
            billing_document_id INT,
            source VARCHAR(50) DEFAULT 'manual',
            channel VARCHAR(50) DEFAULT 'call',
            title VARCHAR(255),
            contact_name VARCHAR(255),
            contact_value VARCHAR(255),
            due_date DATE,
            status VARCHAR(50) DEFAULT 'open',
            responsible_name VARCHAR(255),
            notes TEXT,
            result TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_platform_followups_company ON platform_followups (company_id);
        CREATE INDEX IF NOT EXISTS idx_platform_followups_document ON platform_followups (billing_document_id);
        CREATE INDEX IF NOT EXISTS idx_platform_followups_status_due ON platform_followups (status, due_date);
        -- Заявки на демо с лендинга
        CREATE TABLE IF NOT EXISTS demo_requests (
            id SERIAL PRIMARY KEY,
            company_name VARCHAR(255),
            contact_name VARCHAR(255),
            phone VARCHAR(100),
            email VARCHAR(255),
            employees_count VARCHAR(50),
            projects_count VARCHAR(50),
            comment TEXT,
            source VARCHAR(100),
            status VARCHAR(50) DEFAULT 'Новая',
            assigned_company_id INT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS platform_audit_log (
            id SERIAL PRIMARY KEY,
            actor_user_id INT,
            actor_name VARCHAR(255),
            actor_role VARCHAR(100),
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(100),
            entity_id INT,
            entity_name VARCHAR(255),
            platform_account_id INT,
            company_id INT,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS platform_support_sessions (
            id SERIAL PRIMARY KEY,
            platform_account_id INT,
            company_id INT,
            reason TEXT NOT NULL,
            scope VARCHAR(50) DEFAULT 'read_only',
            status VARCHAR(50) DEFAULT 'active',
            expires_at TIMESTAMP,
            opened_by_user_id INT,
            opened_by_name VARCHAR(255),
            closed_by_user_id INT,
            closed_by_name VARCHAR(255),
            closed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );
        -- Ставим company_id на ключевые таблицы — пока всем 1 (текущая компания)
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE materials ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;
        -- Рабочие роли пользователя в нескольких компаниях одного SaaS-аккаунта.
        -- users.company_id остается default/legacy-привязкой до полной миграции рабочих цепочек.
        CREATE TABLE IF NOT EXISTS user_company_roles (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            platform_account_id INT,
            company_id INT NOT NULL,
            role VARCHAR(100) NOT NULL,
            assigned_projects JSONB DEFAULT '[]'::jsonb,
            assigned_packages JSONB DEFAULT '[]'::jsonb,
            active BOOLEAN DEFAULT TRUE,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS platform_account_id INT;
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS staff_id INT;
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS assigned_projects JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS assigned_packages JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE user_company_roles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_company_roles_unique_role ON user_company_roles (user_id, company_id, role);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_company_roles_one_default ON user_company_roles (user_id) WHERE active IS TRUE AND is_default IS TRUE;
        CREATE INDEX IF NOT EXISTS idx_user_company_roles_user ON user_company_roles (user_id);
        CREATE INDEX IF NOT EXISTS idx_user_company_roles_company ON user_company_roles (company_id);
        CREATE INDEX IF NOT EXISTS idx_user_company_roles_account ON user_company_roles (platform_account_id);
        CREATE INDEX IF NOT EXISTS idx_user_company_roles_active ON user_company_roles (active);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_staff_company_id
            ON staff (company_id, id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_company_roles_active_staff
            ON user_company_roles (company_id, staff_id)
            WHERE staff_id IS NOT NULL AND COALESCE(active, TRUE) IS TRUE;
        DO $user_company_staff_link$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_constraint
            WHERE conname='fk_user_company_roles_company_staff'
              AND conrelid='public.user_company_roles'::regclass
        ) THEN
            ALTER TABLE public.user_company_roles
            ADD CONSTRAINT fk_user_company_roles_company_staff
            FOREIGN KEY (company_id, staff_id)
            REFERENCES public.staff(company_id, id);
        END IF;
        END $user_company_staff_link$;
        INSERT INTO user_company_roles
            (user_id, platform_account_id, company_id, role, assigned_projects, assigned_packages, active, is_default)
        SELECT u.id,
               COALESCE(u.platform_account_id,c.platform_account_id,1),
               u.company_id,
               u.role,
               COALESCE(u.assigned_projects,'[]'::jsonb),
               COALESCE(u.assigned_packages,'[]'::jsonb),
               COALESCE(u.active,TRUE),
               TRUE
        FROM users u
        LEFT JOIN companies c ON c.id=u.company_id
        WHERE u.company_id IS NOT NULL
          AND COALESCE(u.role,'') <> ''
          AND COALESCE(u.role,'') NOT IN ('system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin')
        ON CONFLICT (user_id, company_id, role) DO NOTHING;
        -- Поставщики — глобальные. company_id у них означает «первичный клиент» (необязательно)
        -- Связи компания-поставщик через company_supplier_links (договор и рейтинг свой у каждой пары)
        CREATE TABLE IF NOT EXISTS company_supplier_links (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            supplier_id INT NOT NULL,
            platform_account_id INT,
            local_category VARCHAR(100),
            source_type VARCHAR(100),
            source_detail TEXT,
            contract_url VARCHAR(500),
            contract_number VARCHAR(100),
            contract_date DATE,
            rating FLOAT,
            status VARCHAR(50) DEFAULT 'Активный',
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(company_id, supplier_id)
        );
        ALTER TABLE company_supplier_links ADD COLUMN IF NOT EXISTS platform_account_id INT;
        ALTER TABLE company_supplier_links ADD COLUMN IF NOT EXISTS local_category VARCHAR(100);
        ALTER TABLE company_supplier_links ADD COLUMN IF NOT EXISTS source_type VARCHAR(100);
        ALTER TABLE company_supplier_links ADD COLUMN IF NOT EXISTS source_detail TEXT;
        CREATE INDEX IF NOT EXISTS idx_company_supplier_links_account ON company_supplier_links(platform_account_id);
        CREATE INDEX IF NOT EXISTS idx_company_supplier_links_company ON company_supplier_links(company_id);
        CREATE INDEX IF NOT EXISTS idx_company_supplier_links_supplier ON company_supplier_links(supplier_id);
        CREATE TABLE IF NOT EXISTS supply_request_recipients (
            id SERIAL PRIMARY KEY,
            company_id INT,
            request_id INT NOT NULL,
            supplier_id INT NOT NULL,
            target_supplier_id INT NOT NULL,
            supplier_user_id INT,
            supplier_group_ids INT[] DEFAULT '{}',
            visible_to_supplier BOOLEAN DEFAULT FALSE,
            problem_reason TEXT DEFAULT '',
            status VARCHAR(100) DEFAULT 'Ожидает ответа',
            email_notification_status VARCHAR(100) DEFAULT '',
            email_sent_at TIMESTAMP,
            max_notification_status VARCHAR(100) DEFAULT '',
            max_outbox_id INT,
            max_queued_at TIMESTAMP,
            requested_at TIMESTAMP DEFAULT NOW(),
            responded_at TIMESTAMP
        );
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS request_id INT;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS supplier_id INT;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS target_supplier_id INT;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS supplier_user_id INT;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS supplier_group_ids INT[] DEFAULT '{}';
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS visible_to_supplier BOOLEAN DEFAULT FALSE;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS problem_reason TEXT DEFAULT '';
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS status VARCHAR(100) DEFAULT 'Ожидает ответа';
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS email_notification_status VARCHAR(100) DEFAULT '';
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS email_sent_at TIMESTAMP;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS max_notification_status VARCHAR(100) DEFAULT '';
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS max_outbox_id INT;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS max_queued_at TIMESTAMP;
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS requested_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE supply_request_recipients ADD COLUMN IF NOT EXISTS responded_at TIMESTAMP;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_supply_request_recipients_request_target
            ON supply_request_recipients(request_id, target_supplier_id);
        CREATE INDEX IF NOT EXISTS idx_supply_request_recipients_company ON supply_request_recipients(company_id);
        CREATE INDEX IF NOT EXISTS idx_supply_request_recipients_supplier ON supply_request_recipients(target_supplier_id);
        CREATE INDEX IF NOT EXISTS idx_supply_request_recipients_visible ON supply_request_recipients(visible_to_supplier);
        -- Подписки поставщиков (биллинг — пока заготовка)
        CREATE TABLE IF NOT EXISTS supplier_subscriptions (
            id SERIAL PRIMARY KEY,
            supplier_id INT NOT NULL,
            plan VARCHAR(50) DEFAULT 'free',
            valid_until DATE,
            monthly_fee NUMERIC(10,2) DEFAULT 0,
            payment_method VARCHAR(50),
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS supplier_offers (
            id SERIAL PRIMARY KEY,
            request_id INT,
            supplier_id INT,
            price_per_unit FLOAT,
            total_price FLOAT,
            delivery_days INT,
            notes TEXT,
            status VARCHAR(100) DEFAULT 'Ожидает'
        );
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(100) DEFAULT 'Постоплата';
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS vat_included BOOLEAN DEFAULT TRUE;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS pdf_url VARCHAR(500);
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS valid_until DATE;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS supplier_message TEXT;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS requested_at TIMESTAMP DEFAULT NOW();
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS response_due_at TIMESTAMPTZ;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS responded_at TIMESTAMP;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS ai_recommended BOOLEAN DEFAULT FALSE;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(100);
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS items_kp_json TEXT;
        ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS party_snapshot_json JSONB;
        CREATE TABLE IF NOT EXISTS supplier_offer_events (
            id SERIAL PRIMARY KEY,
            offer_id INT,
            event_type VARCHAR(100),
            status_from VARCHAR(100),
            status_to VARCHAR(100),
            actor_name VARCHAR(255),
            actor_role VARCHAR(100),
            payload_json TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE supplier_invoices ADD COLUMN IF NOT EXISTS delivery_allowed BOOLEAN DEFAULT FALSE;
        CREATE TABLE IF NOT EXISTS supply_deliveries (
            id SERIAL PRIMARY KEY,
            offer_id INT,
            company_id INT DEFAULT 1,
            request_id INT,
            supplier_id INT,
            supplier_name VARCHAR(255),
            project VARCHAR(255),
            work_package VARCHAR(100),
            material_name VARCHAR(255),
            planned_quantity NUMERIC(14,4),
            shipped_quantity NUMERIC(14,4),
            received_quantity NUMERIC(14,4) DEFAULT 0,
            unit VARCHAR(50),
            price_per_unit NUMERIC(14,2),
            total_price NUMERIC(14,2),
            status VARCHAR(100) DEFAULT 'Готовится к отгрузке',
            waybill_number VARCHAR(100),
            waybill_date DATE,
            vehicle_number VARCHAR(100),
            driver_name VARCHAR(255),
            document_url TEXT,
            photo_url TEXT,
            shipped_at TIMESTAMP,
            received_at TIMESTAMP,
            received_by VARCHAR(255),
            quality_status VARCHAR(100) DEFAULT 'Не проверено',
            quality_notes TEXT,
            shortage_quantity NUMERIC(14,4) DEFAULT 0,
            ai_check_result TEXT,
            claim_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE supply_deliveries ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE supply_deliveries ADD COLUMN IF NOT EXISTS work_package VARCHAR(100);
        CREATE TABLE IF NOT EXISTS supply_claims (
            id SERIAL PRIMARY KEY,
            delivery_id INT,
            request_id INT,
            offer_id INT,
            supplier_id INT,
            project VARCHAR(255),
            material_name VARCHAR(255),
            claim_type VARCHAR(100),
            description TEXT,
            expected_quantity NUMERIC(14,4),
            received_quantity NUMERIC(14,4),
            shortage_quantity NUMERIC(14,4),
            photo_url TEXT,
            status VARCHAR(100) DEFAULT 'Открыта',
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            resolved_at TIMESTAMP,
            resolution TEXT
        );
        ALTER TABLE supply_claims ADD COLUMN IF NOT EXISTS work_package VARCHAR(100);
        CREATE TABLE IF NOT EXISTS supply_history (
            id SERIAL PRIMARY KEY,
            company_id INT DEFAULT 1,
            supplier_id INT,
            material_name VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50),
            price_per_unit FLOAT,
            total_price FLOAT,
            project VARCHAR(255),
            date VARCHAR(50),
            status VARCHAR(100),
            confirmed_by VARCHAR(255),
            work_package VARCHAR(100) DEFAULT ''
        );
        ALTER TABLE supply_history ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE supply_history ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT '';
        ALTER TABLE supply_history ADD COLUMN IF NOT EXISTS request_id INT;
        ALTER TABLE supply_history ADD COLUMN IF NOT EXISTS delivery_id INT;
        CREATE TABLE IF NOT EXISTS supplier_catalog (
            id SERIAL PRIMARY KEY,
            supplier_id INT,
            supplier_name VARCHAR(255),
            material_name VARCHAR(255),
            unit VARCHAR(50) DEFAULT 'шт',
            price FLOAT DEFAULT 0,
            min_quantity FLOAT DEFAULT 1,
            delivery_days INT DEFAULT 3,
            in_stock BOOLEAN DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS supply_request_templates (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            category VARCHAR(100),
            items_json TEXT,
            created_by VARCHAR(255),
            created_by_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS material_transfers (
            id SERIAL PRIMARY KEY,
            company_id INT,
            project_id INT,
            project_name VARCHAR(255),
            from_location VARCHAR(255),
            to_person VARCHAR(255),
            to_person_role VARCHAR(100),
            work_package VARCHAR(255),
            material_name VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50) DEFAULT 'шт',
            transfer_date DATE,
            signed BOOLEAN DEFAULT FALSE,
            signed_at TIMESTAMP,
            notes TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Активна';
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS cancelled_by VARCHAR(255);
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS cancel_reason TEXT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS work_package VARCHAR(255);
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS to_user_id INT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS invoice_id INT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS invoice_line_key VARCHAR(255);
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS invoice_line_index INT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(100);
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS project_id INT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS issue_party_snapshot_json JSONB;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS issue_party_snapshot_hash CHAR(64);
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS issue_party_snapshot_frozen_at TIMESTAMPTZ;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS receipt_party_snapshot_json JSONB;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS receipt_party_snapshot_hash CHAR(64);
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS receipt_party_snapshot_frozen_at TIMESTAMPTZ;
        UPDATE material_transfers mt
           SET company_id=project_scope.company_id,
               project_id=project_scope.project_id
          FROM (
              SELECT name, MIN(id) AS project_id, MIN(company_id) AS company_id
                FROM projects
               WHERE company_id IS NOT NULL
               GROUP BY name
              HAVING COUNT(*)=1
          ) project_scope
         WHERE (mt.company_id IS NULL OR mt.project_id IS NULL)
           AND mt.project_name=project_scope.name;
        CREATE INDEX IF NOT EXISTS idx_material_transfers_company_id
            ON material_transfers(company_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_material_transfers_company_project
            ON material_transfers(company_id,project_id,id DESC);
        CREATE TABLE IF NOT EXISTS brigade_contracts (
            id SERIAL PRIMARY KEY,
            company_id INT DEFAULT 1,
            project_id INT,
            project_name VARCHAR(255),
            work_package VARCHAR(100) DEFAULT '',
            brigade_name VARCHAR(255),
            contractor_type VARCHAR(50),
            contractor_id INT,
            total_amount NUMERIC(14,2) DEFAULT 0,
            status VARCHAR(50) DEFAULT 'Черновик',
            signed_at DATE,
            notes TEXT,
            pricelist_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT '';
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS act_scan_url TEXT;
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS settlement_version SMALLINT NOT NULL DEFAULT 1;
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS contract_scan_url TEXT;
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS party_snapshot_json JSONB;
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS party_snapshot_hash VARCHAR(64);
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS party_snapshot_frozen_at TIMESTAMPTZ;
        ALTER TABLE brigade_contracts ALTER COLUMN company_id SET DEFAULT 1;
        ALTER TABLE brigade_contracts ALTER COLUMN company_id DROP NOT NULL;
        UPDATE brigade_contracts bc
           SET company_id=p.company_id
          FROM projects p
         WHERE bc.project_id=p.id
           AND p.company_id IS NOT NULL
           AND bc.company_id IS DISTINCT FROM p.company_id;
        UPDATE brigade_contracts bc
           SET company_id=project_scope.company_id,
               project_id=project_scope.project_id
          FROM (
              SELECT name, MIN(id) AS project_id, MIN(company_id) AS company_id
                FROM projects
               WHERE company_id IS NOT NULL
               GROUP BY name
              HAVING COUNT(*)=1
          ) project_scope
         WHERE NOT EXISTS (
                   SELECT 1 FROM projects exact_project
                   WHERE exact_project.id=bc.project_id
                     AND exact_project.company_id IS NOT NULL
               )
           AND bc.project_name=project_scope.name
           AND (bc.company_id IS DISTINCT FROM project_scope.company_id
                OR bc.project_id IS DISTINCT FROM project_scope.project_id);
        UPDATE brigade_contracts bc
           SET company_id=NULL
         WHERE bc.company_id IS NOT NULL
           AND NOT EXISTS (
                   SELECT 1 FROM projects p
                   WHERE p.id=bc.project_id
                     AND p.company_id=bc.company_id
               );
        CREATE INDEX IF NOT EXISTS idx_brigade_contracts_company_id ON brigade_contracts(company_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_brigade_contracts_company_project_id ON brigade_contracts(company_id,project_id);
        CREATE INDEX IF NOT EXISTS idx_brigade_contracts_company_project_name ON brigade_contracts(company_id,project_name);
        CREATE TABLE IF NOT EXISTS brigade_contract_items (
            id SERIAL PRIMARY KEY,
            contract_id INT,
            estimate_section VARCHAR(255),
            description VARCHAR(255),
            work_package VARCHAR(100) DEFAULT '',
            estimate_item_key VARCHAR(255) DEFAULT '',
            unit VARCHAR(50),
            quantity FLOAT DEFAULT 0,
            price_smeta NUMERIC(14,2) DEFAULT 0,
            price_brigade NUMERIC(14,2) DEFAULT 0,
            done_quantity FLOAT DEFAULT 0,
            status VARCHAR(50) DEFAULT 'Не начато'
        );
        CREATE TABLE IF NOT EXISTS brigade_payments (
            id SERIAL PRIMARY KEY,
            company_id INT,
            contract_id INT,
            project_payment_id INT,
            amount NUMERIC(14,2) DEFAULT 0,
            paid_by VARCHAR(255),
            paid_date DATE,
            note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE brigade_payments ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE brigade_payments ADD COLUMN IF NOT EXISTS project_payment_id INT;
        ALTER TABLE brigade_payments ALTER COLUMN company_id DROP DEFAULT;
        ALTER TABLE brigade_payments ALTER COLUMN company_id DROP NOT NULL;
        UPDATE brigade_payments bp
           SET company_id=bc.company_id
          FROM brigade_contracts bc
         WHERE bp.contract_id=bc.id
           AND bc.company_id IS NOT NULL
           AND bp.company_id IS DISTINCT FROM bc.company_id;
        UPDATE brigade_payments bp
           SET company_id=NULL
         WHERE bp.company_id IS NOT NULL
           AND NOT EXISTS (
                   SELECT 1 FROM brigade_contracts bc
                   WHERE bc.id=bp.contract_id
                     AND bc.company_id=bp.company_id
               );
        UPDATE brigade_payments
           SET company_id=NULL,
               project_payment_id=NULL
         WHERE (company_id IS NOT NULL OR project_payment_id IS NOT NULL)
           AND (
               amount IS NULL
               OR amount IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
           );
        DO $brigade_payment_constraint$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                  FROM pg_constraint
                 WHERE conname='chk_brigade_payments_finite_amount'
                   AND conrelid='brigade_payments'::regclass
            ) THEN
                ALTER TABLE brigade_payments
                    ADD CONSTRAINT chk_brigade_payments_finite_amount
                    CHECK (
                        company_id IS NULL
                        OR (
                            amount IS NOT NULL
                            AND amount NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
                        )
                    );
            END IF;
        END
        $brigade_payment_constraint$;
        CREATE INDEX IF NOT EXISTS idx_brigade_payments_company_id ON brigade_payments(company_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_brigade_payments_company_contract ON brigade_payments(company_id,contract_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_brigade_payments_project_payment
            ON brigade_payments(project_payment_id) WHERE project_payment_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS brigade_acts (
            id SERIAL PRIMARY KEY,
            contract_id INT,
            project_name VARCHAR(255),
            brigade_name VARCHAR(255),
            period_from VARCHAR(50),
            period_to VARCHAR(50),
            total_amount NUMERIC(14,2) DEFAULT 0,
            status VARCHAR(50) DEFAULT 'Черновик',
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS project_documents (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            side VARCHAR(20) DEFAULT 'customer',
            doc_type VARCHAR(100),
            number VARCHAR(100),
            doc_date DATE,
            counterparty VARCHAR(255),
            sign_status VARCHAR(40) DEFAULT 'Не подписан',
            scan_url TEXT,
            amount NUMERIC(14,2) DEFAULT 0,
            notes TEXT,
            uploaded_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS project_measurements (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            source_type VARCHAR(100) DEFAULT 'Фактический обмер',
	            doc_type VARCHAR(100) DEFAULT 'Обмер',
	            title VARCHAR(255),
	            file_url TEXT,
	            photo_url TEXT,
	            status VARCHAR(50) DEFAULT 'Черновик',
            rooms_created INT DEFAULT 0,
            notes TEXT,
            uploaded_by VARCHAR(255),
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
	        );
	        ALTER TABLE project_measurements ADD COLUMN IF NOT EXISTS photo_url TEXT;
	        CREATE INDEX IF NOT EXISTS idx_project_measurements_project ON project_measurements(project_name);
        CREATE INDEX IF NOT EXISTS idx_project_measurements_status ON project_measurements(status);
        CREATE TABLE IF NOT EXISTS measurement_room_drafts (
            id SERIAL PRIMARY KEY,
            measurement_id INT,
            project_name VARCHAR(255),
            name VARCHAR(255),
            floor INT DEFAULT 1,
            liter VARCHAR(100),
            room_type VARCHAR(100) DEFAULT 'Комната',
            floor_area FLOAT DEFAULT 0,
            wall_area FLOAT DEFAULT 0,
            ceiling_area FLOAT DEFAULT 0,
            height FLOAT DEFAULT 0,
            windows INT DEFAULT 0,
            doors INT DEFAULT 0,
            notes TEXT,
            status VARCHAR(50) DEFAULT 'Черновик ИИ',
            created_by VARCHAR(255),
            accepted_room_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_measurement_room_drafts_project ON measurement_room_drafts(project_name);
        CREATE INDEX IF NOT EXISTS idx_measurement_room_drafts_measurement ON measurement_room_drafts(measurement_id);
        CREATE INDEX IF NOT EXISTS idx_measurement_room_drafts_status ON measurement_room_drafts(status);
        CREATE TABLE IF NOT EXISTS project_letters (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            side VARCHAR(20) DEFAULT 'customer',
            direction VARCHAR(20) DEFAULT 'outgoing',
            subject VARCHAR(500),
            body TEXT,
            counterparty VARCHAR(255),
            letter_date DATE,
            file_url TEXT,
            author VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE project_letters ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Активно';
        CREATE TABLE IF NOT EXISTS estimates (
            id SERIAL PRIMARY KEY,
            project_id INT,
            project_name VARCHAR(255),
            name VARCHAR(255),
            version VARCHAR(50),
            sections_json TEXT,
            status VARCHAR(50) DEFAULT 'Черновик',
            is_template BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE estimates ADD COLUMN IF NOT EXISTS company_id INT;
        CREATE TABLE IF NOT EXISTS project_payments (
            id SERIAL PRIMARY KEY,
            company_id INT,
            company_scope_verified BOOLEAN NOT NULL DEFAULT TRUE,
            project_name VARCHAR(255),
            work_package VARCHAR(100) DEFAULT '',
            amount NUMERIC(14,2) DEFAULT 0,
            note TEXT,
            date VARCHAR(50),
            added_by VARCHAR(255),
            paid_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE project_payments ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE project_payments ADD COLUMN IF NOT EXISTS company_scope_verified BOOLEAN;
        ALTER TABLE project_payments ALTER COLUMN company_id DROP DEFAULT;
        ALTER TABLE project_payments ALTER COLUMN company_id DROP NOT NULL;
        UPDATE project_payments pp
           SET company_id=project_scope.company_id,
               company_scope_verified=TRUE
          FROM (
              SELECT name, MIN(company_id) AS company_id
                FROM projects
               WHERE company_id IS NOT NULL
               GROUP BY name
              HAVING COUNT(DISTINCT company_id)=1
          ) project_scope
         WHERE pp.company_scope_verified IS NULL
           AND pp.project_name=project_scope.name;
        UPDATE project_payments pp
           SET company_id=NULL,
               company_scope_verified=FALSE
         WHERE (
                   pp.company_scope_verified IS NULL
               AND NOT EXISTS (
                   SELECT 1
                     FROM (
                         SELECT name, MIN(company_id) AS company_id
                           FROM projects
                          WHERE company_id IS NOT NULL
                          GROUP BY name
                         HAVING COUNT(DISTINCT company_id)=1
                     ) project_scope
                    WHERE project_scope.name=pp.project_name
                      AND project_scope.company_id=pp.company_id
               ))
            OR (
                (pp.company_id IS NOT NULL OR pp.company_scope_verified IS DISTINCT FROM FALSE)
                AND (
                    pp.amount IS NULL
                    OR pp.amount IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
                )
            );
        UPDATE project_payments
           SET company_scope_verified=FALSE
         WHERE company_scope_verified IS NULL;
        ALTER TABLE project_payments ALTER COLUMN company_scope_verified SET DEFAULT TRUE;
        ALTER TABLE project_payments ALTER COLUMN company_scope_verified SET NOT NULL;
        DO $project_payment_constraint$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                  FROM pg_constraint
                 WHERE conname='chk_project_payments_verified_amount'
                   AND conrelid='project_payments'::regclass
            ) THEN
                ALTER TABLE project_payments
                    ADD CONSTRAINT chk_project_payments_verified_amount
                    CHECK (
                        company_scope_verified=FALSE
                        OR (
                            company_id IS NOT NULL
                            AND amount IS NOT NULL
                            AND amount NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
                        )
                    );
            END IF;
        END
        $project_payment_constraint$;
        ALTER TABLE project_payments ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT '';
        CREATE INDEX IF NOT EXISTS idx_project_payments_company_id ON project_payments(company_id,id DESC);
        CREATE INDEX IF NOT EXISTS idx_project_payments_company_project ON project_payments(company_id,project_name);
        WITH candidate_pairs AS (
            SELECT bp.id AS brigade_payment_id,
                   pp.id AS project_payment_id,
                   COUNT(*) OVER (PARTITION BY bp.id) AS project_candidates,
                   COUNT(*) OVER (PARTITION BY pp.id) AS brigade_candidates
              FROM brigade_payments bp
              JOIN brigade_contracts bc
                ON bc.id=bp.contract_id AND bc.company_id=bp.company_id
              JOIN (
                  SELECT name
                    FROM projects
                   WHERE company_id IS NOT NULL
                   GROUP BY name
                  HAVING COUNT(*)=1
              ) unique_project
                ON unique_project.name=bc.project_name
              JOIN project_payments pp
                ON pp.company_id=bp.company_id
               AND pp.company_scope_verified=TRUE
               AND pp.project_name=bc.project_name
               AND pp.amount=bp.amount
               AND COALESCE(pp.note,'')='Оплата бригаде ' || COALESCE(bc.brigade_name,'')
               AND COALESCE(pp.date::text,'')=COALESCE(bp.paid_date::text,'')
               AND COALESCE(pp.added_by,'')=COALESCE(bp.paid_by,'')
             WHERE bp.project_payment_id IS NULL
               AND bp.company_id IS NOT NULL
        )
        UPDATE brigade_payments bp
           SET project_payment_id=candidate_pairs.project_payment_id
          FROM candidate_pairs
         WHERE bp.id=candidate_pairs.brigade_payment_id
           AND candidate_pairs.project_candidates=1
           AND candidate_pairs.brigade_candidates=1;
        CREATE TABLE IF NOT EXISTS accountable_payments (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            given_to VARCHAR(255),
            given_to_id INT,
            amount NUMERIC(14,2) DEFAULT 0,
            payment_method VARCHAR(50),
            purpose TEXT,
            date VARCHAR(50),
            added_by VARCHAR(255),
            status VARCHAR(50) DEFAULT 'Выдан',
            spent_amount NUMERIC(14,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS accountable_expenses (
            id SERIAL PRIMARY KEY,
            payment_id INT,
            project_name VARCHAR(255),
            description TEXT,
            amount NUMERIC(14,2) DEFAULT 0,
            photo_url TEXT,
            date VARCHAR(50),
            added_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS own_expenses (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            employee_name VARCHAR(255),
            employee_id INT,
            description TEXT,
            amount NUMERIC(14,2) DEFAULT 0,
            photo_url TEXT,
            date VARCHAR(50),
            category VARCHAR(100),
            status VARCHAR(50) DEFAULT 'Ожидает',
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            project VARCHAR(255),
            category VARCHAR(100),
            amount NUMERIC(14,2) DEFAULT 0,
            note TEXT,
            date VARCHAR(50),
            added_by VARCHAR(255),
            photo_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE own_expenses ADD COLUMN IF NOT EXISTS category VARCHAR(100);
        ALTER TABLE own_expenses ADD COLUMN IF NOT EXISTS approved_by VARCHAR(255);
        ALTER TABLE own_expenses ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(100);
        ALTER TABLE own_expenses ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(100);
        ALTER TABLE own_expenses ADD COLUMN IF NOT EXISTS expense_id INT;
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS own_expense_id INT;
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS source VARCHAR(100);
        ALTER TABLE expenses ADD COLUMN IF NOT EXISTS photo_url TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_expenses_own_expense_id ON expenses(own_expense_id) WHERE own_expense_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS unexpected_works (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            description TEXT,
            unit VARCHAR(50),
            quantity FLOAT DEFAULT 0,
            price NUMERIC(14,2) DEFAULT 0,
            total NUMERIC(14,2) DEFAULT 0,
            added_by VARCHAR(255),
            added_by_role VARCHAR(50),
            status VARCHAR(50) DEFAULT 'На рассмотрении',
            approved_by VARCHAR(255),
            approved_at VARCHAR(50),
            notes TEXT,
            photo_url TEXT,
            project_id INT,
            company_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS change_type VARCHAR(80) DEFAULT 'Работа вне сметы';
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS estimate_id INT;
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS section_name VARCHAR(255);
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS estimate_item_name TEXT;
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS base_quantity NUMERIC(14,4);
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS new_required_quantity NUMERIC(14,4);
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS delta_quantity NUMERIC(14,4);
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS included_in_estimate_id INT;
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS reason TEXT;
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS project_id INT;
        ALTER TABLE unexpected_works ADD COLUMN IF NOT EXISTS company_id INT;
        CREATE INDEX IF NOT EXISTS idx_unexpected_works_project_id ON unexpected_works(project_id);
        CREATE INDEX IF NOT EXISTS idx_unexpected_works_company_id ON unexpected_works(company_id);
        UPDATE unexpected_works SET change_type='Работа вне сметы' WHERE change_type IS NULL OR change_type='';
        CREATE TABLE IF NOT EXISTS prescriptions (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            number VARCHAR(100),
            issued_by VARCHAR(255),
            issued_by_role VARCHAR(50),
            violation TEXT,
            deadline VARCHAR(50),
            responsible VARCHAR(255),
            status VARCHAR(50) DEFAULT 'Открыто',
            photo_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS project_stages (
            id SERIAL PRIMARY KEY,
            project_id INT,
            project_name VARCHAR(255),
            name VARCHAR(255),
            status VARCHAR(50) DEFAULT 'Не начат',
            start_date VARCHAR(50),
            end_date VARCHAR(50),
            progress INT DEFAULT 0,
            responsible VARCHAR(255),
            notes TEXT,
            order_num INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS project_checklists (
            id SERIAL PRIMARY KEY,
            project_id INT,
            project_name VARCHAR(255),
            name VARCHAR(255),
            template VARCHAR(100),
            status VARCHAR(50) DEFAULT 'Активен',
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS checklist_items (
            id SERIAL PRIMARY KEY,
            checklist_id INT,
            name VARCHAR(255),
            checked BOOLEAN DEFAULT FALSE,
            checked_by VARCHAR(255),
            checked_at VARCHAR(50),
            order_num INT DEFAULT 0
        );
        ALTER TABLE checklist_items ADD COLUMN IF NOT EXISTS checklist_id INT;
        ALTER TABLE checklist_items ADD COLUMN IF NOT EXISTS name VARCHAR(255);
        ALTER TABLE checklist_items ADD COLUMN IF NOT EXISTS checked BOOLEAN DEFAULT FALSE;
        ALTER TABLE checklist_items ADD COLUMN IF NOT EXISTS checked_by VARCHAR(255);
        ALTER TABLE checklist_items ADD COLUMN IF NOT EXISTS checked_at VARCHAR(50);
        ALTER TABLE checklist_items ADD COLUMN IF NOT EXISTS order_num INT DEFAULT 0;
        CREATE TABLE IF NOT EXISTS company_requisites (
            id SERIAL PRIMARY KEY,
            company_id INT DEFAULT 1,
            full_name VARCHAR(255),
            short_name VARCHAR(255),
            inn VARCHAR(20),
            kpp VARCHAR(20),
            ogrn VARCHAR(20),
            legal_address TEXT,
            actual_address TEXT,
            phone VARCHAR(50),
            email VARCHAR(255),
            director_name VARCHAR(255),
            director_position VARCHAR(100),
            basis VARCHAR(255),
            bank_name VARCHAR(255),
            bik VARCHAR(20),
            rs VARCHAR(40),
            ks VARCHAR(40)
        );
        ALTER TABLE company_requisites ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        UPDATE company_requisites SET company_id=1 WHERE company_id IS NULL;
        ALTER TABLE company_requisites ALTER COLUMN company_id SET DEFAULT 1;
        ALTER TABLE company_requisites ALTER COLUMN company_id SET NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_company_requisites_company ON company_requisites(company_id);
        CREATE TABLE IF NOT EXISTS company_documents (
            id SERIAL PRIMARY KEY,
            company_id INT,
            name VARCHAR(255),
            doc_type VARCHAR(100),
            file_url TEXT,
            expires_at VARCHAR(50),
            uploaded_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS project_chat (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            author_id INT,
            author_name VARCHAR(255),
            author_role VARCHAR(50),
            text TEXT,
            photo_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS room_doors (
            id SERIAL PRIMARY KEY,
            room_id INT,
            name VARCHAR(255),
            width FLOAT DEFAULT 0,
            height FLOAT DEFAULT 0,
            door_type VARCHAR(100),
            door_purpose VARCHAR(100),
            reveal_depth FLOAT DEFAULT 0,
            reveal_material VARCHAR(100),
            order_num INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS room_windows (
            id SERIAL PRIMARY KEY,
            room_id INT,
            name VARCHAR(255),
            width FLOAT DEFAULT 0,
            height FLOAT DEFAULT 0,
            window_type VARCHAR(100),
            reveal_depth FLOAT DEFAULT 0,
            reveal_material VARCHAR(100),
            order_num INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS warehouse_invoices (
            id SERIAL PRIMARY KEY,
            company_id INT DEFAULT 1,
            number VARCHAR(100),
            date VARCHAR(50),
            supplier_id INT,
            supplier_name VARCHAR(255),
            accepted_by VARCHAR(255),
            location VARCHAR(255),
            project VARCHAR(255),
            vat TEXT DEFAULT 'Без НДС',
            items TEXT,
            total_base NUMERIC(14,2) DEFAULT 0,
            total_vat NUMERIC(14,2) DEFAULT 0,
            total_with_vat NUMERIC(14,2) DEFAULT 0,
            status VARCHAR(50) DEFAULT 'Принято',
            added_by VARCHAR(255),
            photo_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS source_type VARCHAR(100);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS source_id INT;
        ALTER TABLE warehouse_invoices ALTER COLUMN source_id TYPE TEXT USING source_id::text;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS supply_delivery_id INT;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS supply_request_id INT;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS photo_urls TEXT;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS pages_count INT DEFAULT 1;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS warehouse_target VARCHAR(50);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS selected_action VARCHAR(100);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS material_match_json TEXT;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS accounting_status VARCHAR(100);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS accounting_comment TEXT;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS accounting_updated_by VARCHAR(255);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS accounting_updated_at TIMESTAMP;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS paid_amount NUMERIC(14,2) DEFAULT 0;
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS paid_at VARCHAR(50);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS paid_by VARCHAR(255);
        ALTER TABLE warehouse_invoices ADD COLUMN IF NOT EXISTS supplier_invoice_id INT;
        CREATE TABLE IF NOT EXISTS warehouses (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            city VARCHAR(255),
            address TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS salary_payments (
            id SERIAL PRIMARY KEY,
            staff_id INT,
            staff_name VARCHAR(255),
            month VARCHAR(7),
            amount NUMERIC(14,2) DEFAULT 0,
            paid_by VARCHAR(255),
            paid_date VARCHAR(50),
            note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS crm_leads (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(50),
            email VARCHAR(255),
            source VARCHAR(255),
            budget NUMERIC(14,2) DEFAULT 0,
	            notes TEXT,
	            stage VARCHAR(50) DEFAULT 'Новый',
	            project_id INT,
	            photo_url TEXT,
	            created_by VARCHAR(255),
	            created_at VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS work_journal (
            id SERIAL PRIMARY KEY,
            master_id INT,
            master_name VARCHAR(255),
            project VARCHAR(255),
            description VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT,
            price_per_unit FLOAT,
            total FLOAT,
            date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'На проверке',
            comment TEXT,
            photo_url VARCHAR(255),
            confirmed_by VARCHAR(255),
            confirmed_at VARCHAR(50)
        );
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS company_id INT;
        CREATE TABLE IF NOT EXISTS master_profiles (
            id SERIAL PRIMARY KEY,
            user_id INT UNIQUE,
            full_name VARCHAR(255),
            passport VARCHAR(255),
            inn VARCHAR(50),
            contract_type VARCHAR(50),
            bank_account VARCHAR(255),
            bank_name VARCHAR(255),
            phone VARCHAR(100),
            specialization VARCHAR(255),
            ogrnip VARCHAR(50),
            profile_completed BOOLEAN DEFAULT TRUE
        );
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS kpp VARCHAR(20);
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS ogrn VARCHAR(20);
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS legal_address TEXT;
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS bank_bik VARCHAR(20);
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS bank_corr VARCHAR(50);
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS signatory_name VARCHAR(255);
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS signatory_position VARCHAR(255);
        ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS signatory_basis VARCHAR(255);
        CREATE TABLE IF NOT EXISTS contracts (
            id SERIAL PRIMARY KEY,
            master_id INT,
            master_name VARCHAR(255),
            contract_type VARCHAR(50),
            contract_number VARCHAR(100),
            project VARCHAR(255),
            start_date VARCHAR(50),
            end_date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'Активен'
        );
        CREATE TABLE IF NOT EXISTS interim_acts (
            id SERIAL PRIMARY KEY,
            master_id INT,
            master_name VARCHAR(255),
            project VARCHAR(255),
            work_package VARCHAR(100) DEFAULT '',
            period_start VARCHAR(50),
            period_end VARCHAR(50),
            total_amount FLOAT DEFAULT 0,
            paid_amount FLOAT DEFAULT 0,
            contract_id INT,
            status VARCHAR(100) DEFAULT 'Новый',
            source_type VARCHAR(100) DEFAULT '',
            photo_urls TEXT DEFAULT '[]'
        );
        ALTER TABLE interim_acts ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE interim_acts ADD COLUMN IF NOT EXISTS scan_url TEXT;
        ALTER TABLE interim_acts ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT '';
        ALTER TABLE interim_acts ADD COLUMN IF NOT EXISTS work_journal_ids TEXT DEFAULT '[]';
        ALTER TABLE interim_acts ADD COLUMN IF NOT EXISTS source_type VARCHAR(100) DEFAULT '';
        ALTER TABLE interim_acts ADD COLUMN IF NOT EXISTS photo_urls TEXT DEFAULT '[]';
        CREATE TABLE IF NOT EXISTS timesheet (
            id SERIAL PRIMARY KEY,
            staff_id INT,
            day VARCHAR(10)
        );
        CREATE TABLE IF NOT EXISTS rooms (
            id SERIAL PRIMARY KEY,
            company_id INT,
            project_id INT,
            project VARCHAR(255),
            name VARCHAR(255),
            floor INT DEFAULT 1,
            liter VARCHAR(100),
            room_type VARCHAR(100) DEFAULT 'Комната',
            floor_area FLOAT DEFAULT 0,
            wall_area FLOAT DEFAULT 0,
            ceiling_area FLOAT DEFAULT 0,
            height FLOAT DEFAULT 0,
            ceiling_type VARCHAR(100),
            wall_material VARCHAR(100),
            floor_material VARCHAR(100),
	            windows INT DEFAULT 0,
	            doors INT DEFAULT 0,
	            photo_url TEXT,
	            notes TEXT
	        );
        CREATE TABLE IF NOT EXISTS room_works (
            id SERIAL PRIMARY KEY,
            room_id INT,
            project VARCHAR(255),
            room_name VARCHAR(255),
            master_id INT,
            master_name VARCHAR(255),
            description VARCHAR(255),
            surface VARCHAR(100),
            unit VARCHAR(50),
            quantity FLOAT,
            price_per_unit FLOAT DEFAULT 0,
            total FLOAT DEFAULT 0,
            date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'На проверке',
            photo_url VARCHAR(255),
            confirmed_by VARCHAR(255),
            work_journal_id INT,
            work_package VARCHAR(255),
            estimate_item_key VARCHAR(255)
        );
        ALTER TABLE room_works ADD COLUMN IF NOT EXISTS work_journal_id INT;
        ALTER TABLE room_works ADD COLUMN IF NOT EXISTS work_package VARCHAR(255);
        ALTER TABLE room_works ADD COLUMN IF NOT EXISTS estimate_item_key VARCHAR(255);
        CREATE TABLE IF NOT EXISTS tools (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            inventory_number VARCHAR(100),
            cost FLOAT DEFAULT 0,
            status VARCHAR(100) DEFAULT 'На складе',
            location VARCHAR(100) DEFAULT 'Основной склад',
            project VARCHAR(255),
            master_id INT,
            master_name VARCHAR(255),
            issue_type VARCHAR(100),
            photo_url VARCHAR(255),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS tool_history (
            id SERIAL PRIMARY KEY,
            tool_id INT,
            tool_name VARCHAR(255),
            action VARCHAR(100),
            from_location VARCHAR(255),
            to_location VARCHAR(255),
            master_name VARCHAR(255),
            project VARCHAR(255),
            issue_type VARCHAR(100),
            condition VARCHAR(100),
            date VARCHAR(50),
            created_by VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS warehouse_main (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT DEFAULT 0,
            price FLOAT DEFAULT 0,
            min_quantity FLOAT DEFAULT 0,
            category VARCHAR(255)
        );
        ALTER TABLE warehouse_main ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE warehouse_main ALTER COLUMN name TYPE TEXT;
        CREATE TABLE IF NOT EXISTS warehouse_movements (
            id SERIAL PRIMARY KEY,
            material_name VARCHAR(255),
            from_location VARCHAR(255),
            to_location VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50),
            work_package VARCHAR(255),
            date VARCHAR(50),
            created_by VARCHAR(255),
            notes TEXT
        );
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS work_package VARCHAR(255);
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS company_id INT DEFAULT 1;
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS source_invoice_id INT;
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS source_invoice_line_index INT;
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS estimate_control_status VARCHAR(50) NOT NULL DEFAULT 'not_checked';
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS estimate_control JSONB NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS estimate_review_task_id INT;
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS document_snapshot_json JSONB;
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS document_snapshot_hash CHAR(64);
        ALTER TABLE warehouse_movements ADD COLUMN IF NOT EXISTS document_snapshot_frozen_at TIMESTAMPTZ;
        UPDATE warehouse_movements SET company_id=1 WHERE company_id IS NULL;
        ALTER TABLE warehouse_movements ALTER COLUMN material_name TYPE TEXT;
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            project VARCHAR(255),
            date VARCHAR(50),
            created_by VARCHAR(255),
            status VARCHAR(100) DEFAULT 'Открыта',
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS inventory_items (
            id SERIAL PRIMARY KEY,
            inventory_id INT,
            material_name VARCHAR(255),
            unit VARCHAR(50),
            expected FLOAT,
            actual FLOAT,
            difference FLOAT,
            notes TEXT
        );
        ALTER TABLE work_journal ALTER COLUMN description TYPE TEXT;
        ALTER TABLE room_works ALTER COLUMN description TYPE TEXT;
        ALTER TABLE supplier_invoices ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE supply_requests ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE supply_deliveries ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE supply_claims ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE supply_history ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE supplier_catalog ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE material_transfers ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS to_user_id INT;
        ALTER TABLE inventory_items ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE brigade_contract_items ALTER COLUMN estimate_section TYPE TEXT;
        ALTER TABLE brigade_contract_items ALTER COLUMN description TYPE TEXT;
        ALTER TABLE brigade_contract_items ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT '';
        ALTER TABLE brigade_contract_items ADD COLUMN IF NOT EXISTS estimate_item_key VARCHAR(255) DEFAULT '';
        ALTER TABLE brigade_contract_items ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Не начато';
        CREATE TABLE IF NOT EXISTS pd_consents (
            id SERIAL PRIMARY KEY,
            user_id INT UNIQUE,
            signed_at VARCHAR(100),
            scan_url VARCHAR(255),
            uploaded_by VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS project_ai_summary (
            project_name VARCHAR(255) PRIMARY KEY,
            company_id INT,
            project_id INT,
            payload_hash VARCHAR(64),
            summary TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE project_ai_summary ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE project_ai_summary ADD COLUMN IF NOT EXISTS project_id INT;
        CREATE INDEX IF NOT EXISTS idx_project_ai_summary_company_id ON project_ai_summary(company_id);
        CREATE INDEX IF NOT EXISTS idx_project_ai_summary_project_id ON project_ai_summary(project_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_project_ai_summary_company_project
            ON project_ai_summary(company_id,project_id)
            WHERE company_id IS NOT NULL AND project_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS ai_findings (
            id SERIAL PRIMARY KEY,
            company_id INT,
            project_id INT,
            project_name VARCHAR(255),
            finding_type VARCHAR(100) DEFAULT 'rule',
            category VARCHAR(100) DEFAULT 'Общее',
            severity VARCHAR(50) DEFAULT 'Проверить',
            title TEXT,
            description TEXT,
            source VARCHAR(100) DEFAULT 'system_rules',
            linked_entity_type VARCHAR(100),
            linked_entity_id VARCHAR(100),
            suggested_action TEXT,
            assigned_role VARCHAR(100),
            assigned_to VARCHAR(255),
            status VARCHAR(50) DEFAULT 'Новое',
            dedupe_key VARCHAR(255),
            created_by VARCHAR(255),
            created_by_id INT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE ai_findings ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE ai_findings ADD COLUMN IF NOT EXISTS project_id INT;
        CREATE INDEX IF NOT EXISTS idx_ai_findings_company_id ON ai_findings(company_id);
        CREATE INDEX IF NOT EXISTS idx_ai_findings_project_id ON ai_findings(project_id);
        CREATE INDEX IF NOT EXISTS idx_ai_findings_owner_status ON ai_findings(company_id,project_id,status);
        CREATE INDEX IF NOT EXISTS idx_ai_findings_project ON ai_findings(project_name);
        CREATE INDEX IF NOT EXISTS idx_ai_findings_status ON ai_findings(status);
        CREATE INDEX IF NOT EXISTS idx_ai_findings_dedupe ON ai_findings(project_name, dedupe_key);
        CREATE TABLE IF NOT EXISTS ai_tasks (
            id SERIAL PRIMARY KEY,
            owner_scope TEXT,
            company_id INT,
            project_id INT,
            finding_id INT,
            project_name VARCHAR(255),
            title TEXT,
            description TEXT,
            assigned_role VARCHAR(100),
            assigned_to VARCHAR(255),
            status VARCHAR(50) DEFAULT 'Новое',
            due_date DATE,
            accepted_by VARCHAR(255),
            accepted_at TIMESTAMP,
            closed_by VARCHAR(255),
            closed_at TIMESTAMP,
            action_label VARCHAR(255),
            action_payload TEXT,
            dedupe_key VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT ck_ai_tasks_owner_scope CHECK (
                owner_scope IS NULL OR
                (owner_scope='company' AND company_id IS NOT NULL AND project_id IS NOT NULL) OR
                (owner_scope='platform' AND company_id IS NULL AND project_id IS NULL)
            )
        );
        ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS owner_scope TEXT;
        ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS project_id INT;
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_company_id ON ai_tasks(company_id);
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_project_id ON ai_tasks(project_id);
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_owner_status ON ai_tasks(owner_scope,company_id,project_id,status);
        ALTER TABLE ai_tasks ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(255);
        ALTER TABLE ai_findings ALTER COLUMN project_name TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN finding_type TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN category TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN severity TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN title TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN description TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN source TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN linked_entity_type TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN linked_entity_id TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN suggested_action TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN assigned_role TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN assigned_to TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN status TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN dedupe_key TYPE TEXT;
        ALTER TABLE ai_findings ALTER COLUMN created_by TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN project_name TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN title TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN description TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN assigned_role TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN assigned_to TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN status TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN action_label TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN action_payload TYPE TEXT;
        ALTER TABLE ai_tasks ALTER COLUMN dedupe_key TYPE TEXT;
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_project ON ai_tasks(project_name);
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_status ON ai_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_finding ON ai_tasks(finding_id);
        CREATE INDEX IF NOT EXISTS idx_ai_tasks_dedupe ON ai_tasks(project_name, dedupe_key);
        UPDATE ai_tasks t
        SET dedupe_key=f.dedupe_key
        FROM ai_findings f
        WHERE t.finding_id=f.id
          AND COALESCE(t.dedupe_key,'')=''
          AND COALESCE(f.dedupe_key,'')<>'';
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY project_name, dedupe_key
                       ORDER BY updated_at DESC NULLS LAST, id DESC
                   ) AS rn
            FROM ai_tasks
            WHERE COALESCE(dedupe_key,'')<>''
              AND status NOT IN ('Закрыто','Отклонено')
        )
        UPDATE ai_tasks t
        SET status='Закрыто',
            closed_by=COALESCE(NULLIF(t.closed_by,''),'system'),
            closed_at=COALESCE(t.closed_at,NOW()),
            updated_at=NOW()
        FROM ranked r
        WHERE t.id=r.id AND r.rn>1;
        CREATE TABLE IF NOT EXISTS material_norms (
            id SERIAL PRIMARY KEY,
            rule_key VARCHAR(100) UNIQUE,
            name VARCHAR(255),
            work_keywords TEXT,
            block_work_keywords TEXT,
            material_keywords TEXT,
            work_unit VARCHAR(50),
            material_unit VARCHAR(50),
            qty_per_unit NUMERIC(14,4) DEFAULT 0,
            thickness_base_mm NUMERIC(14,4),
            default_thickness_mm NUMERIC(14,4),
            label TEXT,
            active BOOLEAN DEFAULT TRUE,
            updated_by VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE material_norms ALTER COLUMN rule_key TYPE TEXT;
        ALTER TABLE material_norms ALTER COLUMN name TYPE TEXT;
        ALTER TABLE material_norms ALTER COLUMN work_unit TYPE TEXT;
        ALTER TABLE material_norms ALTER COLUMN material_unit TYPE TEXT;
        ALTER TABLE material_norms ALTER COLUMN updated_by TYPE TEXT;
        CREATE TABLE IF NOT EXISTS material_aliases (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            alias_name TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            canonical_unit VARCHAR(50),
            source VARCHAR(50) DEFAULT 'manual',
            active BOOLEAN DEFAULT TRUE,
            updated_by VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_material_aliases_project ON material_aliases(project_name);
        CREATE INDEX IF NOT EXISTS idx_material_aliases_alias ON material_aliases(alias_name);
        ALTER TABLE material_aliases ALTER COLUMN project_name TYPE TEXT;
        ALTER TABLE material_aliases ALTER COLUMN canonical_unit TYPE TEXT;
        ALTER TABLE material_aliases ALTER COLUMN source TYPE TEXT;
        ALTER TABLE material_aliases ALTER COLUMN updated_by TYPE TEXT;
        CREATE TABLE IF NOT EXISTS material_norm_overrides (
            id SERIAL PRIMARY KEY,
            base_norm_id INT,
            project_name VARCHAR(255),
            estimate_id INT,
            section_name TEXT,
            work_name TEXT,
            material_name TEXT,
            work_keywords TEXT,
            block_work_keywords TEXT,
            material_keywords TEXT,
            work_unit VARCHAR(50),
            material_unit VARCHAR(50),
            qty_per_unit NUMERIC(14,4) DEFAULT 0,
            thickness_base_mm NUMERIC(14,4),
            default_thickness_mm NUMERIC(14,4),
            label TEXT,
            reason TEXT,
            active BOOLEAN DEFAULT TRUE,
            updated_by VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_material_norm_overrides_project ON material_norm_overrides(project_name);
        CREATE INDEX IF NOT EXISTS idx_material_norm_overrides_estimate ON material_norm_overrides(estimate_id);
        ALTER TABLE material_norm_overrides ALTER COLUMN project_name TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN section_name TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN work_name TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN work_unit TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN material_unit TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN label TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN reason TYPE TEXT;
        ALTER TABLE material_norm_overrides ALTER COLUMN updated_by TYPE TEXT;
        CREATE TABLE IF NOT EXISTS material_norm_suggestions (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            suggestion_type VARCHAR(100) DEFAULT 'without_norm',
            status VARCHAR(50) DEFAULT 'Новая',
            severity VARCHAR(50) DEFAULT 'Проверить',
            work_name TEXT,
            section_name TEXT,
            work_unit VARCHAR(50),
            material_name TEXT,
            material_unit VARCHAR(50),
            current_norm_id INT,
            current_qty_per_unit NUMERIC(14,4),
            suggested_qty_per_unit NUMERIC(14,4),
            sample_count INT DEFAULT 0,
            actual_qty NUMERIC(14,4) DEFAULT 0,
            norm_qty NUMERIC(14,4) DEFAULT 0,
            confidence NUMERIC(5,2) DEFAULT 0,
            reason TEXT,
            ai_summary TEXT,
            work_keywords TEXT,
            material_keywords TEXT,
            block_work_keywords TEXT,
            label TEXT,
            source VARCHAR(100) DEFAULT 'rules',
            dedupe_key VARCHAR(255),
            created_by VARCHAR(255),
            applied_norm_id INT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE material_norm_suggestions ALTER COLUMN project_name TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN suggestion_type TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN status TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN severity TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN work_name TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN section_name TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN work_unit TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN material_name TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN material_unit TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN reason TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN ai_summary TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN work_keywords TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN material_keywords TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN block_work_keywords TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN label TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN source TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN dedupe_key TYPE TEXT;
        ALTER TABLE material_norm_suggestions ALTER COLUMN created_by TYPE TEXT;
        CREATE INDEX IF NOT EXISTS idx_material_norm_suggestions_project ON material_norm_suggestions(project_name);
        CREATE INDEX IF NOT EXISTS idx_material_norm_suggestions_status ON material_norm_suggestions(status);
        CREATE INDEX IF NOT EXISTS idx_material_norm_suggestions_dedupe ON material_norm_suggestions(dedupe_key);
        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS floor INT DEFAULT 1;
        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS liter VARCHAR(100);
        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS room_type VARCHAR(100) DEFAULT 'Комната';
        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS height FLOAT DEFAULT 0;
        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS ceiling_type VARCHAR(100);
	        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS wall_material VARCHAR(100);
	        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS floor_material VARCHAR(100);
	        ALTER TABLE rooms ADD COLUMN IF NOT EXISTS photo_url TEXT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS materials_used TEXT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS material_accounting_version SMALLINT NOT NULL DEFAULT 1;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS estimate_id INT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS section_name VARCHAR(255);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS responsible_itr VARCHAR(255);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS weather VARCHAR(255);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS time_start VARCHAR(10);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS time_end VARCHAR(10);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS hidden_work BOOLEAN DEFAULT FALSE;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS quality_status VARCHAR(50);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS normatives TEXT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS project_docs TEXT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS ai_filled BOOLEAN DEFAULT FALSE;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS unexpected_work_id INT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS work_package VARCHAR(255);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS room_id INT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS room_name VARCHAR(255);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS surface VARCHAR(100);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS estimate_item_name TEXT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS estimate_item_key VARCHAR(500);
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS contract_item_id INT;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS customer_price_per_unit FLOAT DEFAULT 0;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS customer_total FLOAT DEFAULT 0;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS execution_price_per_unit FLOAT DEFAULT 0;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS execution_total FLOAT DEFAULT 0;
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS execution_price_mode VARCHAR(100);
        CREATE TABLE IF NOT EXISTS material_inspection_journal (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            invoice_id INT,
            material_name VARCHAR(255),
            unit VARCHAR(50),
            quantity NUMERIC(14,4),
            supplier VARCHAR(255),
            batch_number VARCHAR(100),
            passport_number VARCHAR(100),
            certificate_number VARCHAR(100),
            test_protocol_number VARCHAR(100),
            visual_inspection_result VARCHAR(50),
            remarks TEXT,
            inspector_name VARCHAR(255),
            received_at DATE,
            inspected_at DATE,
            inspected BOOLEAN DEFAULT FALSE,
            normatives TEXT,
            ai_filled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS delivery_id INT;
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS work_package VARCHAR(100);
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS status VARCHAR(100) DEFAULT 'Активна';
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS warehouse_history_id INT;
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS source_type VARCHAR(100);
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS source_id INT;
        ALTER TABLE material_inspection_journal ADD COLUMN IF NOT EXISTS source_item_key VARCHAR(255);
        ALTER TABLE material_inspection_journal ALTER COLUMN material_name TYPE TEXT;
        CREATE INDEX IF NOT EXISTS idx_material_inspection_delivery_id ON material_inspection_journal(delivery_id);
        CREATE INDEX IF NOT EXISTS idx_material_inspection_invoice_id ON material_inspection_journal(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_material_inspection_source ON material_inspection_journal(source_type, source_id, source_item_key);
        CREATE TABLE IF NOT EXISTS supervisor_acts (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            act_number VARCHAR(100),
            act_type VARCHAR(100),
            description TEXT,
            findings TEXT,
            recommendations TEXT,
            issued_by VARCHAR(255),
            issued_by_role VARCHAR(50),
            date DATE,
            photo_url TEXT,
            file_url TEXT,
            status VARCHAR(50) DEFAULT 'Открыт',
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE prescriptions ADD COLUMN IF NOT EXISTS photo_url TEXT;
        CREATE TABLE IF NOT EXISTS cable_journal (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            invoice_id INT,
            cable_brand VARCHAR(255),
            cross_section NUMERIC(8,2),
            cores_count INT,
            length_received NUMERIC(10,2),
            length_installed NUMERIC(10,2),
            drum_number VARCHAR(100),
            manufacturer VARCHAR(255),
            supplier VARCHAR(255),
            certificate_number VARCHAR(100),
            passport_number VARCHAR(100),
            insulation_before NUMERIC(8,2),
            insulation_after NUMERIC(8,2),
            installation_location TEXT,
            installation_method VARCHAR(255),
            installed_at DATE,
            received_at DATE,
            responsible_itr VARCHAR(255),
            normatives TEXT,
            ai_filled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS delivery_id INT;
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS cable_type VARCHAR(100);
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS status VARCHAR(100) DEFAULT 'Активна';
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS work_package VARCHAR(100);
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS warehouse_history_id INT;
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS source_type VARCHAR(100);
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS source_id INT;
        ALTER TABLE cable_journal ADD COLUMN IF NOT EXISTS source_item_key VARCHAR(255);
        ALTER TABLE cable_journal ALTER COLUMN cable_brand TYPE TEXT;
        CREATE INDEX IF NOT EXISTS idx_cable_journal_delivery_id ON cable_journal(delivery_id);
        CREATE INDEX IF NOT EXISTS idx_cable_journal_invoice_id ON cable_journal(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_cable_journal_source ON cable_journal(source_type, source_id, source_item_key);
        ALTER TABLE estimates ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Черновик';
        ALTER TABLE estimates ADD COLUMN IF NOT EXISTS is_template BOOLEAN DEFAULT FALSE;
        ALTER TABLE estimates ADD COLUMN IF NOT EXISTS smeta_type VARCHAR(50) DEFAULT 'Заказчик';
        ALTER TABLE estimates ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT 'Основная';
        ALTER TABLE estimates ALTER COLUMN project_name TYPE TEXT;
        ALTER TABLE estimates ALTER COLUMN name TYPE TEXT;
        ALTER TABLE estimates ALTER COLUMN version TYPE TEXT;
        ALTER TABLE estimates ALTER COLUMN status TYPE TEXT;
        ALTER TABLE estimates ALTER COLUMN smeta_type TYPE TEXT;
        ALTER TABLE estimates ALTER COLUMN work_package TYPE TEXT;
        UPDATE estimates SET smeta_type='Заказчик' WHERE smeta_type IS NULL OR smeta_type='';
        UPDATE estimates SET work_package='Основная' WHERE work_package IS NULL OR work_package='';
        CREATE TABLE IF NOT EXISTS estimate_versions (
            id SERIAL PRIMARY KEY,
            estimate_id INT NOT NULL,
            version_label VARCHAR(100),
            sections_json TEXT,
            total NUMERIC(14,2) DEFAULT 0,
            comment TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE estimate_versions
            ADD COLUMN IF NOT EXISTS sections_sha256 VARCHAR(64);
        CREATE TABLE IF NOT EXISTS estimate_reconciliations (
            id SERIAL PRIMARY KEY,
            project_name TEXT,
            work_package TEXT DEFAULT 'Основная',
            smeta_type TEXT DEFAULT 'Заказчик',
            base_estimate_id INT NOT NULL,
            next_estimate_id INT NOT NULL,
            base_estimate_name TEXT,
            next_estimate_name TEXT,
            base_version TEXT,
            next_version TEXT,
            base_total NUMERIC(14,2) DEFAULT 0,
            next_total NUMERIC(14,2) DEFAULT 0,
            impact NUMERIC(14,2) DEFAULT 0,
            changed_count INT DEFAULT 0,
            added_count INT DEFAULT 0,
            removed_count INT DEFAULT 0,
            status TEXT DEFAULT 'Черновик',
            notes TEXT,
            created_by TEXT,
            approved_by TEXT,
            approved_at DATE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_estimate_reconciliations_project ON estimate_reconciliations(project_name);
        CREATE INDEX IF NOT EXISTS idx_estimate_reconciliations_estimates ON estimate_reconciliations(base_estimate_id, next_estimate_id);
        CREATE TABLE IF NOT EXISTS estimate_reconciliation_items (
            id SERIAL PRIMARY KEY,
            reconciliation_id INT NOT NULL REFERENCES estimate_reconciliations(id) ON DELETE CASCADE,
            item_type TEXT,
            section_name TEXT,
            item_name TEXT,
            unit TEXT,
            base_quantity NUMERIC(14,4) DEFAULT 0,
            next_quantity NUMERIC(14,4) DEFAULT 0,
            base_unit_price NUMERIC(14,4) DEFAULT 0,
            next_unit_price NUMERIC(14,4) DEFAULT 0,
            base_total NUMERIC(14,2) DEFAULT 0,
            next_total NUMERIC(14,2) DEFAULT 0,
            impact NUMERIC(14,2) DEFAULT 0,
            decision TEXT DEFAULT 'На проверке',
            confidence NUMERIC(6,4) DEFAULT 0,
            notes TEXT,
            old_row_json TEXT,
            new_row_json TEXT,
            unexpected_work_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_estimate_reconciliation_items_reconciliation ON estimate_reconciliation_items(reconciliation_id);
        CREATE TABLE IF NOT EXISTS estimate_chat_messages (
            id SERIAL PRIMARY KEY,
            estimate_id INT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS pricelist_id INT;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS middle_name VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS birth_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS citizenship VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS address TEXT;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS email_work VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS email_personal VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS phone_extra VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_series VARCHAR(10);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_number VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_issued_by VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_issued_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS inn VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS snils VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS specialization VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS category VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS employment_type VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS hired_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS fired_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS status VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS brigade VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_bik VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_corr VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS ogrnip VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS card_number VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS signature_url VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS notes TEXT;
        ALTER TABLE contracts ADD COLUMN IF NOT EXISTS status VARCHAR(100) DEFAULT 'Активен';
        ALTER TABLE pricelist_items ADD COLUMN IF NOT EXISTS item_type VARCHAR(20);
        ALTER TABLE pricelists ALTER COLUMN name TYPE TEXT;
        ALTER TABLE pricelists ALTER COLUMN description TYPE TEXT;
        ALTER TABLE pricelists ALTER COLUMN for_who TYPE TEXT;
        ALTER TABLE pricelist_items ALTER COLUMN name TYPE TEXT;
        ALTER TABLE pricelist_items ALTER COLUMN unit TYPE TEXT;
        ALTER TABLE pricelist_items ALTER COLUMN category TYPE TEXT;
        ALTER TABLE pricelist_items ALTER COLUMN specialization TYPE TEXT;
        ALTER TABLE pricelist_items ALTER COLUMN item_type TYPE TEXT;
        CREATE TABLE IF NOT EXISTS hidden_works_acts (
            id SERIAL PRIMARY KEY,
            project_name VARCHAR(255),
            estimate_id INT,
            act_number VARCHAR(100),
            work_name TEXT,
            section_name VARCHAR(255),
            work_package VARCHAR(100) DEFAULT '',
            brigade VARCHAR(255),
            quantity NUMERIC(14,4),
            unit VARCHAR(50),
            price_per_unit NUMERIC(14,2),
            total NUMERIC(14,2),
            work_date DATE,
            materials_used TEXT,
            project_docs TEXT,
            conclusion TEXT,
            signed_customer VARCHAR(255),
            signed_supervisor VARCHAR(255),
            signed_contractor VARCHAR(255),
            signed_subcontractor VARCHAR(255),
            signed_customer_at DATE,
            signed_supervisor_at DATE,
            signed_contractor_at DATE,
            signed_subcontractor_at DATE,
            photos TEXT,
            certificates TEXT,
            city VARCHAR(100),
            status VARCHAR(50) DEFAULT 'Черновик',
            comments TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE hidden_works_acts ALTER COLUMN section_name TYPE TEXT;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS company_id INT;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS signed_customer_at DATE;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS signed_supervisor_at DATE;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS signed_contractor_at DATE;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS signed_subcontractor_at DATE;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS photos TEXT;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS certificates TEXT;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS city VARCHAR(100);
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS ai_filled BOOLEAN DEFAULT FALSE;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS paid_status VARCHAR(50) DEFAULT 'Не оплачен';
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS paid_amount NUMERIC(14,2);
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS paid_at DATE;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS paid_by VARCHAR(255);
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS paid_note TEXT;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS work_journal_id INT;
        ALTER TABLE hidden_works_acts ADD COLUMN IF NOT EXISTS work_package VARCHAR(100) DEFAULT '';
        CREATE INDEX IF NOT EXISTS idx_hidden_works_work_journal_id ON hidden_works_acts(work_journal_id);
        CREATE TABLE IF NOT EXISTS staff_documents (
            id SERIAL PRIMARY KEY,
            staff_id INT NOT NULL,
            doc_type VARCHAR(50) NOT NULL,
            title VARCHAR(255),
            file_url VARCHAR(500),
            status VARCHAR(50) DEFAULT 'действует',
            signed_at DATE,
            expires_at DATE,
            notes TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE staff_documents ADD COLUMN IF NOT EXISTS signed_at DATE;
        ALTER TABLE staff_documents ADD COLUMN IF NOT EXISTS expires_at DATE;
        ALTER TABLE staff_documents ADD COLUMN IF NOT EXISTS notes TEXT;
    """
