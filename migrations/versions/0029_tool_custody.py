"""Append-only tool custody and contractual responsibility; no historical attribution."""
from alembic import op

revision = '0029_tool_custody'
down_revision = '0028_work_acceptance'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE tools ADD COLUMN custody_version BIGINT NOT NULL DEFAULT 0')
    op.execute('ALTER TABLE tools ADD COLUMN custody_contract_id INTEGER REFERENCES brigade_contracts(id)')
    op.execute('CREATE UNIQUE INDEX tools_owner_identity ON tools(id,company_id)')
    op.execute('''CREATE TABLE tool_custody_events (
        id BIGSERIAL PRIMARY KEY, tool_id INTEGER NOT NULL, company_id INTEGER NOT NULL,
        project_id INTEGER REFERENCES projects(id), holder_id INTEGER REFERENCES users(id),
        contract_id INTEGER REFERENCES brigade_contracts(id), operation_id BIGINT NOT NULL UNIQUE,
        actor_id INTEGER NOT NULL REFERENCES users(id), actor_name TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('issue','return','repair','recover','write_off','archive','reconcile')),
        condition TEXT NOT NULL, reason TEXT NOT NULL,
        before_state JSONB NOT NULL, after_state JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        FOREIGN KEY(tool_id,company_id) REFERENCES tools(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('CREATE INDEX tool_custody_history ON tool_custody_events(company_id,tool_id,id)')
    op.execute('''CREATE TABLE tool_incidents (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, tool_id INTEGER NOT NULL,
        event_id BIGINT NOT NULL UNIQUE, project_id INTEGER NOT NULL REFERENCES projects(id),
        holder_id INTEGER NOT NULL REFERENCES users(id), contract_id INTEGER REFERENCES brigade_contracts(id),
        kind TEXT NOT NULL CHECK(kind IN ('damaged','lost')), reason TEXT NOT NULL,
        tool_name TEXT NOT NULL, holder_name TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        FOREIGN KEY(tool_id,company_id) REFERENCES tools(id,company_id),
        FOREIGN KEY(event_id,company_id) REFERENCES tool_custody_events(id,company_id))''')
    op.execute('''CREATE TABLE tool_incident_decisions (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, incident_id BIGINT NOT NULL,
        operation_id BIGINT NOT NULL UNIQUE, actor_id INTEGER NOT NULL REFERENCES users(id),
        decision TEXT NOT NULL CHECK(decision IN ('confirmed','disputed','cancelled')),
        reason TEXT NOT NULL CHECK(length(trim(reason))>0), amount NUMERIC(14,2) NOT NULL,
        price_evidence TEXT NOT NULL, contract_evidence TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        CHECK((decision='confirmed' AND amount>0 AND length(trim(price_evidence))>0
               AND length(trim(contract_evidence))>0) OR (decision<>'confirmed' AND amount=0)),
        FOREIGN KEY(incident_id,company_id) REFERENCES tool_incidents(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('CREATE INDEX tool_incident_decision_history ON tool_incident_decisions(incident_id,id)')
    op.execute('''CREATE TABLE tool_fine_allocations (
        act_id INTEGER NOT NULL, company_id INTEGER NOT NULL, incident_id BIGINT NOT NULL,
        decision_id BIGINT NOT NULL, amount NUMERIC(14,2) NOT NULL CHECK(amount>0),
        PRIMARY KEY(act_id,incident_id),
        FOREIGN KEY(act_id,company_id) REFERENCES work_contract_acts(act_id,company_id),
        FOREIGN KEY(incident_id,company_id) REFERENCES tool_incidents(id,company_id),
        FOREIGN KEY(decision_id,company_id) REFERENCES tool_incident_decisions(id,company_id))''')
    op.execute('ALTER TABLE tool_history ADD COLUMN master_id INTEGER REFERENCES users(id)')
    op.execute('ALTER TABLE tool_history ADD COLUMN custody_event_id BIGINT UNIQUE REFERENCES tool_custody_events(id)')
    for table in ('tool_custody_events', 'tool_incidents', 'tool_incident_decisions', 'tool_fine_allocations'):
        op.execute(f'''CREATE TRIGGER tool_custody_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_work_material_immutable()''')
    op.execute('''CREATE FUNCTION guard_tool_custody_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='tool_incidents' THEN
            IF NOT EXISTS(SELECT 1 FROM tool_custody_events e WHERE e.id=NEW.event_id
                AND e.company_id=NEW.company_id AND e.tool_id=NEW.tool_id AND e.action='return'
                AND e.condition=NEW.kind AND e.project_id=NEW.project_id AND e.holder_id=NEW.holder_id
                AND e.contract_id IS NOT DISTINCT FROM NEW.contract_id)
            THEN RAISE EXCEPTION 'Tool incident lineage mismatch'; END IF;
        ELSE
            IF NOT EXISTS(SELECT 1 FROM tool_incident_decisions d
                JOIN tool_incidents i ON i.id=d.incident_id
                JOIN work_contract_acts a ON a.act_id=NEW.act_id
                WHERE d.id=NEW.decision_id AND d.incident_id=NEW.incident_id
                AND d.company_id=NEW.company_id AND d.decision='confirmed'
                AND a.company_id=NEW.company_id AND a.contract_id=i.contract_id
                AND d.id=(SELECT max(s.id) FROM tool_incident_decisions s WHERE s.incident_id=i.id)
                AND NEW.amount+COALESCE((SELECT SUM(f.amount) FROM tool_fine_allocations f
                    WHERE f.incident_id=i.id),0)<=d.amount)
            THEN RAISE EXCEPTION 'Tool fine allocation mismatch'; END IF;
        END IF;
        RETURN NEW;
        END $$''')
    for table in ('tool_incidents', 'tool_fine_allocations'):
        op.execute(f'''CREATE TRIGGER tool_custody_lineage BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_tool_custody_lineage()''')
    op.execute('''CREATE TRIGGER tool_custody_history_immutable BEFORE UPDATE OR DELETE ON tool_history
        FOR EACH ROW WHEN (OLD.custody_event_id IS NOT NULL) EXECUTE FUNCTION guard_work_material_immutable()''')


def downgrade():
    op.execute('LOCK TABLE tool_custody_events IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM tool_custody_events)
        THEN RAISE EXCEPTION 'Tool history must be preserved'; END IF; END $$''')
    op.execute('DROP TRIGGER tool_custody_history_immutable ON tool_history')
    op.execute('ALTER TABLE tool_history DROP COLUMN custody_event_id, DROP COLUMN master_id')
    for table in ('tool_fine_allocations', 'tool_incident_decisions', 'tool_incidents', 'tool_custody_events'):
        op.execute(f'DROP TABLE {table}')
    op.execute('DROP FUNCTION guard_tool_custody_lineage()')
    op.execute('DROP INDEX tools_owner_identity')
    op.execute('ALTER TABLE tools DROP COLUMN custody_version, DROP COLUMN custody_contract_id')
