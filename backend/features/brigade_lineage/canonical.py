"""Canonical estimate snapshot serialization shared by audits and writers."""

import hashlib
import json


HASH_CONTRACT = "canonical-json-v1"


def parse_sections(value):
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("estimate snapshot sections must be a list")
    return parsed


def sections_sha256(sections):
    canonical = json.dumps(
        {"sections": parse_sections(sections)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
