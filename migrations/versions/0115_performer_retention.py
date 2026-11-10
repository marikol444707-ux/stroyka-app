"""Confirmed guarantee retention on legacy performer acts; no historical inference."""
from alembic import op
revision='0115_performer_retention'
down_revision='0114_performer_advances'
branch_labels=None
depends_on=None

SCHEMA_SQL='''
ALTER TABLE interim_acts
 ADD COLUMN retention_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK(retention_amount>=0),
 ADD COLUMN retention_released NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK(retention_released>=0 AND retention_released<=retention_amount),
 ADD COLUMN retention_revision BIGINT NOT NULL DEFAULT 0 CHECK(retention_revision>=0),
 ADD COLUMN retention_basis TEXT NOT NULL DEFAULT '';
CREATE TABLE performer_retention_events (
 id BIGSERIAL PRIMARY KEY,
 company_id INTEGER NOT NULL REFERENCES companies(id),
 act_id INTEGER NOT NULL,
 revision BIGINT NOT NULL,
 actor TEXT NOT NULL,
 change JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(act_id,revision),
 FOREIGN KEY(act_id,company_id) REFERENCES interim_acts(id,company_id)
);
CREATE FUNCTION guard_performer_retention_act() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE credited NUMERIC;
BEGIN
 IF TG_OP='DELETE' THEN
   IF OLD.retention_amount>0 THEN RAISE EXCEPTION 'Act has guarantee retention history'; END IF;
   RETURN OLD;
 END IF;
 IF OLD.retention_amount>0 OR NEW.retention_amount>0 THEN
   IF (NEW.company_id,NEW.master_id,NEW.project,NEW.work_package,NEW.total_amount,NEW.work_journal_ids,NEW.source_type)
      IS DISTINCT FROM (OLD.company_id,OLD.master_id,OLD.project,OLD.work_package,OLD.total_amount,OLD.work_journal_ids,OLD.source_type)
      OR NEW.status='Аннулирован' OR NEW.paid_amount IS NULL
      OR NEW.paid_amount<COALESCE(OLD.paid_amount,0)
      OR NEW.retention_released<OLD.retention_released
   THEN RAISE EXCEPTION 'Act is protected by guarantee retention'; END IF;
   SELECT COALESCE(sum(amount),0) INTO credited FROM performer_advance_allocations WHERE act_id=OLD.id;
   IF NEW.paid_amount+credited+NEW.retention_amount-NEW.retention_released>NEW.total_amount
   THEN RAISE EXCEPTION 'Payment exceeds released act balance'; END IF;
   IF NEW.paid_amount+credited>=NEW.total_amount THEN NEW.status:='Оплачен';
   ELSIF NEW.paid_amount+credited>0 THEN NEW.status:='Частично оплачен';
   ELSIF NEW.status='Оплачен' THEN RAISE EXCEPTION 'Unpaid guarantee is not a completed payment'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER performer_retention_act_guard BEFORE UPDATE OR DELETE ON interim_acts
 FOR EACH ROW EXECUTE FUNCTION guard_performer_retention_act();
'''

def upgrade():op.execute(SCHEMA_SQL)
def downgrade():raise RuntimeError('Guarantee retention is financial history; automatic removal is forbidden')
