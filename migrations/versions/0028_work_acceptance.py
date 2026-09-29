"""Immutable work review and exact, linked rework; no historical backfill."""
from alembic import op

revision = '0028_work_acceptance'
down_revision = '0027_work_material_accounting'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE work_acceptance_reviews (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL REFERENCES projects(id), journal_id INTEGER NOT NULL UNIQUE,
        operation_id BIGINT NOT NULL UNIQUE, actor_id INTEGER NOT NULL REFERENCES users(id),
        actor_name TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('accept','return')),
        submitted_quantity NUMERIC(14,6) NOT NULL CHECK(submitted_quantity>0),
        accepted_quantity NUMERIC(14,6) NOT NULL CHECK(accepted_quantity>=0),
        reason TEXT NOT NULL, photos JSONB NOT NULL, work_snapshot JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        CHECK(accepted_quantity<=submitted_quantity),
        CHECK((decision='accept')=(accepted_quantity>0)),
        CHECK(accepted_quantity=submitted_quantity OR length(trim(reason))>0),
        FOREIGN KEY(journal_id,company_id) REFERENCES work_material_accounts(journal_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('''CREATE TABLE work_rework_links (
        journal_id INTEGER PRIMARY KEY REFERENCES work_journal(id),
        company_id INTEGER NOT NULL, project_id INTEGER NOT NULL REFERENCES projects(id),
        parent_journal_id INTEGER NOT NULL REFERENCES work_journal(id),
        review_id BIGINT NOT NULL UNIQUE, quantity NUMERIC(14,6) NOT NULL CHECK(quantity>0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(journal_id,company_id),
        CHECK(journal_id<>parent_journal_id),
        FOREIGN KEY(review_id,company_id) REFERENCES work_acceptance_reviews(id,company_id))''')
    op.execute('''CREATE INDEX work_rework_parent ON work_rework_links(company_id,parent_journal_id)''')
    op.execute('''CREATE TABLE work_rework_submissions (
        journal_id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL,
        operation_id BIGINT NOT NULL UNIQUE, actor_id INTEGER NOT NULL REFERENCES users(id),
        comment TEXT NOT NULL CHECK(length(trim(comment))>0), photos JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        FOREIGN KEY(journal_id,company_id) REFERENCES work_rework_links(journal_id,company_id),
        FOREIGN KEY(journal_id,company_id) REFERENCES work_material_accounts(journal_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    for table in ('work_acceptance_reviews', 'work_rework_links', 'work_rework_submissions'):
        op.execute(f'''CREATE TRIGGER work_acceptance_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_work_material_immutable()''')
    op.execute('''CREATE FUNCTION guard_work_acceptance_owner() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='work_acceptance_reviews' THEN
            IF NOT EXISTS(SELECT 1 FROM work_material_accounts a WHERE a.journal_id=NEW.journal_id
                AND a.company_id=NEW.company_id AND a.project_id=NEW.project_id)
            THEN RAISE EXCEPTION 'Work review owner mismatch'; END IF;
        ELSIF TG_TABLE_NAME='work_rework_links' THEN
            IF NOT EXISTS(SELECT 1 FROM work_acceptance_reviews r
                JOIN work_journal p ON p.id=r.journal_id
                JOIN work_journal w ON w.id=NEW.journal_id
                WHERE r.id=NEW.review_id AND r.company_id=NEW.company_id
                  AND r.project_id=NEW.project_id AND r.journal_id=NEW.parent_journal_id
                  AND NEW.quantity=r.submitted_quantity-r.accepted_quantity
                  AND w.quantity=NEW.quantity AND w.status='На доработке'
                  AND (w.company_id,w.project,w.master_id,w.contract_item_id,w.work_package,
                       w.estimate_id,w.estimate_item_key,w.room_id,w.room_name,w.unit)
                      IS NOT DISTINCT FROM
                      (p.company_id,p.project,p.master_id,p.contract_item_id,p.work_package,
                       p.estimate_id,p.estimate_item_key,p.room_id,p.room_name,p.unit))
            THEN RAISE EXCEPTION 'Rework lineage mismatch'; END IF;
        ELSE
            IF NOT EXISTS(SELECT 1 FROM work_material_accounts a WHERE a.journal_id=NEW.journal_id
                AND a.company_id=NEW.company_id AND a.actor_id=NEW.actor_id)
            THEN RAISE EXCEPTION 'Rework submitter mismatch'; END IF;
        END IF;
        RETURN NEW;
        END $$''')
    for table in ('work_acceptance_reviews', 'work_rework_links', 'work_rework_submissions'):
        op.execute(f'''CREATE TRIGGER work_acceptance_owner BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_work_acceptance_owner()''')


def downgrade():
    op.execute('''LOCK TABLE work_acceptance_reviews,work_rework_links,work_rework_submissions IN ACCESS EXCLUSIVE MODE''')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM work_acceptance_reviews)
        OR EXISTS(SELECT 1 FROM work_rework_links) OR EXISTS(SELECT 1 FROM work_rework_submissions)
        THEN RAISE EXCEPTION 'Work acceptance history must be preserved'; END IF; END $$''')
    for table in ('work_rework_submissions', 'work_rework_links', 'work_acceptance_reviews'):
        op.execute(f'DROP TABLE {table}')
    op.execute('DROP FUNCTION guard_work_acceptance_owner()')
