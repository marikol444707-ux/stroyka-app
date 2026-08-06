"""Server-owned writers for brigade contract item source metadata."""

import math


def _finite_number(value, field):
    try:
        number = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}_invalid") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field}_invalid")
    return number


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
