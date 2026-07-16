from collections import defaultdict


def _value(row, key, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return default


def _positive_id(value):
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _canonical_score(row, identity_keys):
    details = (
        "inn",
        "ogrn",
        "kpp",
        "phone",
        "email",
        "legal_address",
        "actual_address",
        "website",
        "specialization",
    )
    supplier_id = _positive_id(_value(row, "id"))
    return (
        int(bool(_value(row, "user_id") or _value(row, "registered_at"))),
        len(identity_keys(row or {})),
        sum(1 for key in details if str(_value(row, key, "") or "").strip()),
        int(str(_value(row, "status", "") or "").strip().lower() == "активный"),
        -supplier_id,
    )


def build_supplier_relation_metadata(
    supplier_rows,
    alias_rows,
    *,
    identity_keys,
    normalize_name_key,
):
    """Build non-destructive supplier groups from strong identity and manual links."""
    suppliers = {
        supplier_id: row
        for row in (supplier_rows or [])
        if (supplier_id := _positive_id(_value(row, "id")))
    }
    parent = {supplier_id: supplier_id for supplier_id in suppliers}

    def find(supplier_id):
        while parent[supplier_id] != supplier_id:
            parent[supplier_id] = parent[parent[supplier_id]]
            supplier_id = parent[supplier_id]
        return supplier_id

    def union(left, right):
        if left not in parent or right not in parent:
            return
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    identity_owner = {}
    supplier_ids_by_name = defaultdict(list)
    for supplier_id, row in suppliers.items():
        name_key = normalize_name_key(_value(row, "name", "") or "")
        if name_key:
            supplier_ids_by_name[name_key].append(supplier_id)
        for key in identity_keys(row or {}):
            owner_id = identity_owner.get(key)
            if owner_id:
                union(supplier_id, owner_id)
            else:
                identity_owner[key] = supplier_id

    manual_aliases = []
    for alias in alias_rows or []:
        supplier_id = _positive_id(_value(alias, "supplier_id"))
        if supplier_id not in suppliers:
            continue
        source = str(_value(alias, "source", "") or "").strip()
        related_supplier_id = _positive_id(_value(alias, "related_supplier_id"))
        if related_supplier_id and source == "manual_supplier_duplicate_link":
            union(supplier_id, related_supplier_id)
        for key in identity_keys(alias or {}):
            owner_id = identity_owner.get(key)
            if owner_id:
                union(supplier_id, owner_id)
            else:
                identity_owner[key] = supplier_id
        alias_key = str(_value(alias, "alias_key", "") or "").strip()
        if source == "manual_supplier_duplicate_link" and alias_key:
            manual_aliases.append((supplier_id, alias_key))

    manual_keys_by_supplier = defaultdict(set)
    for supplier_id, alias_key in manual_aliases:
        manual_keys_by_supplier[supplier_id].add(alias_key)
    for supplier_id, alias_key in manual_aliases:
        candidates = supplier_ids_by_name.get(alias_key, [])
        candidates = [candidate_id for candidate_id in candidates if candidate_id != supplier_id]
        source_name_key = normalize_name_key(_value(suppliers[supplier_id], "name", "") or "")
        reciprocal_candidates = [
            candidate_id
            for candidate_id in candidates
            if source_name_key in manual_keys_by_supplier.get(candidate_id, set())
        ]
        if source_name_key and len(reciprocal_candidates) == 1:
            union(supplier_id, reciprocal_candidates[0])

    groups = defaultdict(list)
    for supplier_id in suppliers:
        groups[find(supplier_id)].append(supplier_id)

    metadata = {}
    for supplier_ids in groups.values():
        related_ids = sorted(supplier_ids)
        canonical_id = max(
            related_ids,
            key=lambda supplier_id: _canonical_score(suppliers[supplier_id], identity_keys),
        )
        group_metadata = {
            "relatedSupplierIds": related_ids,
            "canonicalSupplierId": canonical_id,
            "duplicateCount": len(related_ids),
        }
        for supplier_id in related_ids:
            metadata[supplier_id] = dict(group_metadata)
    return metadata
