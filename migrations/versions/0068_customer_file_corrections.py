"""Keep customer file corrections as immutable linked versions."""
from alembic import op

revision = '0068_customer_file_corrections'
down_revision = '0067_supplier_contract_originals'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
    ALTER TABLE public.project_letters
        ADD COLUMN correction_reason TEXT,
        ADD COLUMN correction_requested_at TIMESTAMPTZ,
        ADD COLUMN correction_requested_by_id INTEGER REFERENCES public.users(id),
        ADD COLUMN correction_requested_by_name TEXT,
        ADD COLUMN corrected_by_letter_id INTEGER,
        ADD COLUMN replaces_letter_id INTEGER,
        ADD CONSTRAINT project_letters_version_owner_unique UNIQUE(id,company_id,project_id),
        ADD CONSTRAINT project_letter_corrected_owner_fk
            FOREIGN KEY(corrected_by_letter_id,company_id,project_id)
            REFERENCES public.project_letters(id,company_id,project_id),
        ADD CONSTRAINT project_letter_replaces_owner_fk
            FOREIGN KEY(replaces_letter_id,company_id,project_id)
            REFERENCES public.project_letters(id,company_id,project_id),
        ADD CONSTRAINT project_letter_correction_request_pair CHECK (
            (correction_reason IS NULL) = (correction_requested_at IS NULL)
        );
    CREATE UNIQUE INDEX project_letter_single_replacement
        ON public.project_letters(company_id,replaces_letter_id) WHERE replaces_letter_id IS NOT NULL;
    CREATE INDEX project_letter_open_correction
        ON public.project_letters(company_id,project_id,id)
        WHERE correction_requested_at IS NOT NULL AND corrected_by_letter_id IS NULL;
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM public.project_letters
        WHERE correction_requested_at IS NOT NULL OR replaces_letter_id IS NOT NULL
    ) THEN RAISE EXCEPTION 'Preserve customer document correction history'; END IF; END $$""")
    op.execute('DROP INDEX public.project_letter_open_correction')
    op.execute('DROP INDEX public.project_letter_single_replacement')
    op.execute('ALTER TABLE public.project_letters DROP COLUMN replaces_letter_id, DROP COLUMN corrected_by_letter_id, '
               'DROP COLUMN correction_requested_by_name, DROP COLUMN correction_requested_by_id, '
               'DROP COLUMN correction_requested_at, DROP COLUMN correction_reason, '
               'DROP CONSTRAINT project_letters_version_owner_unique')
