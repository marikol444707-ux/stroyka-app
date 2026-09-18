"""Separate actual consumption from acceptance of the work; preserve old journals."""
from alembic import op

revision = '0027_work_material_accounting'
down_revision = '0026_distribution_transfers'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS
        settlement_version SMALLINT NOT NULL DEFAULT 1''')
    op.execute('''ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS
        material_accounting_version SMALLINT NOT NULL DEFAULT 1''')
    op.execute('''CREATE TABLE work_material_operations (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
        actor_id INTEGER NOT NULL REFERENCES users(id), request_id UUID NOT NULL,
        kind TEXT NOT NULL, payload_hash TEXT NOT NULL, result JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(company_id,actor_id,request_id), UNIQUE(id,company_id))''')
    op.execute('''CREATE TABLE work_material_accounts (
        journal_id INTEGER PRIMARY KEY REFERENCES work_journal(id),
        company_id INTEGER NOT NULL REFERENCES companies(id),
        project_id INTEGER NOT NULL REFERENCES projects(id),
        actor_id INTEGER NOT NULL REFERENCES users(id),
        contract_id INTEGER NOT NULL REFERENCES brigade_contracts(id),
        operation_id BIGINT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(journal_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE INDEX work_material_contract ON work_material_accounts(company_id,contract_id,journal_id)''')
    op.execute('''CREATE TABLE work_material_entries (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL,
        journal_id INTEGER NOT NULL, operation_id BIGINT NOT NULL,
        corrects_entry_id BIGINT,
        source TEXT NOT NULL CHECK(source IN ('personal','warehouse')),
        warehouse_material_id INTEGER REFERENCES materials(id),
        material_name TEXT NOT NULL, unit TEXT NOT NULL, work_package TEXT NOT NULL,
        quantity NUMERIC(14,6) NOT NULL CHECK(quantity<>0),
        identity_snapshot JSONB NOT NULL,
        unit_price NUMERIC(18,4), reason TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        CHECK((source='warehouse')=(warehouse_material_id IS NOT NULL)),
        CHECK(unit_price IS NULL OR unit_price>=0),
        FOREIGN KEY(journal_id,company_id) REFERENCES work_material_accounts(journal_id,company_id),
        FOREIGN KEY(corrects_entry_id,company_id) REFERENCES work_material_entries(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE INDEX work_material_journal ON work_material_entries(company_id,journal_id,id)''')
    op.execute('''CREATE TABLE work_material_defects (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, journal_id INTEGER NOT NULL,
        operation_id BIGINT NOT NULL, reported_by INTEGER NOT NULL REFERENCES users(id),
        reason TEXT NOT NULL CHECK(length(trim(reason))>0), photos JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        FOREIGN KEY(journal_id,company_id) REFERENCES work_material_accounts(journal_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE TABLE work_material_defect_items (
        defect_id BIGINT NOT NULL, company_id INTEGER NOT NULL, entry_id BIGINT NOT NULL,
        quantity NUMERIC(14,6) NOT NULL CHECK(quantity>0), PRIMARY KEY(defect_id,entry_id),
        FOREIGN KEY(defect_id,company_id) REFERENCES work_material_defects(id,company_id),
        FOREIGN KEY(entry_id,company_id) REFERENCES work_material_entries(id,company_id))''')
    op.execute('''CREATE TABLE work_material_defect_decisions (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, defect_id BIGINT NOT NULL,
        operation_id BIGINT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
        decision TEXT NOT NULL CHECK(decision IN ('confirmed','disputed','cancelled')),
        reason TEXT NOT NULL, amount NUMERIC(14,2) NOT NULL CHECK(amount>=0),
        contract_evidence TEXT NOT NULL DEFAULT '', valuations JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        FOREIGN KEY(defect_id,company_id) REFERENCES work_material_defects(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE INDEX work_material_defect_journal ON work_material_defects(company_id,journal_id,id)''')
    op.execute('''CREATE INDEX work_material_decisions_latest ON work_material_defect_decisions(defect_id,id DESC)''')
    op.execute('''CREATE FUNCTION guard_work_material_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='work_material_operations' AND TG_OP='UPDATE'
           AND OLD.result IS NULL AND NEW.result IS NOT NULL
           AND (to_jsonb(NEW)-'result')=(to_jsonb(OLD)-'result') THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'Material accounting history is immutable'; END $$''')
    for table in ('work_material_operations', 'work_material_accounts', 'work_material_entries',
                  'work_material_defects', 'work_material_defect_items', 'work_material_defect_decisions'):
        op.execute(f'''CREATE TRIGGER work_material_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_work_material_immutable()''')
    op.execute('''CREATE FUNCTION guard_work_material_owner() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='work_material_accounts' THEN
            IF NOT EXISTS (SELECT 1 FROM work_journal w JOIN projects p
                    ON p.id=NEW.project_id AND p.company_id=NEW.company_id AND p.name=w.project
                JOIN brigade_contract_items i ON i.id=w.contract_item_id
                JOIN brigade_contracts c ON c.id=i.contract_id
                WHERE w.id=NEW.journal_id AND w.company_id=NEW.company_id
                  AND w.master_id=NEW.actor_id AND c.id=NEW.contract_id
                  AND c.company_id=NEW.company_id AND c.project_id=NEW.project_id FOR SHARE OF i,c,p)
            THEN RAISE EXCEPTION 'Material accounting owner mismatch'; END IF;
            RETURN NEW;
        END IF;
        IF EXISTS(SELECT 1 FROM work_material_accounts a WHERE a.journal_id=OLD.id)
           AND (NEW.company_id,NEW.project,NEW.master_id,NEW.contract_item_id,NEW.work_package,NEW.material_accounting_version)
               IS DISTINCT FROM
               (OLD.company_id,OLD.project,OLD.master_id,OLD.contract_item_id,OLD.work_package,OLD.material_accounting_version)
        THEN RAISE EXCEPTION 'Material accounting owner cannot change'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER work_material_account_owner BEFORE INSERT ON work_material_accounts
        FOR EACH ROW EXECUTE FUNCTION guard_work_material_owner()''')
    op.execute('''CREATE TRIGGER work_material_journal_owner BEFORE UPDATE ON work_journal
        FOR EACH ROW EXECUTE FUNCTION guard_work_material_owner()''')
    op.execute('''CREATE FUNCTION guard_work_material_lineage() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='brigade_contract_items' THEN
            IF EXISTS(SELECT 1 FROM work_journal w
                      WHERE w.contract_item_id=OLD.id AND
                      (EXISTS(SELECT 1 FROM work_material_accounts a WHERE a.journal_id=w.id)
                       OR EXISTS(SELECT 1 FROM work_contract_act_items a WHERE a.journal_id=w.id)))
               AND (TG_OP='DELETE' OR NEW.contract_id IS DISTINCT FROM OLD.contract_id)
            THEN RAISE EXCEPTION 'Contract item with material accounting cannot be removed or moved'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END IF;
        IF NEW.corrects_entry_id IS NOT NULL THEN
            IF NOT EXISTS(SELECT 1 FROM work_material_entries e WHERE e.id=NEW.corrects_entry_id
                AND e.corrects_entry_id IS NULL AND e.company_id=NEW.company_id
                AND e.journal_id=NEW.journal_id AND e.source=NEW.source
                AND e.material_name=NEW.material_name AND e.unit=NEW.unit AND e.work_package=NEW.work_package
                AND e.warehouse_material_id IS NOT DISTINCT FROM NEW.warehouse_material_id
                AND e.identity_snapshot=NEW.identity_snapshot)
            THEN RAISE EXCEPTION 'Material correction lineage mismatch'; END IF;
        ELSIF NEW.quantity<=0 THEN RAISE EXCEPTION 'Initial consumption must be positive'; END IF;
        IF NEW.source='warehouse' AND NOT EXISTS(SELECT 1 FROM materials m
            JOIN work_material_accounts a ON a.journal_id=NEW.journal_id AND a.company_id=NEW.company_id
            JOIN projects p ON p.id=a.project_id AND p.company_id=a.company_id
            WHERE m.id=NEW.warehouse_material_id AND m.company_id=NEW.company_id AND m.project=p.name)
        THEN RAISE EXCEPTION 'Material stock owner mismatch'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER work_material_entry_lineage BEFORE INSERT ON work_material_entries
        FOR EACH ROW EXECUTE FUNCTION guard_work_material_lineage()''')
    op.execute('''CREATE TRIGGER work_material_contract_item_lineage BEFORE UPDATE OR DELETE ON brigade_contract_items
        FOR EACH ROW EXECUTE FUNCTION guard_work_material_lineage()''')
    _upgrade_settlement()


def _upgrade_settlement():
    op.execute('''CREATE TABLE work_contract_acts (
        act_id INTEGER PRIMARY KEY REFERENCES brigade_acts(id), company_id INTEGER NOT NULL,
        contract_id INTEGER NOT NULL REFERENCES brigade_contracts(id), operation_id BIGINT NOT NULL,
        gross_amount NUMERIC(14,2) NOT NULL CHECK(gross_amount>0),
        fine_amount NUMERIC(14,2) NOT NULL CHECK(fine_amount>=0),
        net_amount NUMERIC(14,2) NOT NULL CHECK(net_amount>=0),
        snapshot JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(act_id,company_id), CHECK(gross_amount=fine_amount+net_amount),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE TABLE work_contract_act_items (
        journal_id INTEGER PRIMARY KEY REFERENCES work_journal(id), act_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL, snapshot JSONB NOT NULL,
        FOREIGN KEY(act_id,company_id) REFERENCES work_contract_acts(act_id,company_id))''')
    op.execute('''CREATE TABLE work_contract_fine_allocations (
        act_id INTEGER NOT NULL, company_id INTEGER NOT NULL, defect_id BIGINT NOT NULL,
        decision_id BIGINT NOT NULL, amount NUMERIC(14,2) NOT NULL CHECK(amount>0),
        PRIMARY KEY(act_id,defect_id),
        FOREIGN KEY(act_id,company_id) REFERENCES work_contract_acts(act_id,company_id),
        FOREIGN KEY(defect_id,company_id) REFERENCES work_material_defects(id,company_id),
        FOREIGN KEY(decision_id,company_id) REFERENCES work_material_defect_decisions(id,company_id))''')
    op.execute('''CREATE TABLE work_contract_act_signatures (
        act_id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, operation_id BIGINT NOT NULL,
        scan_url TEXT NOT NULL CHECK(length(trim(scan_url))>0),
        signed_by INTEGER NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        FOREIGN KEY(act_id,company_id) REFERENCES work_contract_acts(act_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE TABLE work_contract_act_payments (
        payment_id INTEGER PRIMARY KEY REFERENCES brigade_payments(id), act_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL, operation_id BIGINT NOT NULL,
        FOREIGN KEY(act_id,company_id) REFERENCES work_contract_acts(act_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    for table in ('work_contract_acts', 'work_contract_act_items', 'work_contract_fine_allocations',
                  'work_contract_act_signatures', 'work_contract_act_payments'):
        op.execute(f'''CREATE TRIGGER work_material_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_work_material_immutable()''')
    op.execute('''CREATE FUNCTION guard_work_contract_settlement() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='work_journal' THEN
            IF EXISTS(SELECT 1 FROM work_contract_act_items WHERE journal_id=OLD.id)
                AND (TG_OP='DELETE' OR
                     (NEW.company_id,NEW.project,NEW.contract_item_id,NEW.master_id,NEW.work_package,
                      NEW.description,NEW.unit,NEW.quantity,NEW.execution_price_per_unit,NEW.execution_total,NEW.status,NEW.date)
                     IS DISTINCT FROM
                     (OLD.company_id,OLD.project,OLD.contract_item_id,OLD.master_id,OLD.work_package,
                      OLD.description,OLD.unit,OLD.quantity,OLD.execution_price_per_unit,OLD.execution_total,OLD.status,OLD.date))
            THEN RAISE EXCEPTION 'Work already included in an immutable contract act'; END IF;
        ELSIF TG_TABLE_NAME='brigade_contracts' THEN
            IF OLD.settlement_version=2 AND
                (NEW.settlement_version,NEW.company_id,NEW.project_id,NEW.project_name,NEW.work_package,NEW.contractor_id)
                IS DISTINCT FROM
                (OLD.settlement_version,OLD.company_id,OLD.project_id,OLD.project_name,OLD.work_package,OLD.contractor_id)
            THEN RAISE EXCEPTION 'Settled contract owner and kind cannot change'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW; END $$''')
    op.execute('''CREATE TRIGGER work_contract_journal_settled BEFORE UPDATE OR DELETE ON work_journal
        FOR EACH ROW EXECUTE FUNCTION guard_work_contract_settlement()''')
    op.execute('''CREATE TRIGGER work_contract_owner_settled BEFORE UPDATE ON brigade_contracts
        FOR EACH ROW EXECUTE FUNCTION guard_work_contract_settlement()''')


def downgrade():
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation')<>'read committed'
        THEN RAISE EXCEPTION 'Use a fresh READ COMMITTED transaction for downgrade'; END IF;
        END $$''')
    tables = ('work_contract_act_payments','work_contract_act_signatures','work_contract_fine_allocations',
              'work_contract_act_items','work_contract_acts','work_material_defect_decisions',
              'work_material_defect_items','work_material_defects','work_material_entries',
              'work_material_accounts','work_material_operations')
    op.execute('LOCK TABLE ' + ','.join(tables) + ' IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM work_material_operations)
           OR EXISTS(SELECT 1 FROM work_material_accounts)
           OR EXISTS(SELECT 1 FROM work_material_entries)
        THEN RAISE EXCEPTION 'Cannot remove material accounting with business data'; END IF;
        END $$''')
    op.execute('DROP TRIGGER work_material_journal_owner ON work_journal')
    op.execute('DROP TRIGGER work_material_contract_item_lineage ON brigade_contract_items')
    op.execute('DROP TRIGGER work_contract_journal_settled ON work_journal')
    op.execute('DROP TRIGGER work_contract_owner_settled ON brigade_contracts')
    op.execute('DROP TABLE work_contract_act_payments,work_contract_act_signatures,work_contract_fine_allocations,work_contract_act_items,work_contract_acts')
    op.execute('DROP FUNCTION guard_work_contract_settlement()')
    op.execute('DROP TABLE work_material_defect_decisions,work_material_defect_items,work_material_defects')
    op.execute('DROP TABLE work_material_entries,work_material_accounts,work_material_operations')
    op.execute('DROP FUNCTION guard_work_material_owner(),guard_work_material_immutable(),guard_work_material_lineage()')
    # Keep the additive version column: bootstrap also supplies its legacy default.
