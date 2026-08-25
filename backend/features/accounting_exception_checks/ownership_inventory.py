"""Read-only ownership inventory for legacy accounting rows.

This private A11.1 slice classifies ownership evidence only.  It does not
alter schema, backfill rows, register routes, or expose a public API.
"""

from collections import Counter, defaultdict

import psycopg2.extras


SOURCE_LIMIT = 1000
PUBLIC_RECORD_LIMIT = 100

_ACCOUNTING_SOURCES = (
    "staff",
    "accountable_payments",
    "accountable_expenses",
    "expense_reports",
    "salary_payments",
    "own_expenses",
    "expenses",
)
INVENTORY_RECORD_LIMIT = SOURCE_LIMIT * len(_ACCOUNTING_SOURCES)

_SOURCE_QUERIES = (
    (
        "projects",
        """SELECT id,company_id,name
             FROM public.projects
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "staff",
        """SELECT staff_row.id,staff_row.company_id,staff_row.project,
                  ARRAY(
                      SELECT DISTINCT role.company_id
                        FROM public.users user_row
                        JOIN public.user_company_roles role
                          ON role.user_id=user_row.id
                         AND role.active IS TRUE
                       WHERE user_row.active IS TRUE
                         AND (
                             ((NULLIF(BTRIM(staff_row.email_work),'') IS NOT NULL
                               OR NULLIF(BTRIM(staff_row.email_personal),'') IS NOT NULL)
                              AND LOWER(BTRIM(user_row.email)) IN (
                                  LOWER(BTRIM(staff_row.email_work)),
                                  LOWER(BTRIM(staff_row.email_personal))
                              ))
                             OR (NULLIF(BTRIM(staff_row.telegram_id),'') IS NOT NULL
                                 AND user_row.telegram_id=staff_row.telegram_id)
                             OR (NULLIF(BTRIM(staff_row.telegram_chat_id),'') IS NOT NULL
                                 AND user_row.telegram_chat_id=staff_row.telegram_chat_id)
                         )
                       ORDER BY role.company_id
                  ) AS exact_identity_company_ids
             FROM public.staff staff_row
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "accountable_payments",
        """SELECT id,project_name,given_to_id
             FROM public.accountable_payments
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "accountable_expenses",
        """SELECT id,payment_id,project_name
             FROM public.accountable_expenses
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "expense_reports",
        """SELECT id,employee_id,project_name
             FROM public.expense_reports
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "salary_payments",
        """SELECT id,staff_id
             FROM public.salary_payments
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "own_expenses",
        """SELECT own_row.id,own_row.project_name,own_row.employee_id,
                  ARRAY(
                      SELECT DISTINCT role.company_id
                        FROM public.users user_row
                        JOIN public.user_company_roles role
                          ON role.user_id=user_row.id
                         AND role.active IS TRUE
                       WHERE user_row.id=own_row.employee_id
                         AND user_row.active IS TRUE
                       ORDER BY role.company_id
                  ) AS employee_user_company_ids,
                  ARRAY(
                      SELECT DISTINCT role.company_id
                        FROM public.staff staff_row
                        JOIN public.users user_row
                          ON user_row.active IS TRUE
                         AND (
                             ((NULLIF(BTRIM(staff_row.email_work),'') IS NOT NULL
                               OR NULLIF(BTRIM(staff_row.email_personal),'') IS NOT NULL)
                              AND LOWER(BTRIM(user_row.email)) IN (
                                  LOWER(BTRIM(staff_row.email_work)),
                                  LOWER(BTRIM(staff_row.email_personal))
                              ))
                             OR (NULLIF(BTRIM(staff_row.telegram_id),'') IS NOT NULL
                                 AND user_row.telegram_id=staff_row.telegram_id)
                             OR (NULLIF(BTRIM(staff_row.telegram_chat_id),'') IS NOT NULL
                                 AND user_row.telegram_chat_id=staff_row.telegram_chat_id)
                         )
                        JOIN public.user_company_roles role
                          ON role.user_id=user_row.id
                         AND role.active IS TRUE
                       WHERE staff_row.id=own_row.employee_id
                       ORDER BY role.company_id
                  ) AS employee_staff_identity_company_ids
             FROM public.own_expenses own_row
            ORDER BY id
            LIMIT %s""",
    ),
    (
        "expenses",
        """SELECT id,project,own_expense_id
             FROM public.expenses
            ORDER BY id
            LIMIT %s""",
    ),
)


