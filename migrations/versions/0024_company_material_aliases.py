"""Company-owned material mappings, separate from unowned legacy history."""
from alembic import op

revision = '0024_company_material_aliases'
down_revision = '0023_quality_journal_owners'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_alias_owner
        ON projects(id,company_id)''')
    op.execute('''CREATE TABLE company_material_aliases (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        project_id INTEGER,
        alias_name TEXT NOT NULL CHECK(length(btrim(alias_name)) BETWEEN 1 AND 500),
        alias_key TEXT NOT NULL CHECK(length(alias_key) BETWEEN 1 AND 500),
        canonical_name TEXT NOT NULL CHECK(length(btrim(canonical_name)) BETWEEN 1 AND 500),
        canonical_unit TEXT NOT NULL DEFAULT '' CHECK(length(canonical_unit)<=50),
        active BOOLEAN NOT NULL DEFAULT TRUE,
        previous_id BIGINT,
        created_by_id INTEGER NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        deactivated_by_id INTEGER REFERENCES users(id),
        deactivated_at TIMESTAMPTZ,
        UNIQUE(id,company_id),
        FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id),
        FOREIGN KEY(previous_id,company_id) REFERENCES company_material_aliases(id,company_id),
        CHECK(project_id IS NULL OR project_id>0),
        CHECK((active AND deactivated_at IS NULL AND deactivated_by_id IS NULL)
           OR (NOT active AND deactivated_at IS NOT NULL AND deactivated_by_id IS NOT NULL))
    )''')
    op.execute('''CREATE UNIQUE INDEX idx_company_material_alias_active_key
        ON company_material_aliases(company_id,COALESCE(project_id,0),alias_key)
        WHERE active''')


def downgrade():
    # Never drop new mappings during rollback. Operators must preserve/reconcile
    # them explicitly before reverting to a schema that cannot represent owners.
    op.execute('LOCK TABLE company_material_aliases IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation') <> 'read committed' THEN
            RAISE EXCEPTION 'Alias downgrade requires READ COMMITTED isolation';
        END IF;
        IF EXISTS(SELECT 1 FROM company_material_aliases LIMIT 1) THEN
            RAISE EXCEPTION 'Cannot downgrade: company material aliases contain data';
        END IF;
    END $$''')
    op.execute('DROP TABLE company_material_aliases')
    # Retain the harmless additive projects index for other ownership consumers.
