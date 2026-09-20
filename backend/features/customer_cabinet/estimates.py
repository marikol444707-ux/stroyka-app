"""Customer estimate projection: expose contractual prices, not internal rates."""

SECTION_FIELDS = frozenset(('id', 'name'))
ITEM_FIELDS = frozenset((
    'id', 'key', 'itemKey', 'estimateItemKey', 'name', 'unit', 'quantity',
    'type', 'itemType', 'kind', 'code', 'itemCode', 'originalType', 'importKind',
    'isImported', 'priceWork', 'priceMaterial',
    'totalWork', 'workTotal', 'workSum', 'totalMaterial', 'materialTotal', 'materialSum',
    'lineTotal', 'currentTotal', 'total', 'amount', 'sum', 'totalSum', 'estimatedCost',
))


def _scalars(value, fields):
    return {key: value[key] for key in fields if key in value
            and (value[key] is None or isinstance(value[key], (str, int, float, bool)))}


def customer_estimate_sections(sections):
    result = []
    for section in sections if isinstance(sections, list) else []:
        if not isinstance(section, dict):
            continue
        projected = _scalars(section, SECTION_FIELDS)
        items = section.get('items')
        projected['items'] = [_scalars(item, ITEM_FIELDS)
                              for item in (items if isinstance(items, list) else [])
                              if isinstance(item, dict)]
        result.append(projected)
    return result
