"""Add platform licensor profiles and client contracts.

Revision ID: 0005_platform_client_contracts
Revises: 0004_active_estimate_snapshots
Create Date: 2026-09-01
"""

from alembic import op


revision = "0005_platform_client_contracts"
down_revision = "0004_active_estimate_snapshots"
branch_labels = None
depends_on = None


_CREATE_LICENSOR_PROFILES = """
CREATE TABLE IF NOT EXISTS public.platform_licensor_profiles (
    id SERIAL PRIMARY KEY,
    platform_account_id INTEGER NOT NULL,
    legal_form VARCHAR(30) NOT NULL DEFAULT 'individual_entrepreneur',
    legal_name VARCHAR(500) NOT NULL,
    short_name VARCHAR(255),
    inn VARCHAR(12),
    kpp VARCHAR(9),
    ogrn VARCHAR(15),
    ogrnip VARCHAR(15),
    legal_address TEXT,
    phone VARCHAR(100),
    email VARCHAR(255),
    settlement_account VARCHAR(20),
    bank_name VARCHAR(500),
    bank_bik VARCHAR(9),
    correspondent_account VARCHAR(20),
    signatory_name VARCHAR(255),
    signatory_basis VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

_CREATE_CONTRACTS = """
CREATE TABLE IF NOT EXISTS public.platform_client_contracts (
    id SERIAL PRIMARY KEY,
    platform_account_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    licensor_profile_id INTEGER NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_fingerprint VARCHAR(64) NOT NULL,
    contract_type VARCHAR(50) NOT NULL DEFAULT 'platform_license',
    number VARCHAR(100) NOT NULL,
    contract_date DATE NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE,
    plan VARCHAR(50) NOT NULL,
    monthly_fee NUMERIC(14,2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
    max_projects INTEGER,
    max_users INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    terms_version VARCHAR(50),
    licensor_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    client_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    terms_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_file_url TEXT,
    signed_file_url TEXT,
    notes TEXT,
    issued_at TIMESTAMP,
    activated_at TIMESTAMP,
    terminated_at TIMESTAMP,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

_INDEXES = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_id_platform_account
ON public.companies (id, platform_account_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_licensor_profiles_id_account
ON public.platform_licensor_profiles (id, platform_account_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_licensor_profiles_active_account
ON public.platform_licensor_profiles (platform_account_id)
WHERE active IS TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_client_contracts_id_company
ON public.platform_client_contracts (id, company_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_client_contracts_number
ON public.platform_client_contracts (platform_account_id, number);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_client_contracts_idempotency
ON public.platform_client_contracts (platform_account_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_platform_client_contracts_company_status
ON public.platform_client_contracts (company_id, status, starts_on, ends_on);
"""

_CONTRACT_CHECKS = """
DO $platform_client_contract_checks$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='chk_platform_client_contracts_status'
      AND conrelid='public.platform_client_contracts'::regclass
) THEN
    ALTER TABLE public.platform_client_contracts
    ADD CONSTRAINT chk_platform_client_contracts_status
    CHECK (status IN (
        'draft', 'issued', 'active', 'expired', 'terminated', 'cancelled'
    ));
END IF;
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='chk_platform_client_contracts_dates'
      AND conrelid='public.platform_client_contracts'::regclass
) THEN
    ALTER TABLE public.platform_client_contracts
    ADD CONSTRAINT chk_platform_client_contracts_dates
    CHECK (ends_on IS NULL OR ends_on >= starts_on);
END IF;
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='chk_platform_client_contracts_terms'
      AND conrelid='public.platform_client_contracts'::regclass
) THEN
    ALTER TABLE public.platform_client_contracts
    ADD CONSTRAINT chk_platform_client_contracts_terms
    CHECK (
        monthly_fee >= 0
        AND monthly_fee NOT IN (
            'NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric
        )
        AND currency ~ '^[A-Z]{3}$'
        AND request_fingerprint ~ '^[0-9a-f]{64}$'
        AND (max_projects IS NULL OR max_projects >= 0)
        AND (max_users IS NULL OR max_users >= 0)
        AND jsonb_typeof(licensor_snapshot_json) = 'object'
        AND jsonb_typeof(client_snapshot_json) = 'object'
        AND jsonb_typeof(terms_snapshot_json) = 'object'
    );
END IF;
END $platform_client_contract_checks$
"""

_OWNER_FOREIGN_KEYS = """
DO $platform_client_contract_owner_fks$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_platform_licensor_profiles_account'
      AND conrelid='public.platform_licensor_profiles'::regclass
) THEN
    ALTER TABLE public.platform_licensor_profiles
    ADD CONSTRAINT fk_platform_licensor_profiles_account
    FOREIGN KEY (platform_account_id)
    REFERENCES public.platform_accounts(id);
END IF;
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_platform_client_contracts_company_account'
      AND conrelid='public.platform_client_contracts'::regclass
) THEN
    ALTER TABLE public.platform_client_contracts
    ADD CONSTRAINT fk_platform_client_contracts_company_account
    FOREIGN KEY (company_id, platform_account_id)
    REFERENCES public.companies(id, platform_account_id);
END IF;
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_platform_client_contracts_licensor_account'
      AND conrelid='public.platform_client_contracts'::regclass
) THEN
    ALTER TABLE public.platform_client_contracts
    ADD CONSTRAINT fk_platform_client_contracts_licensor_account
    FOREIGN KEY (licensor_profile_id, platform_account_id)
    REFERENCES public.platform_licensor_profiles(id, platform_account_id);