def _input_error():
    return ValueError("accounting_ownership_input_invalid")


def _positive_int(value):
    if type(value) is not int or value <= 0:
        return None
    return value


def _text(value):
    return value if type(value) is str else ""


def _company_candidates(row, *keys):
    candidates = set()
    for key in keys:
        if key not in row:
            continue
        values = row[key]
        if type(values) not in (list, tuple):
            raise _input_error() from None
        for value in values:
            company_id = _positive_int(value)
            if company_id is None:
                raise _input_error() from None
            candidates.add(company_id)
    return sorted(candidates)


def _rows_for_source(rows_by_source, source):
    if not isinstance(rows_by_source, dict):
        raise _input_error() from None
    rows = rows_by_source.get(source, [])
    if type(rows) not in (list, tuple):
        raise _input_error() from None
    normalized = []
    seen = set()
    for raw in rows:
        try:
            row = dict(raw or {})
        except (TypeError, ValueError):
            raise _input_error() from None
        record_id = _positive_int(row.get("id"))
        if not record_id or record_id in seen:
            raise _input_error() from None
        seen.add(record_id)
        normalized.append(row)
    return sorted(normalized, key=lambda item: item["id"])


def _owner(company_id, project_id=None, project_name=""):
    return {
        "companyId": _positive_int(company_id),
        "projectId": _positive_int(project_id),
        "projectName": _text(project_name),
    }


def _decision(source, record_id, classification, reason, owner=None):
    owner = owner or {}
    return {
        "source": source,
        "recordId": record_id,
        "classification": classification,
        "reason": reason,
        "companyId": owner.get("companyId") if classification == "provable" else None,
        "projectId": owner.get("projectId") if classification == "provable" else None,
    }


def _project_indexes(project_rows):
    by_id = {}
    by_name = defaultdict(list)
    for row in project_rows:
        project_id = _positive_int(row.get("id"))
        company_id = _positive_int(row.get("company_id"))
        project_name = _text(row.get("name"))
        if not project_id or not company_id or not project_name:
            continue
        owner = _owner(company_id, project_id, project_name)
        by_id[project_id] = owner
        by_name[project_name].append(owner)
    return by_id, dict(by_name)


def _project_proof(project_name, projects_by_name):
    if not project_name:
        return "ambiguous", "project_owner_missing", None
    candidates = projects_by_name.get(project_name, [])
    if not candidates:
        return "orphaned", "project_not_found", None
    if len(candidates) != 1:
        return "ambiguous", "project_name_ambiguous", None
    return "provable", "project_owner_exact", candidates[0]


def _staff_decisions(staff_rows, projects_by_name):
    decisions = {}
    raw_by_id = {}
    for row in staff_rows:
        staff_id = row["id"]
        raw_by_id[staff_id] = row
        project_name = _text(row.get("project"))
        classification, reason, owner = _project_proof(project_name, projects_by_name)
        stored_company_id = _positive_int(row.get("company_id"))
        identity_candidates = _company_candidates(row, "exact_identity_company_ids")
        identity_owner = _owner(identity_candidates[0]) if len(identity_candidates) == 1 else None
        if (
            classification == "provable"
            and identity_owner
            and identity_owner["companyId"] != owner["companyId"]
        ):
            classification = "conflicting"
            reason = "staff_identity_project_owner_mismatch"
            owner = None
        elif classification == "provable" and stored_company_id and stored_company_id != owner["companyId"]:
            classification = "conflicting"
            reason = "staff_project_owner_mismatch"
            owner = None
        elif classification == "provable":
            reason = "staff_project_owner_exact"
        elif identity_owner and stored_company_id and stored_company_id != identity_owner["companyId"]:
            classification = "conflicting"
            reason = "staff_identity_owner_mismatch"
            owner = None
        elif identity_owner:
            classification = "provable"
            reason = "staff_identity_owner_exact"
            owner = identity_owner
        elif len(identity_candidates) > 1:
            classification = "ambiguous"
            reason = "staff_identity_owner_ambiguous"
        elif not project_name:
            classification = "ambiguous"
            reason = "staff_owner_unverified"
        decisions[staff_id] = _decision("staff", staff_id, classification, reason, owner)
    return decisions, raw_by_id


