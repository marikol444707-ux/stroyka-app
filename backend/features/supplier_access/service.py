def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _supplier_ids(values):
    return sorted({
        supplier_id
        for value in values or []
        for supplier_id in [_positive_int(value)]
        if supplier_id
    })


def supplier_recipient_identity_filter(supplier_ids, supplier_user_id=None):
    normalized_ids = _supplier_ids(supplier_ids)
    user_id = _positive_int(supplier_user_id) or 0
    if not normalized_ids and not user_id:
        return "FALSE", []
    return """(
        recipient.supplier_user_id=%s
        OR recipient.target_supplier_id = ANY(%s::int[])
        OR recipient.supplier_id = ANY(%s::int[])
        OR COALESCE(recipient.supplier_group_ids, '{}'::int[]) && %s::int[]
    )""", [user_id, normalized_ids, normalized_ids, normalized_ids]


def supplier_offer_visibility_filter(supplier_ids, supplier_user_id=None):
    """Build a fail-closed SQL filter for supplier-facing offer reads."""
    normalized_ids = _supplier_ids(supplier_ids)
    user_id = _positive_int(supplier_user_id) or 0
    if not normalized_ids and not user_id:
        return " AND FALSE", []
    recipient_identity_sql, recipient_identity_params = supplier_recipient_identity_filter(
        normalized_ids,
        user_id,
    )

    sql = """
      AND EXISTS (
            SELECT 1
              FROM supply_requests scoped_request
             WHERE scoped_request.id=supplier_offers.request_id
               AND scoped_request.company_id=supplier_offers.company_id
      )
      AND NOT EXISTS (
            SELECT 1
              FROM supply_request_recipients mixed_recipient
             WHERE mixed_recipient.request_id=supplier_offers.request_id
               AND mixed_recipient.company_id IS DISTINCT FROM supplier_offers.company_id
      )
      AND (
            EXISTS (
                SELECT 1
                 FROM supply_request_recipients recipient
                 WHERE recipient.request_id=supplier_offers.request_id
                   AND recipient.company_id=supplier_offers.company_id
                   AND (
                        recipient.target_supplier_id=supplier_offers.supplier_id
                     OR recipient.supplier_id=supplier_offers.supplier_id
                     OR supplier_offers.supplier_id = ANY(COALESCE(recipient.supplier_group_ids, '{}'::int[]))
                   )
                   AND """ + recipient_identity_sql + """
            )
         OR (
                NOT EXISTS (
                    SELECT 1
                      FROM supply_request_recipients any_recipient
                     WHERE any_recipient.request_id=supplier_offers.request_id
                )
            AND supplier_offers.supplier_id = ANY(%s::int[])
            AND EXISTS (
                    SELECT 1
                      FROM supply_requests legacy_request
                     WHERE legacy_request.id=supplier_offers.request_id
                       AND legacy_request.company_id=supplier_offers.company_id
                       AND COALESCE(legacy_request.selected_suppliers, '{}'::int[]) && %s::int[]
                )
         )
      )
    """
    params = recipient_identity_params + [
        normalized_ids,
        normalized_ids,
    ]
    return sql, params


def supplier_invoice_visibility_filter(supplier_ids, supplier_user_id=None):
    """Build supplier-facing invoice scope, preserving direct legacy documents."""
    normalized_ids = _supplier_ids(supplier_ids)
    user_id = _positive_int(supplier_user_id) or 0
    if not normalized_ids:
        return " AND FALSE", []
    offer_sql, offer_params = supplier_offer_visibility_filter(normalized_ids, user_id)
    sql = """ AND si.company_id IS NOT NULL
      AND si.company_id > 0
      AND EXISTS (
            SELECT 1
              FROM companies invoice_company
             WHERE invoice_company.id=si.company_id
      )
      AND si.supplier_id = ANY(%s::int[])
      AND (
            si.offer_id IS NULL
         OR EXISTS (
                SELECT 1
                  FROM supplier_offers
                 WHERE supplier_offers.id=si.offer_id
                   AND supplier_offers.company_id=si.company_id
                   AND supplier_offers.supplier_id = ANY(%s::int[])
    """ + offer_sql + """
            )
      )
    """
    return sql, [normalized_ids, normalized_ids] + offer_params