END IF;
END $platform_client_contract_owner_fks$
"""

_ADD_DOCUMENT_LINKS = """
ALTER TABLE public.platform_billing_documents
ADD COLUMN IF NOT EXISTS client_contract_id INTEGER;

ALTER TABLE public.company_payments
ADD COLUMN IF NOT EXISTS client_contract_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_platform_billing_documents_client_contract
ON public.platform_billing_documents (client_contract_id)
WHERE client_contract_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_company_payments_client_contract
ON public.company_payments (client_contract_id)
WHERE client_contract_id IS NOT NULL;
"""

_DOCUMENT_FOREIGN_KEYS = """
DO $platform_client_contract_document_fks$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_platform_billing_documents_client_contract_company'
      AND conrelid='public.platform_billing_documents'::regclass
) THEN
    ALTER TABLE public.platform_billing_documents
    ADD CONSTRAINT fk_platform_billing_documents_client_contract_company
    FOREIGN KEY (client_contract_id, company_id)
    REFERENCES public.platform_client_contracts(id, company_id);
END IF;
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_company_payments_client_contract_company'
      AND conrelid='public.company_payments'::regclass
) THEN
    ALTER TABLE public.company_payments
    ADD CONSTRAINT fk_company_payments_client_contract_company
    FOREIGN KEY (client_contract_id, company_id)
    REFERENCES public.platform_client_contracts(id, company_id);
END IF;
END $platform_client_contract_document_fks$
"""

_DOWNGRADE_EMPTY_GUARD = """
DO $platform_client_contract_downgrade_guard$ BEGIN
IF to_regclass('public.platform_client_contracts') IS NOT NULL
   AND EXISTS (SELECT 1 FROM public.platform_client_contracts LIMIT 1) THEN
    RAISE EXCEPTION 'platform_client_contracts is not empty';
END IF;
IF to_regclass('public.platform_licensor_profiles') IS NOT NULL
   AND EXISTS (SELECT 1 FROM public.platform_licensor_profiles LIMIT 1) THEN
    RAISE EXCEPTION 'platform_licensor_profiles is not empty';
END IF;
END $platform_client_contract_downgrade_guard$
"""


def upgrade() -> None:
    op.execute(_CREATE_LICENSOR_PROFILES)
    op.execute(_CREATE_CONTRACTS)
    op.execute(_INDEXES)
    op.execute(_CONTRACT_CHECKS)
    op.execute(_OWNER_FOREIGN_KEYS)
    op.execute(_ADD_DOCUMENT_LINKS)
    op.execute(_DOCUMENT_FOREIGN_KEYS)


def downgrade() -> None:
    op.execute(_DOWNGRADE_EMPTY_GUARD)
    op.execute(
        "ALTER TABLE public.platform_billing_documents "
        "DROP CONSTRAINT IF EXISTS "
        "fk_platform_billing_documents_client_contract_company"
    )
    op.execute(
        "ALTER TABLE public.company_payments "
        "DROP CONSTRAINT IF EXISTS "
        "fk_company_payments_client_contract_company"
    )
    op.execute(
        "DROP INDEX IF EXISTS "
        "public.idx_platform_billing_documents_client_contract"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.idx_company_payments_client_contract"
    )
    op.execute(
        "ALTER TABLE public.platform_billing_documents "
        "DROP COLUMN IF EXISTS client_contract_id"
    )
    op.execute(
        "ALTER TABLE public.company_payments "
        "DROP COLUMN IF EXISTS client_contract_id"
    )
    op.execute("DROP TABLE IF EXISTS public.platform_client_contracts")
    op.execute("DROP TABLE IF EXISTS public.platform_licensor_profiles")
    op.execute("DROP INDEX IF EXISTS public.uq_companies_id_platform_account")
