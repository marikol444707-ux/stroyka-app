"""Explicit allocation of reviewed tool purchases; historical charges are not inferred."""
from alembic import op

revision = '0116_tool_deductions'
down_revision = '0115_performer_retention'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
CREATE UNIQUE INDEX IF NOT EXISTS tool_deduction_tool_owner ON tools(id,company_id);
CREATE UNIQUE INDEX IF NOT EXISTS tool_deduction_history_owner ON tool_history(id,company_id);
CREATE UNIQUE INDEX IF NOT EXISTS tool_deduction_staff_owner ON staff(id,company_id);
CREATE UNIQUE INDEX IF NOT EXISTS tool_deduction_project_owner ON projects(id,company_id);
ALTER TABLE interim_acts ADD COLUMN tool_deduction_prior_status TEXT;
CREATE TABLE tool_deduction_sources (
 id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
 tool_id INTEGER NOT NULL, history_id INTEGER, source_key TEXT NOT NULL,
 staff_id INTEGER NOT NULL, project_id INTEGER NOT NULL,
 amount NUMERIC(14,2) NOT NULL CHECK(amount>0),
 previously_deducted NUMERIC(14,2) NOT NULL CHECK(previously_deducted>=0 AND previously_deducted<=amount),
 basis TEXT NOT NULL, snapshot JSONB NOT NULL, revision BIGINT NOT NULL DEFAULT 0 CHECK(revision>=0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(company_id,source_key), UNIQUE(id,company_id),
 FOREIGN KEY(tool_id,company_id) REFERENCES tools(id,company_id),
 FOREIGN KEY(history_id,company_id) REFERENCES tool_history(id,company_id),
 FOREIGN KEY(staff_id,company_id) REFERENCES staff(id,company_id),
 FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)
);
CREATE TABLE tool_deduction_allocations (
 id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, source_id BIGINT NOT NULL,
 act_id INTEGER, staff_id INTEGER NOT NULL, month TEXT,
 amount NUMERIC(14,2) NOT NULL CHECK(amount>=0),
 refunded NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK(refunded>=0 AND refunded<=amount),
 CHECK((act_id IS NOT NULL AND month IS NULL) OR (act_id IS NULL AND month IS NOT NULL AND month ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$')),
 UNIQUE(source_id,act_id), UNIQUE(source_id,staff_id,month), UNIQUE(id,company_id),
 FOREIGN KEY(source_id,company_id) REFERENCES tool_deduction_sources(id,company_id),
 FOREIGN KEY(act_id,company_id) REFERENCES interim_acts(id,company_id),
 FOREIGN KEY(staff_id,company_id) REFERENCES staff(id,company_id)
);
CREATE TABLE tool_deduction_events (
 id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, source_id BIGINT NOT NULL,
 revision BIGINT NOT NULL, actor TEXT NOT NULL, change JSONB NOT NULL,
 project_payment_id INTEGER UNIQUE REFERENCES project_payments(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(source_id,revision),
 FOREIGN KEY(source_id,company_id) REFERENCES tool_deduction_sources(id,company_id)
);
CREATE FUNCTION guard_tool_deduction_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Tool deduction audit is immutable'; END $$;
CREATE TRIGGER tool_deduction_event_immutable BEFORE UPDATE OR DELETE ON tool_deduction_events
 FOR EACH ROW EXECUTE FUNCTION guard_tool_deduction_event();
ALTER TABLE salary_payments ADD COLUMN tool_deduction_snapshot JSONB NOT NULL DEFAULT '{}';
CREATE FUNCTION guard_tool_deduction_act() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tool_amount NUMERIC; gross_tool NUMERIC; advance NUMERIC;
BEGIN
 SELECT COALESCE(sum(amount-refunded),0),COALESCE(sum(amount),0)
 INTO tool_amount,gross_tool FROM tool_deduction_allocations WHERE act_id=OLD.id;
 IF gross_tool>0 THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Act has tool deduction history'; END IF;
  IF (NEW.company_id,NEW.master_id,NEW.project,NEW.work_package,NEW.total_amount,NEW.work_journal_ids,NEW.source_type)
      IS DISTINCT FROM (OLD.company_id,OLD.master_id,OLD.project,OLD.work_package,OLD.total_amount,OLD.work_journal_ids,OLD.source_type)
   OR NEW.status='Аннулирован' OR NEW.paid_amount IS NULL OR NEW.paid_amount<COALESCE(OLD.paid_amount,0)
  THEN RAISE EXCEPTION 'Act identity and cash are protected by tool deductions'; END IF;
  SELECT COALESCE(sum(amount),0) INTO advance FROM performer_advance_allocations WHERE act_id=OLD.id;
  IF NEW.paid_amount+advance+tool_amount+NEW.retention_amount-NEW.retention_released>NEW.total_amount
  THEN RAISE EXCEPTION 'Payment exceeds act balance after tool deductions'; END IF;
  IF NEW.paid_amount+advance+tool_amount>=NEW.total_amount THEN NEW.status:='Оплачен';
  ELSIF NEW.paid_amount+advance+tool_amount>0 THEN NEW.status:='Частично оплачен'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER tool_deduction_act_guard BEFORE UPDATE OR DELETE ON interim_acts
 FOR EACH ROW EXECUTE FUNCTION guard_tool_deduction_act();
CREATE FUNCTION guard_tool_deduction_salary() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF COALESCE((OLD.tool_deduction_snapshot->>'amount')::numeric,0)>0 THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Salary contains tool deductions; use a confirmed refund'; END IF;
  IF (NEW.company_id,NEW.staff_id,NEW.month,NEW.amount,NEW.tool_deduction_snapshot)
     IS DISTINCT FROM (OLD.company_id,OLD.staff_id,OLD.month,OLD.amount,OLD.tool_deduction_snapshot)
  THEN RAISE EXCEPTION 'Salary tool deduction snapshot is immutable'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER tool_deduction_salary_guard BEFORE UPDATE OR DELETE ON salary_payments
 FOR EACH ROW EXECUTE FUNCTION guard_tool_deduction_salary();
'''

def upgrade():
    op.execute(SCHEMA_SQL)

def downgrade():
    raise RuntimeError('Tool deductions contain financial history; automatic downgrade is forbidden')
