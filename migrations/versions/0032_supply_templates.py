"""Company request templates; historical ownership requires explicit evidence."""
from alembic import op

revision = '0032_supply_templates'
down_revision = '0031_company_warehouses'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE supply_request_templates
        ADD COLUMN company_id INTEGER REFERENCES companies(id),
        ADD COLUMN name_key TEXT,
        ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN version BIGINT NOT NULL DEFAULT 1 CHECK(version>0),
        ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        ADD CONSTRAINT supply_template_owned_name CHECK(company_id IS NULL OR
            (name_key IS NOT NULL AND length(name_key)>0 AND name IS NOT NULL AND length(trim(name))>0))''')
    op.execute('CREATE UNIQUE INDEX supply_template_identity ON supply_request_templates(id,company_id)')
    op.execute('''CREATE UNIQUE INDEX supply_template_active_name ON supply_request_templates(company_id,name_key)
        WHERE company_id IS NOT NULL AND NOT archived''')
    op.execute('''CREATE TABLE supply_template_events (
        id BIGSERIAL PRIMARY KEY, template_id INTEGER NOT NULL, company_id INTEGER NOT NULL,
        operation_id BIGINT UNIQUE, actor_id INTEGER REFERENCES users(id), actor_name TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('create','archive','assign_owner')),
        reason TEXT NOT NULL, before_template JSONB, after_template JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK((action='assign_owner' AND operation_id IS NULL AND actor_id IS NULL AND length(trim(reason))>0)
           OR (action<>'assign_owner' AND operation_id IS NOT NULL AND actor_id IS NOT NULL)),
        FOREIGN KEY(template_id,company_id) REFERENCES supply_request_templates(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('CREATE INDEX supply_template_history ON supply_template_events(company_id,template_id,id)')
    op.execute('''CREATE FUNCTION guard_supply_template() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='supply_template_events' OR TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Template records and history cannot be deleted or rewritten';
        END IF;
        IF (NEW.id,NEW.name,NEW.category,NEW.items_json,NEW.created_by,NEW.created_by_id,NEW.created_at)
            IS DISTINCT FROM (OLD.id,OLD.name,OLD.category,OLD.items_json,OLD.created_by,OLD.created_by_id,OLD.created_at)
            OR (OLD.company_id IS NOT NULL AND (NEW.company_id,NEW.name_key) IS DISTINCT FROM (OLD.company_id,OLD.name_key))
            OR NEW.version<>OLD.version+1 OR (OLD.archived AND NOT NEW.archived) THEN
            RAISE EXCEPTION 'Template content, owner and version are protected';
        END IF;
        RETURN NEW;
        END $$''')
    for table in ('supply_request_templates', 'supply_template_events'):
        op.execute(f'''CREATE TRIGGER {table}_guard BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_supply_template()''')


def downgrade():
    op.execute('LOCK TABLE supply_request_templates,supply_template_events IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF current_setting('transaction_isolation')<>'read committed'
        OR EXISTS(SELECT 1 FROM supply_template_events)
        OR EXISTS(SELECT 1 FROM supply_request_templates WHERE company_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot discard template ownership or recorded history'; END IF; END $$''')
    op.execute('DROP TRIGGER supply_request_templates_guard ON supply_request_templates')
    op.execute('DROP TABLE supply_template_events')
    op.execute('DROP FUNCTION guard_supply_template()')
    op.execute('DROP INDEX supply_template_active_name')
    op.execute('DROP INDEX supply_template_identity')
    op.execute('''ALTER TABLE supply_request_templates DROP CONSTRAINT supply_template_owned_name,
        DROP COLUMN company_id,DROP COLUMN name_key,DROP COLUMN archived,DROP COLUMN version,DROP COLUMN updated_at''')