def _staff_owner(staff_id, staff_decisions):
    if not staff_id:
        return None
    decision = staff_decisions.get(staff_id)
    if decision and decision["classification"] == "provable":
        return _owner(decision["companyId"], decision["projectId"])
    return None


def _project_and_staff_decision(source, row, staff_key, staff_decisions, staff_rows, projects_by_name):
    record_id = row["id"]
    project_name = _text(row.get("project_name"))
    classification, reason, project_owner = _project_proof(project_name, projects_by_name)
    staff_id = _positive_int(row.get(staff_key))
    if staff_key in row and row.get(staff_key) is not None and not staff_id:
        return _decision(source, record_id, "orphaned", "staff_not_found")
    if staff_id:
        staff_row = staff_rows.get(staff_id)
        if not staff_row:
            return _decision(source, record_id, "orphaned", "staff_not_found")
        staff_decision = staff_decisions.get(staff_id)
        staff_owner = _staff_owner(staff_id, staff_decisions)
        if project_owner and staff_owner and (
            project_owner["companyId"] != staff_owner["companyId"]
            or (
                staff_owner["projectId"] is not None
                and project_owner["projectId"] != staff_owner["projectId"]
            )
        ):
            return _decision(source, record_id, "conflicting", "staff_project_owner_mismatch")
        stored_staff_company = _positive_int(staff_row.get("company_id"))
        if project_owner and stored_staff_company and stored_staff_company != project_owner["companyId"]:
            return _decision(source, record_id, "conflicting", "staff_project_owner_mismatch")
        if not staff_owner and classification != "provable":
            return _decision(
                source,
                record_id,
                staff_decision["classification"],
                "staff_owner_not_provable",
            )
        if not staff_owner and classification == "provable":
            return _decision(source, record_id, "conflicting", "staff_project_owner_mismatch")
        if classification != "provable" and staff_owner and staff_owner["projectId"] is not None:
            classification = "provable"
            reason = "staff_project_owner_exact"
            project_owner = staff_owner
    return _decision(source, record_id, classification, reason, project_owner)


def _payment_decisions(payment_rows, staff_decisions, staff_rows, projects_by_name):
    decisions = {}
    for row in payment_rows:
        decision = _project_and_staff_decision(
            "accountable_payments",
            row,
            "given_to_id",
            staff_decisions,
            staff_rows,
            projects_by_name,
        )
        decisions[row["id"]] = decision
    return decisions


def _expense_decisions(expense_rows, payment_decisions, projects_by_name):
    decisions = {}
    for row in expense_rows:
        record_id = row["id"]
        payment_id = _positive_int(row.get("payment_id"))
        parent = payment_decisions.get(payment_id) if payment_id else None
        if not parent:
            decision = _decision("accountable_expenses", record_id, "orphaned", "parent_payment_not_found")
        elif parent["classification"] != "provable":
            decision = _decision(
                "accountable_expenses",
                record_id,
                parent["classification"],
                "parent_payment_not_provable",
            )
        else:
            project_name = _text(row.get("project_name"))
            if project_name:
                classification, _reason, project_owner = _project_proof(project_name, projects_by_name)
                if classification != "provable" or (
                    project_owner["companyId"] != parent["companyId"]
                    or project_owner["projectId"] != parent["projectId"]
                ):
                    decision = _decision(
                        "accountable_expenses",
                        record_id,
                        "conflicting",
                        "expense_parent_project_mismatch",
                    )
                else:
                    decision = _decision(
                        "accountable_expenses",
                        record_id,
                        "provable",
                        "parent_payment_owner_exact",
                        _owner(parent["companyId"], parent["projectId"]),
                    )
            else:
                decision = _decision(
                    "accountable_expenses",
                    record_id,
                    "provable",
                    "parent_payment_owner_exact",
                    _owner(parent["companyId"], parent["projectId"]),
                )
        decisions[record_id] = decision
    return decisions


