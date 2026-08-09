"""Shared pure A8 policy for binding open supply to material lineage."""

from collections import defaultdict


LINEAGE_MISSING = "lineage_missing"
LINEAGE_AMBIGUOUS = "lineage_ambiguous"
OPEN_REQUEST_AMBIGUOUS = "open_request_ambiguous"
OPEN_SUPPLY_FIELDS = frozenset({
    "requestId",
    "requestItemIndex",
    "sourceEstimateId",
    "sourceSectionIndex",
    "sourceItemIndex",
    "state",
})


def _coordinate_key(coordinate):
    return (
        coordinate["estimateId"],
        coordinate["sectionIndex"],
        coordinate["itemIndex"],
    )


def _open_base(item):
    if "base" in item:
        return item["base"]
    return {
        "estimateId": item["sourceEstimateId"],
        "sectionIndex": item["sourceSectionIndex"],
        "itemIndex": item["sourceItemIndex"],
    }


def bind_open_supply_to_material_pairs(material_pairs, open_supply):
    """Apply one canonical join policy to already-normalized bounded inputs."""

    pairs_by_base = defaultdict(list)
    for pair in material_pairs:
        pairs_by_base[_coordinate_key(pair["base"])].append(pair)

    candidates = []
    issues = []
    open_by_base = defaultdict(int)
    for item in open_supply:
        base = _open_base(item)
        base_key = _coordinate_key(base)
        open_by_base[base_key] += 1
        matches = pairs_by_base.get(base_key, [])
        if not matches:
            issues.append(LINEAGE_MISSING)
            continue
        if len(matches) != 1:
            issues.append(LINEAGE_AMBIGUOUS)
            continue
        candidates.append({
            "requestId": item["requestId"],
            "requestItemIndex": item["requestItemIndex"],
            **matches[0],
        })
    if any(count > 1 for count in open_by_base.values()):
        issues.append(OPEN_REQUEST_AMBIGUOUS)

    candidates.sort(key=lambda item: (
        item["requestId"],
        item["requestItemIndex"],
        *_coordinate_key(item["base"]),
        *_coordinate_key(item["target"]),
    ))
    return candidates, sorted(set(issues))


__all__ = [
    "LINEAGE_AMBIGUOUS",
    "LINEAGE_MISSING",
    "OPEN_REQUEST_AMBIGUOUS",
    "OPEN_SUPPLY_FIELDS",
    "bind_open_supply_to_material_pairs",
]
