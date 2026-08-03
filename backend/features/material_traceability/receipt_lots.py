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
    cur.execute(
        """CREATE TABLE IF NOT EXISTS warehouse_lot_movements (
            id SERIAL PRIMARY KEY,
            lot_id INT NOT NULL REFERENCES warehouse_receipt_lots(id),
            company_id INT NOT NULL,
            warehouse_movement_id INT NOT NULL,
            operation_type VARCHAR(50) NOT NULL,
            quantity NUMERIC(14,6) NOT NULL,
            unit VARCHAR(50) NOT NULL,
            from_location VARCHAR(255) NOT NULL,
            to_location VARCHAR(255) NOT NULL,
            created_by VARCHAR(255),
            reversal_of_id INT,
            created_at TIMESTAMP DEFAULT NOW()
        )"""
    )
    cur.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_lot_movement_operation
              ON warehouse_lot_movements(lot_id,warehouse_movement_id,operation_type)"""
    )
    cur.execute(
        """CREATE INDEX IF NOT EXISTS idx_warehouse_lot_movement_company
              ON warehouse_lot_movements(company_id,lot_id,created_at DESC)"""
    )
    cur.execute("ALTER TABLE warehouse_lot_movements ADD COLUMN IF NOT EXISTS reversal_of_id INT")


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


def lock_receipt_lot_for_movement(
    cur,
    *,
    company_id,
    warehouse_invoice_id,
    invoice_line_index,
    warehouse_location,
    material_name,
    unit,
    requested_quantity,
):
    """Lock an exact future receipt lot, leaving historic sources unlinked."""
    cur.execute(
        """SELECT id,company_id,warehouse_location,material_name,unit,available_quantity,status
              FROM warehouse_receipt_lots
             WHERE company_id=%s AND warehouse_invoice_id=%s AND invoice_line_index=%s
             FOR UPDATE""",
        (int(company_id), int(warehouse_invoice_id), int(invoice_line_index)),
    )
    lot = cur.fetchone()
    if not lot:
        return None
    lot = dict(lot) if not isinstance(lot, dict) else lot
    if str(lot.get("status") or "") != "active":
        raise ValueError("Партия выбранной строки накладной уже закрыта")
    if str(lot.get("warehouse_location") or "").strip() != str(warehouse_location or "").strip():
        raise ValueError("Партия выбранной строки накладной относится к другому складу или объекту")
    if (
        str(lot.get("material_name") or "").strip().casefold() != str(material_name or "").strip().casefold()
        or str(lot.get("unit") or "").strip().casefold() != str(unit or "").strip().casefold()
    ):
        raise ValueError("Партия выбранной строки накладной не совпадает с материалом или единицей")
    available_quantity = float(lot.get("available_quantity") or 0)
    if available_quantity + 1e-9 < float(requested_quantity or 0):
        raise ValueError(
            "В выбранной партии доступно " + format(available_quantity, ".6g") + " " + str(lot.get("unit") or "")
        )
    return lot


def consume_receipt_lot(
    cur,
    *,
    lot,
    warehouse_movement_id,
    quantity,
    from_location,
    to_location,
    created_by,
):
    """Record an immutable movement event and reduce the exact available lot balance."""
    lot_id = int(lot.get("id") if isinstance(lot, dict) else lot["id"])
    company_id = int(lot.get("company_id") if isinstance(lot, dict) else lot["company_id"])
    unit = str(lot.get("unit") if isinstance(lot, dict) else lot["unit"])
    quantity = float(quantity or 0)
    if quantity <= 0:
        raise ValueError("Для списания партии нужно положительное количество")
    cur.execute(
        """UPDATE warehouse_receipt_lots
              SET available_quantity=available_quantity-%s
            WHERE id=%s AND status='active' AND available_quantity >= %s
          RETURNING available_quantity""",
        (quantity, lot_id, quantity),
    )
    remaining = cur.fetchone()
    if not remaining:
        raise ValueError("Остаток выбранной партии изменился, обновите данные и повторите перемещение")
    cur.execute(
        """INSERT INTO warehouse_lot_movements
            (lot_id,company_id,warehouse_movement_id,operation_type,quantity,unit,
             from_location,to_location,created_by)
           VALUES (%s,%s,%s,'warehouse_movement_out',%s,%s,%s,%s,%s)
           ON CONFLICT (lot_id,warehouse_movement_id,operation_type) DO NOTHING""",
        (lot_id, company_id, int(warehouse_movement_id), quantity, unit,
         str(from_location or ""), str(to_location or ""), str(created_by or "")),
    )
    return remaining.get("available_quantity") if isinstance(remaining, dict) else remaining[0]


def restore_receipt_lot(
    cur,
    *,
    lot_id,
    company_id,
    warehouse_movement_id,
    original_lot_movement_id,
    quantity,
    unit,
    from_location,
    to_location,
    created_by,
):
    """Append a compensating lot event without deleting the original consumption."""
    quantity = float(quantity or 0)
    if quantity <= 0:
        raise ValueError("Для возврата партии нужно положительное количество")
    cur.execute(
        """UPDATE warehouse_receipt_lots
              SET available_quantity=available_quantity+%s
            WHERE id=%s AND company_id=%s
          RETURNING available_quantity""",
        (quantity, int(lot_id), int(company_id)),
    )
    remaining = cur.fetchone()
    if not remaining:
        raise ValueError("Партия исходного движения не найдена")
    cur.execute(
        """INSERT INTO warehouse_lot_movements
            (lot_id,company_id,warehouse_movement_id,operation_type,quantity,unit,
             from_location,to_location,created_by,reversal_of_id)
           VALUES (%s,%s,%s,'warehouse_movement_reversal',%s,%s,%s,%s,%s,%s,%s)""",
        (
            int(lot_id), int(company_id), int(warehouse_movement_id), quantity, str(unit or ""),
            str(from_location or ""), str(to_location or ""), str(created_by or ""),
            int(original_lot_movement_id),
        ),
    )
    return remaining.get("available_quantity") if isinstance(remaining, dict) else remaining[0]
