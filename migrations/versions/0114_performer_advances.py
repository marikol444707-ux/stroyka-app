"""Explicit purpose and company-owned manual salary advance allocations."""
from alembic import op

revision = '0114_performer_advances'
down_revision = '0113_warehouse_transfer_drafts'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
ALTER TABLE accountable_payments
 ADD COLUMN payment_kind TEXT NOT NULL DEFAULT 'unclassified'
   CHECK(payment_kind IN ('unclassified','expense','salary_advance')),
 ADD COLUMN revision BIGINT NOT NULL DEFAULT 0 CHECK(revision>=0),
 ADD CONSTRAINT performer_advance_payment_owner UNIQUE(id,company_id);
ALTER TABLE interim_acts ADD COLUMN advance_prior_status TEXT,
 ADD CONSTRAINT performer_advance_act_owner UNIQUE(id,company_id);
CREATE TABLE performer_advance_allocations (
 company_id INTEGER NOT NULL REFERENCES companies(id),
 payment_id INTEGER NOT NULL,
 act_id INTEGER NOT NULL,
 amount NUMERIC(14,2) NOT NULL CHECK(amount>=0 AND amount<1000000000000),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(payment_id,act_id),
 FOREIGN KEY(payment_id,company_id) REFERENCES accountable_payments(id,company_id),
 FOREIGN KEY(act_id,company_id) REFERENCES interim_acts(id,company_id)
);
CREATE INDEX performer_advance_allocations_act ON performer_advance_allocations(act_id,company_id);
CREATE TABLE performer_advance_events (
 id BIGSERIAL PRIMARY KEY,
 company_id INTEGER NOT NULL REFERENCES companies(id),
 payment_id INTEGER NOT NULL,
 revision BIGINT NOT NULL,
 actor TEXT NOT NULL,
 change JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(payment_id,revision),
 FOREIGN KEY(payment_id,company_id) REFERENCES accountable_payments(id,company_id)
);
CREATE FUNCTION guard_performer_advance_act() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE credited NUMERIC;
BEGIN
 SELECT COALESCE(sum(amount),0) INTO credited FROM performer_advance_allocations WHERE act_id=OLD.id;
 IF credited>0 THEN
   IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Act has advance allocations'; END IF;
   IF (NEW.company_id,NEW.master_id,NEW.project,NEW.work_package,NEW.total_amount,NEW.work_journal_ids,NEW.source_type)
      IS DISTINCT FROM (OLD.company_id,OLD.master_id,OLD.project,OLD.work_package,OLD.total_amount,OLD.work_journal_ids,OLD.source_type)
      OR NEW.status='Аннулирован' OR NEW.paid_amount IS NULL
      OR NEW.paid_amount<COALESCE(OLD.paid_amount,0)
      OR NEW.paid_amount+credited>NEW.total_amount
   THEN RAISE EXCEPTION 'Act is protected by advance allocations'; END IF;
   NEW.status := CASE WHEN NEW.paid_amount+credited>=NEW.total_amount THEN 'Оплачен' ELSE 'Частично оплачен' END;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER performer_advance_act_guard BEFORE UPDATE OR DELETE ON interim_acts
 FOR EACH ROW EXECUTE FUNCTION guard_performer_advance_act();
CREATE FUNCTION guard_salary_advance_expense() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE kind TEXT;
BEGIN
 SELECT payment_kind INTO kind FROM accountable_payments WHERE id=NEW.payment_id FOR UPDATE;
 IF kind IS DISTINCT FROM 'expense' THEN RAISE EXCEPTION 'Expense requires a classified expense payment'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER salary_advance_expense_guard BEFORE INSERT OR UPDATE ON accountable_expenses
 FOR EACH ROW EXECUTE FUNCTION guard_salary_advance_expense();
CREATE FUNCTION guard_advance_payment_kind() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='INSERT' AND NEW.payment_kind='unclassified' THEN
   RAISE EXCEPTION 'Select expense or salary_advance before issuing money';
 END IF;
 IF TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM performer_advance_allocations WHERE payment_id=OLD.id AND amount>0)
   AND (NEW.payment_kind,NEW.company_id,NEW.project_id,NEW.given_to_id,NEW.amount)
       IS DISTINCT FROM (OLD.payment_kind,OLD.company_id,OLD.project_id,OLD.given_to_id,OLD.amount)
 THEN RAISE EXCEPTION 'Allocated advance identity and amount are immutable'; END IF;
 IF NEW.payment_kind='salary_advance' AND (COALESCE(NEW.spent_amount,0)<>0
   OR EXISTS(SELECT 1 FROM accountable_expenses WHERE payment_id=NEW.id))
 THEN RAISE EXCEPTION 'Expense payment cannot be a salary advance'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER performer_advance_payment_guard BEFORE INSERT OR UPDATE ON accountable_payments
 FOR EACH ROW EXECUTE FUNCTION guard_advance_payment_kind();
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    raise RuntimeError('Advance allocations are financial history; automatic removal is forbidden')