def _salary_decisions(salary_rows, staff_decisions):
    decisions = {}
    for row in salary_rows:
        record_id = row["id"]
        staff_id = _positive_int(row.get("staff_id"))
        staff = staff_decisions.get(staff_id) if staff_id else None
        if not staff:
            decision = _decision("salary_payments", record_id, "orphaned", "staff_not_found")
        elif staff["classification"] != "provable":
            decision = _decision(
                "salary_payments",
                record_id,
                staff["classification"],
                "staff_owner_not_provable",
            )
        else:
            decision = _decision(
                "salary_payments",
                record_id,
                "provable",
                "staff_owner_exact",
                _owner(staff["companyId"], staff["projectId"]),
            )
        decisions[record_id] = decision
    return decisions


def _own_expense_decisions(own_expense_rows, projects_by_name):
    decisions = {}
    for row in own_expense_rows:
        record_id = row["id"]
        project_name = _text(row.get("project_name"))
        classification, reason, owner = _project_proof(project_name, projects_by_name)
        identity_candidates = _company_candidates(
            row,
            "employee_user_company_ids",
            "employee_staff_identity_company_ids",
        )
        identity_owner = _owner(identity_candidates[0]) if len(identity_candidates) == 1 else None
        if (
            classification == "provable"
            and identity_owner
            and identity_owner["companyId"] != owner["companyId"]
        ):
            classification = "conflicting"
            reason = "own_expense_employee_project_owner_mismatch"
            owner = None
        elif classification == "provable":
            reason = "own_expense_project_owner_exact"
        elif not project_name and identity_owner:
            classification = "provable"
            reason = "own_expense_employee_owner_exact"
            owner = identity_owner
        elif not project_name and len(identity_candidates) > 1:
            classification = "ambiguous"
            reason = "own_expense_employee_owner_ambiguous"
        elif not project_name:
            reason = "own_expense_owner_unverified"
        decisions[record_id] = _decision(
            "own_expenses",
            record_id,
            classification,
            reason,
            owner,
        )
    return decisions


def _manual_expense_decisions(expense_rows, own_expense_decisions, projects_by_name):
    decisions = {}
    for row in expense_rows:
        record_id = row["id"]
        raw_parent_id = row.get("own_expense_id")
        parent_id = _positive_int(raw_parent_id)
        if raw_parent_id is not None and not parent_id:
            decision = _decision("expenses", record_id, "orphaned", "own_expense_parent_not_found")
        elif parent_id:
            parent = own_expense_decisions.get(parent_id)
            if not parent:
                decision = _decision("expenses", record_id, "orphaned", "own_expense_parent_not_found")
            elif parent["classification"] != "provable":
                decision = _decision(
                    "expenses",
                    record_id,
                    parent["classification"],
                    "own_expense_parent_not_provable",
                )
            else:
                project_name = _text(row.get("project"))
                classification, _reason, project_owner = _project_proof(
                    project_name,
                    projects_by_name,
                ) if project_name else (
                    "provable",
                    "own_expense_parent_owner_exact",
                    _owner(parent["companyId"], parent["projectId"]),
                )
                if classification != "provable" or (
                    project_owner["companyId"] != parent["companyId"]
                    or project_owner["projectId"] != parent["projectId"]
                ):
                    decision = _decision(
                        "expenses",
                        record_id,
                        "conflicting",
                        "manual_expense_parent_project_mismatch",
                    )
                else:
                    decision = _decision(
                        "expenses",
                        record_id,
                        "provable",
                        "own_expense_parent_owner_exact",
                        _owner(parent["companyId"], parent["projectId"]),
                    )
        else:
            project_name = _text(row.get("project"))
            classification, reason, owner = _project_proof(project_name, projects_by_name)
            if classification == "provable":
                reason = "manual_expense_project_owner_exact"
            elif not project_name:
                reason = "manual_expense_owner_unverified"
            decision = _decision("expenses", record_id, classification, reason, owner)
        decisions[record_id] = decision
    return decisions


