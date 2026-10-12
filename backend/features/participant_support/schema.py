SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS participant_access_diagnostics (
 id UUID PRIMARY KEY,
 company_id INTEGER NOT NULL REFERENCES companies(id),
 platform_account_id INTEGER NOT NULL REFERENCES platform_accounts(id),
 reporter_id INTEGER NOT NULL REFERENCES users(id),
 participant_type TEXT NOT NULL CHECK(participant_type IN ('supplier','contractor','employee','brigade')),
 participant_id INTEGER NOT NULL,
 reason_code TEXT NOT NULL,
 context JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()+INTERVAL '1 hour',
 FOREIGN KEY(company_id,platform_account_id) REFERENCES companies(id,platform_account_id),
 UNIQUE(id,company_id,platform_account_id,reporter_id,participant_type,participant_id,reason_code)
);
CREATE INDEX IF NOT EXISTS participant_diagnostics_reporter ON participant_access_diagnostics(reporter_id,created_at);
CREATE TABLE IF NOT EXISTS participant_access_tickets (
 id BIGSERIAL PRIMARY KEY,
 diagnostic_id UUID NOT NULL UNIQUE REFERENCES participant_access_diagnostics(id),
 company_id INTEGER NOT NULL REFERENCES companies(id),
 platform_account_id INTEGER NOT NULL REFERENCES platform_accounts(id),
 reporter_id INTEGER NOT NULL REFERENCES users(id),
 participant_type TEXT NOT NULL,
 participant_id INTEGER NOT NULL,
 reason_code TEXT NOT NULL,
 comment TEXT NOT NULL CHECK(length(comment)<=2000),
 status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','in_progress','waiting','resolved','closed')),
 version INTEGER NOT NULL DEFAULT 1,
 result TEXT NOT NULL DEFAULT '' CHECK(length(result)<=2000),
 assigned_to INTEGER REFERENCES users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 FOREIGN KEY(diagnostic_id,company_id,platform_account_id,reporter_id,participant_type,participant_id,reason_code)
 REFERENCES participant_access_diagnostics(id,company_id,platform_account_id,reporter_id,participant_type,participant_id,reason_code)
);
CREATE INDEX IF NOT EXISTS participant_tickets_company ON participant_access_tickets(company_id,platform_account_id,id DESC);
CREATE INDEX IF NOT EXISTS participant_tickets_reporter ON participant_access_tickets(company_id,reporter_id,id DESC);
CREATE TABLE IF NOT EXISTS participant_access_ticket_events (
 id BIGSERIAL PRIMARY KEY,
 ticket_id BIGINT NOT NULL REFERENCES participant_access_tickets(id),
 actor_id INTEGER NOT NULL REFERENCES users(id),
 from_status TEXT,
 to_status TEXT NOT NULL,
 result TEXT NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE OR REPLACE FUNCTION participant_access_history_guard() RETURNS TRIGGER AS $$
BEGIN
 IF TG_OP='DELETE' OR TG_TABLE_NAME='participant_access_ticket_events' THEN
   RAISE EXCEPTION 'Preserve participant support history';
 END IF;
 IF (NEW.company_id,NEW.platform_account_id,NEW.reporter_id,NEW.participant_type,NEW.participant_id,NEW.reason_code,NEW.created_at)
    IS DISTINCT FROM
    (OLD.company_id,OLD.platform_account_id,OLD.reporter_id,OLD.participant_type,OLD.participant_id,OLD.reason_code,OLD.created_at) THEN
   RAISE EXCEPTION 'Participant support ownership is immutable';
 END IF;
 IF TG_TABLE_NAME='participant_access_diagnostics' THEN
   IF NEW.id<>OLD.id OR NEW.context IS DISTINCT FROM OLD.context THEN
     RAISE EXCEPTION 'Participant diagnostic evidence is immutable';
   END IF;
 ELSE
   IF NEW.id<>OLD.id OR NEW.diagnostic_id<>OLD.diagnostic_id OR NEW.comment<>OLD.comment THEN
     RAISE EXCEPTION 'Participant support provenance is immutable';
   END IF;
 END IF;
 RETURN NEW;
END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS participant_diagnostic_immutable ON participant_access_diagnostics;
CREATE TRIGGER participant_diagnostic_immutable BEFORE UPDATE OR DELETE ON participant_access_diagnostics
 FOR EACH ROW EXECUTE FUNCTION participant_access_history_guard();
DROP TRIGGER IF EXISTS participant_ticket_immutable ON participant_access_tickets;
CREATE TRIGGER participant_ticket_immutable BEFORE UPDATE OR DELETE ON participant_access_tickets
 FOR EACH ROW EXECUTE FUNCTION participant_access_history_guard();
DROP TRIGGER IF EXISTS participant_event_immutable ON participant_access_ticket_events;
CREATE TRIGGER participant_event_immutable BEFORE UPDATE OR DELETE ON participant_access_ticket_events
 FOR EACH ROW EXECUTE FUNCTION participant_access_history_guard();
"""
