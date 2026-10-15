"""Canonical packaging table bootstrap shared by runtime and migrations."""

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
