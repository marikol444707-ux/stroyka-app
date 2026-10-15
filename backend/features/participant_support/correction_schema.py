"""Immutable, company-owned plans and results; no business backfill."""
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS supplier_connection_correction_plans (
 id UUID PRIMARY KEY,
 connection_request_id UUID NOT NULL REFERENCES supplier_buyer_connection_requests(id),
 company_id INTEGER NOT NULL,
 platform_account_id INTEGER NOT NULL,
 source_supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
 target_supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
 target_link_id INTEGER NOT NULL REFERENCES company_supplier_links(id),
 actor_id INTEGER NOT NULL REFERENCES users(id),
 actor_epoch BIGINT NOT NULL,
 owner_id INTEGER NOT NULL REFERENCES users(id),
 owner_epoch BIGINT NOT NULL,
 target_owner_epoch BIGINT NOT NULL,
 operation_id UUID NOT NULL,
 manifest JSONB NOT NULL CHECK(jsonb_typeof(manifest)='object'),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 expires_at TIMESTAMPTZ NOT NULL,
 applied_at TIMESTAMPTZ,
 reason TEXT,
 result JSONB,
 FOREIGN KEY(company_id,platform_account_id) REFERENCES companies(id,platform_account_id),
 FOREIGN KEY(company_id,source_supplier_id) REFERENCES company_supplier_links(company_id,supplier_id),
 FOREIGN KEY(company_id,target_supplier_id) REFERENCES company_supplier_links(company_id,supplier_id),
 CHECK(source_supplier_id<>target_supplier_id),
 CHECK(expires_at>created_at AND expires_at<=created_at+INTERVAL '15 minutes'),
 CHECK((applied_at IS NULL AND reason IS NULL AND result IS NULL) OR
       (applied_at IS NOT NULL AND reason IS NOT NULL AND result IS NOT NULL
        AND length(trim(reason)) BETWEEN 10 AND 1000 AND jsonb_typeof(result)='object')),
 UNIQUE(company_id,actor_id,operation_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS supplier_connection_one_correction
 ON supplier_connection_correction_plans(connection_request_id) WHERE applied_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS supplier_connection_correction_company
 ON supplier_connection_correction_plans(company_id,connection_request_id,created_at DESC);
CREATE OR REPLACE FUNCTION supplier_connection_correction_guard() RETURNS trigger AS $$
BEGIN
 IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Preserve connection correction evidence'; END IF;
 IF OLD.applied_at IS NOT NULL OR NEW.applied_at IS NULL OR
    (to_jsonb(NEW)-ARRAY['applied_at','reason','result']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['applied_at','reason','result']) THEN
   RAISE EXCEPTION 'Connection correction evidence is immutable';
 END IF;
 RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS supplier_connection_correction_immutable ON supplier_connection_correction_plans;
CREATE TRIGGER supplier_connection_correction_immutable BEFORE UPDATE OR DELETE ON supplier_connection_correction_plans
 FOR EACH ROW EXECUTE FUNCTION supplier_connection_correction_guard();
DROP TRIGGER IF EXISTS supplier_connection_correction_no_truncate ON supplier_connection_correction_plans;
CREATE TRIGGER supplier_connection_correction_no_truncate BEFORE TRUNCATE ON supplier_connection_correction_plans
 FOR EACH STATEMENT EXECUTE FUNCTION supplier_connection_correction_guard();
"""
