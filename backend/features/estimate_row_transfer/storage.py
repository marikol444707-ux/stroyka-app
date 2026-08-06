"""Parameterized persistence for the inert E4.2 mapping ledger only."""

from decimal import Decimal


PLAN_SELECT = """SELECT id,company_id,project_id,work_package,smeta_type,
       reconciliation_id,base_estimate_id,target_estimate_id,
       target_estimate_version_id,base_sections_sha256,target_sections_sha256,
       base_snapshot_row_count,target_snapshot_row_count,plan_sha256,
       approved_plan_sha256,status,created_by_user_id,created_by_name,
       created_by_role,approved_by_user_id,approved_by_name,approved_by_role,
       approved_at,created_at,updated_at
  FROM public.estimate_row_transfer_plans"""

ENTRY_SELECT = """SELECT id,plan_id,company_id,project_id,source_kind,source_id,
       source_parent_id,request_item_index,source_estimate_id,
       source_estimate_version_id,source_section_index,source_item_index,
       source_item_key,source_sections_sha256,target_estimate_id,
       target_estimate_version_id,target_section_index,target_item_index,
       target_item_key,target_sections_sha256,source_total_quantity,
       source_protected_quantity,source_available_quantity,quantity,created_at
  FROM public.estimate_row_transfer_entries"""


def _row_value(row, key, index):
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[index]
    except (IndexError, TypeError):
        return None


