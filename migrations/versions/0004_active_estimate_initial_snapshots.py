"""Create initial immutable versions for active customer estimates.

Revision ID: 0004_active_estimate_snapshots
Revises: 0003_accounting_link_integrity
Create Date: 2026-08-27
"""

import hashlib
import json
from decimal import Decimal, InvalidOperation

from alembic import op


revision = "0004_active_estimate_snapshots"
down_revision = "0003_accounting_link_integrity"
branch_labels = None
depends_on = None


_ADD_HASH_COLUMN = """
ALTER TABLE public.estimate_versions
ADD COLUMN IF NOT EXISTS sections_sha256 VARCHAR(64) NULL
"""

_ADD_HASH_CHECK = """
DO $estimate_snapshot_hash_check$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='chk_estimate_versions_sections_sha256'
      AND conrelid='public.estimate_versions'::regclass
) THEN
    ALTER TABLE public.estimate_versions
    ADD CONSTRAINT chk_estimate_versions_sections_sha256
    CHECK (
        sections_sha256 IS NULL
        OR sections_sha256 ~ '^[0-9a-f]{64}$'
    );
END IF;
END $estimate_snapshot_hash_check$
"""

_ADD_HASH_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_estimate_versions_estimate_sections_sha256
ON public.estimate_versions(estimate_id,sections_sha256)
WHERE sections_sha256 IS NOT NULL
"""

_MISSING_ACTIVE_ESTIMATES = """
SELECT e.id,e.version,e.sections_json
  FROM public.estimates e
 WHERE e.status='Активная'
   AND COALESCE(e.smeta_type,'Заказчик')='Заказчик'
   AND COALESCE(e.is_template,FALSE)=FALSE
   AND e.company_id IS NOT NULL
   AND e.project_id IS NOT NULL
   AND NOT EXISTS (
       SELECT 1
         FROM public.estimate_versions ev
        WHERE ev.estimate_id=e.id
   )
 ORDER BY e.id
"""

_INSERT_SNAPSHOT = """
INSERT INTO public.estimate_versions
    (estimate_id,version_label,sections_json,total,comment,created_by,
     sections_sha256)
VALUES
    (%(estimate_id)s,%(version_label)s,%(sections_json)s,%(total)s,
     %(comment)s,%(created_by)s,%(sections_sha256)s)
ON CONFLICT DO NOTHING
"""


def _row_mapping(row):
    mapping = getattr(row, "_mapping", None)
    return mapping if mapping is not None else row


def _parse_sections(value):
    sections = json.loads(value) if isinstance(value, str) else value
    if not isinstance(sections, list):
        raise ValueError("active estimate sections must be a list")
    return sections


def _sections_sha256(sections):
    canonical = json.dumps(
        {"sections": _parse_sections(sections)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal(value):
    try:
        number = Decimal(
            str(value if value is not None else 0)
            .replace(" ", "")
            .replace(",", ".")
        )
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)
    return number if number.is_finite() else Decimal(0)


def _snapshot_total(sections):
    total = Decimal(0)
    for section in sections:
        if not isinstance(section, dict):
            continue
        for item in section.get("items") or []:
            if not isinstance(item, dict):
                continue
            quantity = _decimal(item.get("quantity"))
            if item.get("isImported"):
                work = _decimal(
                    item.get("totalWork")
                    or item.get("workTotal")
                    or item.get("workSum")
                )
                material = _decimal(
                    item.get("totalMaterial")
                    or item.get("materialTotal")
                    or item.get("materialSum")
                )
                line_total = _decimal(
                    item.get("lineTotal")
                    or item.get("currentTotal")
                    or item.get("total")
                    or item.get("sum")
                    or item.get("amount")
                    or item.get("totalSum")
                )
                if work or material:
                    total += work + material
                elif line_total:
                    total += line_total
                else:
                    total += quantity * (
                        _decimal(item.get("priceWork"))
                        + _decimal(item.get("priceMaterial"))
                    )
            else:
                total += quantity * (
                    _decimal(item.get("priceWork"))
                    + _decimal(item.get("priceMaterial"))
                )
    return total


def upgrade() -> None:
    op.execute(_ADD_HASH_COLUMN)
    op.execute(_ADD_HASH_CHECK)
    op.execute(_ADD_HASH_INDEX)

    bind = op.get_bind()
    bind.exec_driver_sql(
        "LOCK TABLE public.estimates IN SHARE ROW EXCLUSIVE MODE"
    )
    bind.exec_driver_sql(
        "LOCK TABLE public.estimate_versions IN SHARE ROW EXCLUSIVE MODE"
    )
    rows = bind.exec_driver_sql(_MISSING_ACTIVE_ESTIMATES)
    for raw_row in rows:
        row = _row_mapping(raw_row)
        sections = _parse_sections(row["sections_json"] or "[]")
        bind.exec_driver_sql(_INSERT_SNAPSHOT, {
            "estimate_id": row["id"],
            "version_label": str(row["version"] or "1.0")[:100],
            "sections_json": json.dumps(sections, ensure_ascii=False),
            "total": _snapshot_total(sections),
            "comment": "Автоматическая исходная версия активной сметы",
            "created_by": "system:migration:0004",
            "sections_sha256": _sections_sha256(sections),
        })


def downgrade() -> None:
    # Immutable business snapshots may already be referenced by assignments.
    # A downgrade must never delete them or remove their integrity guards.
    pass
