"""Append-only refusals; unknown probes belong to the platform, not a buyer."""
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS participant_support_denials (
 id BIGSERIAL PRIMARY KEY,
 actor_id INTEGER NOT NULL REFERENCES users(id),
 surface TEXT NOT NULL CHECK(surface IN ('business','file','job','diagnostic')),
 method TEXT NOT NULL CHECK(method IN ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS','OTHER')),
 status_code INTEGER NOT NULL CHECK(status_code IN (403,404)),
 access_id UUID,
 company_id INTEGER,
 platform_account_id INTEGER,
 ticket_id BIGINT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 CHECK((access_id IS NULL AND company_id IS NULL AND platform_account_id IS NULL AND ticket_id IS NULL) OR
       (access_id IS NOT NULL AND company_id IS NOT NULL AND platform_account_id IS NOT NULL AND ticket_id IS NOT NULL)),
 FOREIGN KEY(access_id,company_id,platform_account_id,ticket_id)
   REFERENCES participant_support_access(id,company_id,platform_account_id,ticket_id)
);
CREATE INDEX IF NOT EXISTS participant_support_denials_access ON participant_support_denials(access_id,id DESC);
CREATE INDEX IF NOT EXISTS participant_support_denials_actor ON participant_support_denials(actor_id,id DESC);
CREATE OR REPLACE FUNCTION participant_support_denial_guard() RETURNS trigger AS $$
BEGIN
 RAISE EXCEPTION 'Preserve support refusal history';
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS participant_support_denial_immutable ON participant_support_denials;
CREATE TRIGGER participant_support_denial_immutable BEFORE UPDATE OR DELETE ON participant_support_denials
 FOR EACH ROW EXECUTE FUNCTION participant_support_denial_guard();
DROP TRIGGER IF EXISTS participant_support_denial_no_truncate ON participant_support_denials;
CREATE TRIGGER participant_support_denial_no_truncate BEFORE TRUNCATE ON participant_support_denials
 FOR EACH STATEMENT EXECUTE FUNCTION participant_support_denial_guard();
"""