def _id_from_row(row):
    value = _row_value(row, "id", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _quantity(value):
    number = Decimal(str(value))
    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def find_plan_id_by_hash(cur, company_id, reconciliation_id, plan_sha256):
    cur.execute(
        """SELECT id FROM public.estimate_row_transfer_plans
            WHERE company_id=%s AND reconciliation_id=%s AND plan_sha256=%s""",
        (company_id, reconciliation_id, plan_sha256),
    )
    return _id_from_row(cur.fetchone())


def insert_draft(cur, plan, actor):
    base_snapshot = plan["baseSnapshot"]
    target_snapshot = plan["targetSnapshot"]
    cur.execute(
        """INSERT INTO public.estimate_row_transfer_plans
             (company_id,project_id,work_package,smeta_type,reconciliation_id,
              base_estimate_id,target_estimate_id,target_estimate_version_id,
              base_sections_sha256,target_sections_sha256,
              base_snapshot_row_count,target_snapshot_row_count,plan_sha256,
              status,created_by_user_id,created_by_name,created_by_role)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s)
           RETURNING id""",
        (
            plan["companyId"], plan["projectId"], plan["workPackage"],
            plan["smetaType"], plan["reconciliationId"], plan["baseEstimateId"],
            plan["targetEstimateId"], target_snapshot["estimateVersionId"],
            base_snapshot["sectionsSha256"], target_snapshot["sectionsSha256"],
            base_snapshot["rowCount"], target_snapshot["rowCount"],
            plan["planSha256"], actor["id"], str(actor.get("name") or ""),
            str(actor.get("role") or ""),
        ),
    )
    plan_id = _id_from_row(cur.fetchone())
    if not plan_id:
        raise RuntimeError("transfer_plan_insert_failed")
    for entry in plan["entries"]:
        source = entry["source"]
        target = entry["target"]
        cur.execute(
            """INSERT INTO public.estimate_row_transfer_entries
                 (plan_id,company_id,project_id,source_kind,source_id,
                  source_parent_id,request_item_index,source_estimate_id,
                  source_estimate_version_id,source_section_index,source_item_index,
                  source_item_key,source_sections_sha256,target_estimate_id,
                  target_estimate_version_id,target_section_index,target_item_index,
                  target_item_key,target_sections_sha256,source_total_quantity,
                  source_protected_quantity,source_available_quantity,quantity)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s)""",
            (
                plan_id, plan["companyId"], plan["projectId"], entry["sourceKind"],
                entry["sourceId"], entry["sourceParentId"], entry.get("requestItemIndex"),
                source["estimateId"], source["estimateVersionId"], source["sectionIndex"],
                source["itemIndex"], source["itemKey"], source["sectionsSha256"],
                target["estimateId"], target["estimateVersionId"], target["sectionIndex"],
                target["itemIndex"], target["itemKey"], target["sectionsSha256"],
                entry["sourceTotalQuantity"], entry["sourceProtectedQuantity"],
                entry["sourceAvailableQuantity"], entry["quantity"],
            ),
        )
    return plan_id


def _canonical_entry(row):
    source_kind = _row_value(row, "source_kind", 4)
    result = {
        "sourceKind": source_kind,
        "sourceId": _row_value(row, "source_id", 5),
        "sourceParentId": _row_value(row, "source_parent_id", 6),
        "source": {
            "estimateId": _row_value(row, "source_estimate_id", 8),
            "estimateVersionId": _row_value(row, "source_estimate_version_id", 9),
            "sectionIndex": _row_value(row, "source_section_index", 10),
            "itemIndex": _row_value(row, "source_item_index", 11),
            "itemKey": _row_value(row, "source_item_key", 12),
            "sectionsSha256": _row_value(row, "source_sections_sha256", 13),
        },
        "target": {
            "estimateId": _row_value(row, "target_estimate_id", 14),
            "estimateVersionId": _row_value(row, "target_estimate_version_id", 15),
            "sectionIndex": _row_value(row, "target_section_index", 16),
            "itemIndex": _row_value(row, "target_item_index", 17),
            "itemKey": _row_value(row, "target_item_key", 18),
            "sectionsSha256": _row_value(row, "target_sections_sha256", 19),
        },
        "sourceTotalQuantity": _quantity(_row_value(row, "source_total_quantity", 20)),
        "sourceProtectedQuantity": _quantity(_row_value(row, "source_protected_quantity", 21)),
        "sourceAvailableQuantity": _quantity(_row_value(row, "source_available_quantity", 22)),
        "quantity": _quantity(_row_value(row, "quantity", 23)),
    }
    if source_kind == "supply":
        result["requestItemIndex"] = _row_value(row, "request_item_index", 7)
    return result


def _stored_payload(header, entries):
    canonical = {
        "planVersion": 1,
        "companyId": _row_value(header, "company_id", 1),
        "projectId": _row_value(header, "project_id", 2),
        "workPackage": _row_value(header, "work_package", 3),
        "smetaType": _row_value(header, "smeta_type", 4),
        "reconciliationId": _row_value(header, "reconciliation_id", 5),
        "baseEstimateId": _row_value(header, "base_estimate_id", 6),
        "targetEstimateId": _row_value(header, "target_estimate_id", 7),
        "baseSnapshot": {
            "estimateId": _row_value(header, "base_estimate_id", 6),
            "sectionsSha256": _row_value(header, "base_sections_sha256", 9),
            "rowCount": _row_value(header, "base_snapshot_row_count", 11),
        },
        "targetSnapshot": {
            "estimateId": _row_value(header, "target_estimate_id", 7),
            "estimateVersionId": _row_value(header, "target_estimate_version_id", 8),
            "sectionsSha256": _row_value(header, "target_sections_sha256", 10),
            "rowCount": _row_value(header, "target_snapshot_row_count", 12),
        },
        "entries": [_canonical_entry(row) for row in entries],
        "planSha256": _row_value(header, "plan_sha256", 13),
    }
    canonical["entries"].sort(
        key=lambda item: (item["sourceKind"], item["sourceId"], item.get("requestItemIndex"))
    )
    return {
        "id": _id_from_row(header),
        "status": _row_value(header, "status", 15),
        "canonicalPlan": canonical,
        "approvedPlanSha256": _row_value(header, "approved_plan_sha256", 14),
        "createdBy": {
            "userId": _row_value(header, "created_by_user_id", 16),
            "name": _row_value(header, "created_by_name", 17),
            "role": _row_value(header, "created_by_role", 18),
        },
        "approvedBy": {
            "userId": _row_value(header, "approved_by_user_id", 19),
            "name": _row_value(header, "approved_by_name", 20),
            "role": _row_value(header, "approved_by_role", 21),
        } if _row_value(header, "approved_by_user_id", 19) else None,
        "approvedAt": str(_row_value(header, "approved_at", 22) or ""),
        "createdAt": str(_row_value(header, "created_at", 23) or ""),
        "updatedAt": str(_row_value(header, "updated_at", 24) or ""),
    }


def load_stored_plan(cur, plan_id, company_id, *, for_update=False):
    lock_sql = " FOR UPDATE" if for_update else ""
    cur.execute(
        PLAN_SELECT + " WHERE id=%s AND company_id=%s" + lock_sql,
        (plan_id, company_id),
    )
    header = cur.fetchone()
    if not header:
        return None
    cur.execute(ENTRY_SELECT + " WHERE plan_id=%s ORDER BY id", (plan_id,))
    return _stored_payload(header, cur.fetchall() or [])


def approve_plan(cur, *, plan_id, company_id, expected_plan_sha256, actor):
    cur.execute(
        """UPDATE public.estimate_row_transfer_plans
              SET status='approved',approved_plan_sha256=plan_sha256,
                  approved_by_user_id=%s,approved_by_name=%s,approved_by_role=%s,
                  approved_at=NOW(),updated_at=NOW()
            WHERE id=%s AND company_id=%s AND status='draft' AND plan_sha256=%s
            RETURNING id""",
        (
            actor["id"], str(actor.get("name") or ""), str(actor.get("role") or ""),
            plan_id, company_id, expected_plan_sha256,
        ),
    )
    return _id_from_row(cur.fetchone()) == plan_id


def find_other_approved_plan(cur, *, company_id, reconciliation_id, plan_id):
    cur.execute(
        """SELECT id FROM public.estimate_row_transfer_plans
            WHERE company_id=%s AND reconciliation_id=%s
              AND status='approved' AND id<>%s
            ORDER BY id LIMIT 1""",
        (company_id, reconciliation_id, plan_id),
    )
    return _id_from_row(cur.fetchone())
