SCHEMA_SQL = """
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS participant_owner_epoch BIGINT NOT NULL DEFAULT 0;
CREATE OR REPLACE FUNCTION supplier_participant_owner_epoch() RETURNS trigger AS $$
BEGIN
 IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
   NEW.participant_owner_epoch := OLD.participant_owner_epoch+1;
 ELSE NEW.participant_owner_epoch := OLD.participant_owner_epoch;
 END IF;
 RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS supplier_participant_owner_change ON suppliers;
CREATE TRIGGER supplier_participant_owner_change BEFORE UPDATE ON suppliers
 FOR EACH ROW EXECUTE FUNCTION supplier_participant_owner_epoch();
CREATE TABLE IF NOT EXISTS supplier_buyer_connection_requests (
 id UUID PRIMARY KEY,
 company_id INTEGER NOT NULL,
 platform_account_id INTEGER NOT NULL,
 source_supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
 target_supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
 source_version INTEGER NOT NULL CHECK(source_version>0),
 owner_user_id INTEGER NOT NULL REFERENCES users(id),
 owner_epoch BIGINT NOT NULL,
 target_owner_epoch BIGINT NOT NULL,
 created_by_user_id INTEGER NOT NULL REFERENCES users(id),
 issuer_epoch BIGINT NOT NULL,
 operation_key UUID NOT NULL,
 evidence JSONB NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','revoked')),
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()+INTERVAL '2 days',
 decided_at TIMESTAMPTZ,
 decided_by_user_id INTEGER REFERENCES users(id),
 FOREIGN KEY(company_id,platform_account_id) REFERENCES companies(id,platform_account_id),
 FOREIGN KEY(company_id,source_supplier_id) REFERENCES company_supplier_links(company_id,supplier_id),
 CHECK(source_supplier_id<>target_supplier_id),
 CHECK((status='pending' AND decided_at IS NULL AND decided_by_user_id IS NULL)
    OR (status<>'pending' AND decided_at IS NOT NULL AND decided_by_user_id IS NOT NULL)),
 UNIQUE(company_id,created_by_user_id,operation_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS supplier_buyer_connection_pending
 ON supplier_buyer_connection_requests(company_id,target_supplier_id) WHERE status='pending';
CREATE INDEX IF NOT EXISTS supplier_buyer_connection_company
 ON supplier_buyer_connection_requests(company_id,source_supplier_id,created_at DESC,id);
CREATE INDEX IF NOT EXISTS supplier_buyer_connection_owner
 ON supplier_buyer_connection_requests(owner_user_id,created_at DESC,id) WHERE status='pending';
CREATE OR REPLACE FUNCTION supplier_buyer_connection_guard() RETURNS trigger AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Preserve buyer connection history'; END IF;
 IF (to_jsonb(NEW)-ARRAY['status','version','decided_at','decided_by_user_id']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['status','version','decided_at','decided_by_user_id']) THEN
   RAISE EXCEPTION 'Buyer connection evidence is immutable';
 END IF;
 IF OLD.status<>'pending' OR NEW.status='pending' OR NEW.version<>OLD.version+1 THEN
   RAISE EXCEPTION 'Buyer connection decision is final';
 END IF;
 RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS supplier_buyer_connection_immutable ON supplier_buyer_connection_requests;
CREATE TRIGGER supplier_buyer_connection_immutable BEFORE UPDATE OR DELETE ON supplier_buyer_connection_requests
 FOR EACH ROW EXECUTE FUNCTION supplier_buyer_connection_guard();
"""
