"""Record addressed customer publication state and immutable delivery identity."""
from alembic import op

revision = '0069_customer_publications'
down_revision = '0068_customer_file_corrections'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
    ALTER TABLE public.project_letters
        ADD COLUMN delivery_status VARCHAR(20) NOT NULL DEFAULT 'sent',
        ADD COLUMN published_at TIMESTAMPTZ,
        ADD COLUMN published_by_id INTEGER REFERENCES public.users(id),
        ADD COLUMN published_by_name TEXT,
        ADD COLUMN client_request_id UUID,
        ADD CONSTRAINT project_letter_delivery_status_check
            CHECK (delivery_status IN ('sent','received'));
    UPDATE public.project_letters
       SET delivery_status=CASE WHEN direction='incoming' THEN 'received' ELSE 'sent' END,
           published_at=created_at
     WHERE side='customer';
    CREATE UNIQUE INDEX project_letter_publication_request_unique
        ON public.project_letters(company_id,client_request_id)
        WHERE client_request_id IS NOT NULL;
    CREATE INDEX project_letter_customer_delivery
        ON public.project_letters(company_id,project_id,published_at DESC,id DESC)
        WHERE side='customer' AND delivery_status IN ('sent','received');
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM public.project_letters WHERE client_request_id IS NOT NULL
    ) THEN RAISE EXCEPTION 'Preserve addressed customer publication history'; END IF; END $$""")
    op.execute('DROP INDEX public.project_letter_customer_delivery')
    op.execute('DROP INDEX public.project_letter_publication_request_unique')
    op.execute('ALTER TABLE public.project_letters DROP COLUMN client_request_id, '
               'DROP COLUMN published_by_name, DROP COLUMN published_by_id, '
               'DROP COLUMN published_at, DROP COLUMN delivery_status')