def _classify_accounting_ownership_records(rows_by_source):
    project_rows = _rows_for_source(rows_by_source, "projects")
    source_rows = {
        source: _rows_for_source(rows_by_source, source)
        for source in _ACCOUNTING_SOURCES
    }
    _projects_by_id, projects_by_name = _project_indexes(project_rows)
    staff_decisions, staff_rows = _staff_decisions(source_rows["staff"], projects_by_name)
    payment_decisions = _payment_decisions(
        source_rows["accountable_payments"],
        staff_decisions,
        staff_rows,
        projects_by_name,
    )
    expense_decisions = _expense_decisions(
        source_rows["accountable_expenses"],
        payment_decisions,
        projects_by_name,
    )
    report_decisions = {
        row["id"]: _project_and_staff_decision(
            "expense_reports",
            row,
            "employee_id",
            staff_decisions,
            staff_rows,
            projects_by_name,
        )
        for row in source_rows["expense_reports"]
    }
    salary_decisions = _salary_decisions(source_rows["salary_payments"], staff_decisions)
    own_expense_decisions = _own_expense_decisions(
        source_rows["own_expenses"],
        projects_by_name,
    )
    manual_expense_decisions = _manual_expense_decisions(
        source_rows["expenses"],
        own_expense_decisions,
        projects_by_name,
    )

    decisions_by_source = {
        "staff": staff_decisions,
        "accountable_payments": payment_decisions,
        "accountable_expenses": expense_decisions,
        "expense_reports": report_decisions,
        "salary_payments": salary_decisions,
        "own_expenses": own_expense_decisions,
        "expenses": manual_expense_decisions,
    }
    all_records = [
        decisions_by_source[source][record_id]
        for source in _ACCOUNTING_SOURCES
        for record_id in sorted(decisions_by_source[source])
    ]
    summary_counts = Counter(item["classification"] for item in all_records)
    summary = {
        classification: summary_counts.get(classification, 0)
        for classification in ("provable", "ambiguous", "orphaned", "conflicting")
    }
    return all_records, summary


def _build_inventory_report(rows_by_source, max_records):
    all_records, summary = _classify_accounting_ownership_records(rows_by_source)
    return {
        "version": "accounting-ownership-inventory-v1",
        "dryRun": True,
        "writesAttempted": 0,
        "summary": summary,
        "totalRecords": len(all_records),
        "records": all_records[:max_records],
        "truncated": len(all_records) > max_records,
    }


def classify_accounting_ownership(rows_by_source, *, max_records=PUBLIC_RECORD_LIMIT):
    if type(max_records) is not int or max_records < 1 or max_records > PUBLIC_RECORD_LIMIT:
        raise _input_error() from None
    return _build_inventory_report(rows_by_source, max_records)


def _collect_accounting_ownership_rows(cursor):
    rows_by_source = {}
    for source, query in _SOURCE_QUERIES:
        cursor.execute(query, (SOURCE_LIMIT + 1,))
        rows = list(cursor.fetchall() or [])
        if len(rows) > SOURCE_LIMIT:
            raise ValueError("accounting_ownership_source_limit") from None
        rows_by_source[source] = rows
    return rows_by_source


def run_accounting_ownership_inventory(connection, *, max_records=INVENTORY_RECORD_LIMIT):
    if type(max_records) is not int or max_records < 1 or max_records > INVENTORY_RECORD_LIMIT:
        raise _input_error() from None
    cursor = None
    try:
        connection.set_session(readonly=True, autocommit=False)
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        rows_by_source = _collect_accounting_ownership_rows(cursor)
        return _build_inventory_report(rows_by_source, max_records)
    finally:
        try:
            connection.rollback()
        finally:
            if cursor is not None:
                cursor.close()
