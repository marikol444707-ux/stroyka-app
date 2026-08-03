"""Additive receipt-lot storage for future traceable stock operations."""


def ensure_receipt_lot_schema(cur):
    cur.execute(
        """CREATE TABLE IF NOT EXISTS warehouse_receipt_lots (
            id SERIAL PRIMARY KEY,
            company_id INT NOT NULL,
            project_id INT,
            project_name VARCHAR(255),
            warehouse_location VARCHAR(255) NOT NULL,
            warehouse_target VARCHAR(30) NOT NULL,
            warehouse_invoice_id INT NOT NULL,
            invoice_line_index INT NOT NULL,
            material_name TEXT NOT NULL,
            document_quantity NUMERIC(14,6),
            document_unit VARCHAR(50),
            received_quantity NUMERIC(14,6) NOT NULL,
            unit VARCHAR(50) NOT NULL,
            available_quantity NUMERIC(14,6) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )"""
    )
    cur.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_receipt_lot_source
              ON warehouse_receipt_lots(company_id,warehouse_invoice_id,invoice_line_index)"""
    )
    cur.execute(
        """CREATE INDEX IF NOT EXISTS idx_warehouse_receipt_lot_available
              ON warehouse_receipt_lots(company_id,warehouse_location,material_name,unit)
            WHERE status='active'"""
    )


def create_receipt_lot(
    cur,
    *,
    company_id,
    project_id,
    project_name,
    warehouse_location,
    warehouse_target,
    warehouse_invoice_id,
    invoice_line_index,
    material_name,
    document_quantity,
    document_unit,
    received_quantity,
    unit,
    created_by,
):
    """Create one immutable source lot for a newly accepted invoice line."""
    if int(company_id or 0) <= 0 or int(warehouse_invoice_id or 0) <= 0:
        raise ValueError("Для партии прихода нужны компания и накладная")
    if int(invoice_line_index) < 0 or float(received_quantity or 0) <= 0:
        raise ValueError("Для партии прихода нужны строка и положительное количество")
    if not str(material_name or "").strip() or not str(unit or "").strip():
        raise ValueError("Для партии прихода нужны материал и единица")
    cur.execute(
        """INSERT INTO warehouse_receipt_lots
            (company_id,project_id,project_name,warehouse_location,warehouse_target,
             warehouse_invoice_id,invoice_line_index,material_name,document_quantity,
             document_unit,received_quantity,unit,available_quantity,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (company_id,warehouse_invoice_id,invoice_line_index) DO NOTHING
           RETURNING id""",
        (
            int(company_id), project_id, str(project_name or ""), str(warehouse_location or ""),
            str(warehouse_target or "main"), int(warehouse_invoice_id), int(invoice_line_index),
            str(material_name).strip(), document_quantity, str(document_unit or ""),
            received_quantity, str(unit).strip(), received_quantity, str(created_by or ""),
        ),
    )
    row = cur.fetchone()
    return row.get("id") if isinstance(row, dict) else (row[0] if row else None)
