SCHEMA_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS participant_ticket_exact_owner ON participant_access_tickets(id,company_id,platform_account_id);
CREATE TABLE IF NOT EXISTS participant_support_access (
 id UUID PRIMARY KEY,
 company_id INTEGER NOT NULL,
 platform_account_id INTEGER NOT NULL,
 ticket_id BIGINT NOT NULL,
 ticket_version INTEGER NOT NULL CHECK(ticket_version>0),
 assignee_id INTEGER NOT NULL REFERENCES users(id),
 assignee_epoch BIGINT NOT NULL,
 issuer_id INTEGER NOT NULL REFERENCES users(id),
 issuer_epoch BIGINT NOT NULL,
 action TEXT NOT NULL CHECK(action='diagnostic.read'),
 reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 5 AND 1000),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 expires_at TIMESTAMPTZ NOT NULL,
 revoked_at TIMESTAMPTZ,
 revoked_by INTEGER REFERENCES users(id),
 revoke_reason TEXT,
 FOREIGN KEY(ticket_id,company_id,platform_account_id) REFERENCES participant_access_tickets(id,company_id,platform_account_id),
 UNIQUE(id,company_id,platform_account_id,ticket_id),
 CHECK(expires_at>created_at AND expires_at<=created_at+INTERVAL '1 day'),
 CHECK((revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL) OR
       (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND length(trim(revoke_reason)) BETWEEN 5 AND 1000))
);
CREATE INDEX IF NOT EXISTS participant_support_access_company ON participant_support_access(company_id,ticket_id,created_at DESC);
CREATE INDEX IF NOT EXISTS participant_support_access_assignee ON participant_support_access(assignee_id,expires_at) WHERE revoked_at IS NULL;
CREATE TABLE IF NOT EXISTS participant_support_access_events (
 id BIGSERIAL PRIMARY KEY,
 access_id UUID NOT NULL,
 company_id INTEGER NOT NULL,
 platform_account_id INTEGER NOT NULL,
 ticket_id BIGINT NOT NULL,
 actor_id INTEGER NOT NULL REFERENCES users(id),
 action TEXT NOT NULL CHECK(action IN ('granted','listed','diagnostic.read','revoked')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(access_id,company_id,platform_account_id,ticket_id) REFERENCES participant_support_access(id,company_id,platform_account_id,ticket_id)
);
CREATE INDEX IF NOT EXISTS participant_support_access_history ON participant_support_access_events(access_id,id DESC);
CREATE OR REPLACE FUNCTION participant_support_access_guard() RETURNS trigger AS $$
BEGIN
 IF TG_OP='DELETE' OR TG_TABLE_NAME='participant_support_access_events' THEN
   RAISE EXCEPTION 'Preserve support access history';
 END IF;
 IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL OR
    (to_jsonb(NEW)-ARRAY['revoked_at','revoked_by','revoke_reason']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['revoked_at','revoked_by','revoke_reason']) THEN
   RAISE EXCEPTION 'Support authority is immutable';
 END IF;
 RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS participant_support_access_immutable ON participant_support_access;
CREATE TRIGGER participant_support_access_immutable BEFORE UPDATE OR DELETE ON participant_support_access
 FOR EACH ROW EXECUTE FUNCTION participant_support_access_guard();
DROP TRIGGER IF EXISTS participant_support_access_event_immutable ON participant_support_access_events;
CREATE TRIGGER participant_support_access_event_immutable BEFORE UPDATE OR DELETE ON participant_support_access_events
 FOR EACH ROW EXECUTE FUNCTION participant_support_access_guard();
"""
