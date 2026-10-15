"""Canonical packaging table bootstrap shared by runtime and migrations."""


def packaging_schema_ready(cur):
    """Read-only bootstrap check, not proof of the history-lock guard contract."""
    cur.execute(
        """WITH expected(table_name, column_names) AS (VALUES
            ('public.material_packaging_rules', %s::text[]),
            ('public.material_packaging_reviews', %s::text[]))
        SELECT NOT EXISTS (
            SELECT 1 FROM expected e, unnest(e.column_names) AS required(column_name)
            WHERE NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_attribute a
                WHERE a.attrelid=to_regclass(e.table_name)
                  AND a.attname=required.column_name AND a.attnum>0 AND NOT a.attisdropped
            )
        ) AND EXISTS (
            SELECT 1 FROM pg_catalog.pg_index
            WHERE indexrelid=to_regclass('public.idx_material_packaging_rule_identity')
              AND indrelid=to_regclass('public.material_packaging_rules')
              AND indisvalid AND indisready AND indisunique
        ) AND EXISTS (
            SELECT 1 FROM pg_catalog.pg_index
            WHERE indexrelid=to_regclass('public.idx_material_packaging_reviews_invoice')
              AND indrelid=to_regclass('public.material_packaging_reviews')
              AND indisvalid AND indisready
        ) AS ready""",
        (['id', 'company_id', 'supplier_id', 'material_key', 'material_name',
          'document_unit', 'base_unit', 'content_quantity', 'status', 'note',
          'created_by', 'created_at', 'updated_at'],
         ['id', 'company_id', 'warehouse_invoice_id', 'item_index', 'packaging_rule_id',
          'status', 'review_note', 'snapshot', 'reviewed_by', 'reviewed_at', 'review_decision']),
    )
    row = cur.fetchone()
    return bool(row['ready'] if isinstance(row, dict) else row[0])


def ensure_packaging_schema(cur):
    cur.execute(
        """CREATE TABLE IF NOT EXISTS material_packaging_rules (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            supplier_id INT,
            material_key TEXT NOT NULL,
            material_name TEXT NOT NULL,
            document_unit VARCHAR(50) NOT NULL,
            base_unit VARCHAR(50) NOT NULL,
            content_quantity NUMERIC(14,4) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'confirmed',
            note TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )"""
    )
    cur.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_material_packaging_rule_identity
            ON material_packaging_rules(company_id, COALESCE(supplier_id, 0), material_key, document_unit)
        """
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS material_packaging_reviews (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            warehouse_invoice_id INT NOT NULL,
            item_index INT NOT NULL,
            packaging_rule_id INT NOT NULL,
            status VARCHAR(40) NOT NULL DEFAULT 'reviewed_no_stock_change',
            review_note TEXT NOT NULL,
            snapshot JSONB NOT NULL,
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMP DEFAULT NOW()
        )"""
    )
    cur.execute(
        """ALTER TABLE material_packaging_reviews
               ADD COLUMN IF NOT EXISTS review_decision VARCHAR(40) NOT NULL DEFAULT 'legacy_unclassified'"""
    )
    cur.execute(
        """CREATE INDEX IF NOT EXISTS idx_material_packaging_reviews_invoice
            ON material_packaging_reviews(company_id, warehouse_invoice_id, item_index, reviewed_at DESC)
        """
    )
