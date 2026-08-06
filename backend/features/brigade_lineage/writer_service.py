"""Server-owned writers for brigade contract item source metadata."""

import math


class LineageWriteConflict(ValueError):
    pass


def _finite_number(value, field):
    try:
        number = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}_invalid") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field}_invalid")
    return number


def _stored_value(row, index, key):
    if isinstance(row, dict):
        return row.get(key)
    return row[index]


def write_estimate_contract_item(
    cur,
    *,
    contract_id,
    work_package,
    lineage,
    section_name,
    name,
    unit,
    quantity,
    price_smeta,
    price_brigade,
):
    """Insert or exactly reuse one estimate-derived contract item."""
    if (
        getattr(lineage, "source_type", None) != "estimate"
        or getattr(lineage, "source_estimate_version_id", None) is None
        or getattr(lineage, "source_section_index", None) is None
        or getattr(lineage, "source_item_index", None) is None
        or not getattr(lineage, "source_item_key", None)
    ):
        raise ValueError("estimate_lineage_incomplete")

    issued_quantity = _finite_number(quantity, "quantity")
    issued_price_smeta = _finite_number(price_smeta, "price_smeta")
    issued_price_brigade = _finite_number(price_brigade, "price_brigade")
    if issued_quantity <= 0 or issued_price_smeta <= 0 or issued_price_brigade <= 0:
        raise ValueError("estimate_item_value_invalid")

    cur.execute(
        """SELECT id, estimate_section, description, unit, quantity,
                  price_smeta, price_brigade, estimate_item_key
             FROM brigade_contract_items
           WHERE contract_id=%s
             AND source_type='estimate'
             AND source_estimate_version_id=%s
             AND source_section_index=%s
             AND source_item_index=%s
             AND source_item_key=%s
           LIMIT 1 FOR UPDATE""",
        (
            contract_id,
            lineage.source_estimate_version_id,
            lineage.source_section_index,
            lineage.source_item_index,
            lineage.source_item_key,
        ),
    )
    existing = cur.fetchone()
    if existing:
        compatibility_key = _stored_value(existing, 7, "estimate_item_key") or ""
        if compatibility_key != lineage.source_item_key:
            raise LineageWriteConflict("estimate_compatibility_key_conflict")
        return {
            "id": _stored_value(existing, 0, "id"),
            "section": _stored_value(existing, 1, "estimate_section") or section_name or "",
            "name": _stored_value(existing, 2, "description") or name or "",
            "unit": _stored_value(existing, 3, "unit") or unit or "шт",
            "quantity": _finite_number(_stored_value(existing, 4, "quantity"), "stored_quantity"),
            "priceSmeta": _finite_number(_stored_value(existing, 5, "price_smeta"), "stored_price_smeta"),
            "priceBrigade": _finite_number(_stored_value(existing, 6, "price_brigade"), "stored_price_brigade"),
            "estimateItemKey": compatibility_key,
            "inserted": False,
        }

    cur.execute(
        """INSERT INTO brigade_contract_items
             (contract_id, estimate_section, description, work_package, estimate_item_key,
              unit, quantity, price_smeta, price_brigade, done_quantity,
              source_type, source_estimate_version_id, source_section_index,
              source_item_index, source_item_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING id""",
        (
            contract_id, section_name or "", name or "", work_package,
            lineage.source_item_key, unit or "шт", issued_quantity, issued_price_smeta,
            issued_price_brigade, 0, "estimate", lineage.source_estimate_version_id,
            lineage.source_section_index, lineage.source_item_index, lineage.source_item_key,
        ),
    )
    inserted = cur.fetchone()
    item_id = _stored_value(inserted, 0, "id")
    return {
        "id": item_id,
        "section": section_name or "",
        "name": name or "",
        "unit": unit or "шт",
        "quantity": issued_quantity,
        "priceSmeta": issued_price_smeta,
        "priceBrigade": issued_price_brigade,
        "estimateItemKey": lineage.source_item_key,
        "inserted": True,
    }


def insert_pricelist_contract_item(
    cur,
    *,
    contract_id,
    work_package,
    name,
    unit,
    price,
    category,
    coefficient,
):
    """Insert one pricelist-derived item without implying estimate lineage."""
    source_price = _finite_number(price, "price")
    source_coefficient = _finite_number(coefficient, "coefficient")
    brigade_price = round(source_price * source_coefficient, 2)
    if not math.isfinite(brigade_price):
        raise ValueError("price_brigade_invalid")

    cur.execute(
        """INSERT INTO brigade_contract_items
             (contract_id,estimate_section,description,work_package,estimate_item_key,
              unit,quantity,price_smeta,price_brigade,done_quantity,
              source_type,source_estimate_version_id,source_section_index,
              source_item_index,source_item_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            contract_id, category or "", name or "", work_package, "", unit or "шт", 0,
            source_price, brigade_price, 0, "pricelist", None, None, None, None,
        ),
    )
    return {"priceSmeta": source_price, "priceBrigade": brigade_price}
