"""Validate explicit receipt packages; no baseline/history rewrite or backfill."""
from alembic import op

revision = '0047_supplier_payment_packages'
down_revision = '0046_supplier_pay_attachments'
branch_labels = None
depends_on = None


def _previous_guard(filename, name):
    """Read one SQL literal, never import/run a previous migration.

    Retain the exact 0017/0018 bodies for downgrade. Upgrade changes only the
    warehouse package expression, not locks, money, identity or history guards.
    """
    import ast
    from pathlib import Path
    tree = ast.parse(Path(__file__).with_name(filename).read_text(encoding='utf-8'))
    prefix = 'CREATE FUNCTION public.' + name + '()'
    matches = [node.value for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)
               and node.value.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one historical guard: ' + name)
    return matches[0].replace('CREATE FUNCTION ', 'CREATE OR REPLACE FUNCTION ', 1)


def _install_guards(packages):
    for filename, name, old, new in (
        ('0045_supplier_payment_ledger.py', 'supplier_payment_document_guard',
         "COALESCE(NULLIF(project,''),location,''),''::TEXT",
         "COALESCE(NULLIF(project,''),location,''),public.supplier_payment_warehouse_package(items)"),
        ('0046_supplier_payment_attachments.py', 'supplier_payment_attachment_guard',
         "''::TEXT,COALESCE(NULLIF(warehouse.total_with_vat,0),warehouse.total_base)",
         "public.supplier_payment_warehouse_package(warehouse.items),COALESCE(NULLIF(warehouse.total_with_vat,0),warehouse.total_base)"),
    ):
        definition = _previous_guard(filename, name)
        if definition.count(old) != 1:
            raise RuntimeError('Historical warehouse package expression changed: ' + name)
        op.execute(definition.replace(old, new, 1) if packages else definition)


def upgrade():
    # Quiesce both baseline and attachment admission while changing their
    # shared validation contract. Existing immutable rows are not touched.
    op.execute('LOCK TABLE public.supplier_payment_documents, public.supplier_payment_attachments IN ACCESS EXCLUSIVE MODE')
    op.execute(r'''CREATE FUNCTION public.supplier_payment_warehouse_package(items_text TEXT)
        RETURNS TEXT LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE items_json JSON; item JSON; entry RECORD;
                package TEXT; item_package TEXT; candidate TEXT;
                camel_seen BOOLEAN; snake_seen BOOLEAN; item_seen BOOLEAN;
        BEGIN
        BEGIN
            items_json := items_text::JSON;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'Warehouse package requires valid JSON' USING ERRCODE='23514';
        END;
        IF items_json IS NULL OR json_typeof(items_json) IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Warehouse package requires an item array' USING ERRCODE='23514';
        END IF;
        IF json_array_length(items_json)=0 THEN
            RAISE EXCEPTION 'Warehouse package requires nonempty items' USING ERRCODE='23514';
        END IF;
        FOR item IN SELECT value FROM json_array_elements(items_json) LOOP
            IF json_typeof(item) IS DISTINCT FROM 'object' THEN
                RAISE EXCEPTION 'Warehouse package requires object items' USING ERRCODE='23514';
            END IF;
            camel_seen := FALSE; snake_seen := FALSE; item_seen := FALSE; item_package := NULL;
            -- JSON, not JSONB: repeated package keys must not disappear during
            -- parsing, concealing conflicting evidence through last-key-wins.
            FOR entry IN SELECT key,value FROM json_each(item)
                         WHERE key IN ('workPackage','work_package') LOOP
                IF (entry.key='workPackage' AND camel_seen)
                   OR (entry.key='work_package' AND snake_seen)
                   OR json_typeof(entry.value) IS DISTINCT FROM 'string' THEN
                    RAISE EXCEPTION 'Warehouse package keys must be explicit unique strings' USING ERRCODE='23514';
                END IF;
                candidate := entry.value #>> '{}';
                -- Validate canonical text; never trim it or default '' to
                -- Основная. Whitespace policy is explicit ASCII SP/TAB/CR/LF.
                IF candidate IS DISTINCT FROM btrim(candidate, E' \t\r\n') THEN
                    RAISE EXCEPTION 'Warehouse package contains surrounding whitespace' USING ERRCODE='23514';
                END IF;
                IF item_seen AND candidate IS DISTINCT FROM item_package THEN
                    RAISE EXCEPTION 'Warehouse package aliases disagree' USING ERRCODE='23514';
                END IF;
                item_package := candidate; item_seen := TRUE;
                IF entry.key='workPackage' THEN camel_seen := TRUE; ELSE snake_seen := TRUE; END IF;
            END LOOP;
            IF NOT item_seen THEN
                RAISE EXCEPTION 'Warehouse item package is missing' USING ERRCODE='23514';
            END IF;
            IF package IS NOT NULL AND package IS DISTINCT FROM item_package THEN
                RAISE EXCEPTION 'Warehouse contains mixed packages' USING ERRCODE='23514';
            END IF;
            package := item_package;
        END LOOP;
        RETURN package;
        END;
    $$''')
    _install_guards(True)


def downgrade():
    op.execute('LOCK TABLE public.supplier_payment_documents, public.supplier_payment_attachments IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Package downgrade requires READ COMMITTED' USING ERRCODE='23514';
        END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_payment_documents
                  WHERE document_kind='warehouse' AND work_package<>'') THEN
            RAISE EXCEPTION 'Cannot remove nonempty warehouse package baselines' USING ERRCODE='23514';
        END IF;
    END $$''')
    _install_guards(False)
    op.execute('DROP FUNCTION IF EXISTS public.supplier_payment_warehouse_package(TEXT)')
