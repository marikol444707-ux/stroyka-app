"""Explicit new manual contracts only; historical identities are never backfilled."""

SCHEMA_SQL = """
CREATE TABLE manual_brigade_contract_origins (
    contract_id INTEGER PRIMARY KEY REFERENCES brigade_contracts(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    request_id UUID NOT NULL,
    command_hash TEXT NOT NULL CHECK (command_hash ~ '^[0-9a-f]{64}$'),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, request_id)
);
CREATE FUNCTION guard_manual_brigade_origin() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Manual contract origin is immutable';
    END IF;
    PERFORM 1 FROM brigade_contracts bc JOIN projects p ON p.id=bc.project_id
        WHERE bc.id=NEW.contract_id AND bc.company_id=NEW.company_id
          AND bc.project_id=NEW.project_id AND p.company_id=NEW.company_id
          AND bc.contractor_id IS NULL AND bc.status='Черновик'
          AND bc.party_snapshot_json IS NULL AND bc.party_snapshot_hash IS NULL
        FOR UPDATE OF bc;
    IF NOT FOUND THEN RAISE EXCEPTION 'Manual contract scope is unverified'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER manual_brigade_origin_guard BEFORE INSERT OR UPDATE OR DELETE
    ON manual_brigade_contract_origins FOR EACH ROW EXECUTE FUNCTION guard_manual_brigade_origin();
CREATE FUNCTION guard_manual_brigade_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM manual_brigade_contract_origins o WHERE o.contract_id=OLD.id)
       AND (NEW.id IS DISTINCT FROM OLD.id OR NEW.company_id IS DISTINCT FROM OLD.company_id
            OR NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.contractor_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Manual contract identity requires an explicit linking workflow';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER manual_brigade_identity_guard BEFORE UPDATE ON brigade_contracts
    FOR EACH ROW EXECUTE FUNCTION guard_manual_brigade_identity();
"""

DOWNGRADE_SQL = """
LOCK TABLE manual_brigade_contract_origins IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM manual_brigade_contract_origins) THEN
        RAISE EXCEPTION 'Preserve manual contract origins';
    END IF;
END $$;
DROP TRIGGER manual_brigade_identity_guard ON brigade_contracts;
DROP FUNCTION guard_manual_brigade_identity();
DROP TABLE manual_brigade_contract_origins;
DROP FUNCTION guard_manual_brigade_origin();
"""
