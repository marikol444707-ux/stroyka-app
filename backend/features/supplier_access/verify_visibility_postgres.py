"""Opt-in PostgreSQL check: READ ONLY transaction, synthetic CTEs, no table writes.

Run with the application's configured database:
    python -m backend.features.supplier_access.verify_visibility_postgres
"""

from .service import supplier_offer_visibility_filter, supplier_invoice_visibility_filter
from .supply_request_workflow import (
    SUPPLIER_REQUEST_VISIBILITY_SQL,
    supplier_request_visibility_params,
)


FIXTURE = """
WITH supply_requests AS (
    SELECT 1 AS id, %s::int AS company_id,
           CASE WHEN %s THEN NOW() END AS prorab_confirmed_at,
           CASE WHEN %s THEN NOW() END AS director_approved_at,
           ARRAY[7]::int[] AS selected_suppliers
), supply_request_recipients AS (
    SELECT 1 AS request_id, %s::int AS company_id,
           %s::boolean AS visible_to_supplier, 7 AS target_supplier_id,
           7 AS supplier_id, 42 AS supplier_user_id,
           ARRAY[7]::int[] AS supplier_group_ids WHERE %s
    UNION ALL
    SELECT 1, 101, FALSE, 3, 3, 42, ARRAY[3]::int[] WHERE %s
), supplier_offers AS (
    SELECT 1 AS id, 1 AS request_id, %s::int AS company_id,
           %s::int AS supplier_id
), companies AS (
    SELECT %s::int AS id
), supplier_invoices AS (
    SELECT 1 AS id, 1 AS offer_id, %s::int AS company_id, %s::int AS supplier_id
)
"""


def verify(connection):
    connection.set_session(readonly=True, autocommit=False)
    # name, overrides, expected(request, offer, invoice)
    cases = [
        ("company A", {}, (True, True, True)),
        ("company B, same supplier", {"company": 202, "recipient_company": 202, "offer_company": 202}, (True, True, True)),
        ("outsider", {"ids": [99], "user": 99}, (False, False, False)),
        ("no foreman confirmation", {"confirmed": False}, (False, False, False)),
        ("no director approval", {"approved": False}, (False, False, False)),
        ("hidden recipient", {"visible": False}, (False, False, False)),
        ("wrong recipient company", {"recipient_company": 202}, (False, False, False)),
        ("wrong offer company", {"offer_company": 202}, (True, False, False)),
        ("legacy approved", {"recipient": False}, (True, True, True)),
        ("legacy unapproved", {"recipient": False, "confirmed": False}, (False, False, False)),
        ("legacy cannot bypass hidden recipient", {"visible": False}, (False, False, False)),
        ("visible sibling does not reveal hidden offer", {"ids": [3, 7], "hidden_sibling": True, "offer_supplier": 3}, (True, False, False)),
        ("user id alone cannot bypass request scope", {"ids": []}, (False, False, False)),
    ]
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_read_only")
            assert cursor.fetchone()[0] == "on"
            for name, overrides, expected in cases:
                values = dict(company=101, recipient_company=101, offer_company=101,
                              confirmed=True, approved=True, visible=True, recipient=True,
                              hidden_sibling=False, offer_supplier=7, ids=[7], user=42)
                values.update(overrides)
                fixture_params = [values[key] for key in (
                    "company", "confirmed", "approved", "recipient_company", "visible",
                    "recipient", "hidden_sibling", "offer_company", "offer_supplier",
                    "company", "company", "offer_supplier",
                )]
                offer_sql, offer_params = supplier_offer_visibility_filter(values["ids"], values["user"])
                invoice_sql, invoice_params = supplier_invoice_visibility_filter(values["ids"], values["user"])
                queries = [
                    ("SELECT id FROM supply_requests WHERE " + SUPPLIER_REQUEST_VISIBILITY_SQL,
                     supplier_request_visibility_params(values["ids"])),
                    ("SELECT id FROM supplier_offers WHERE TRUE" + offer_sql, offer_params),
                    ("SELECT id FROM supplier_invoices si WHERE TRUE" + invoice_sql, invoice_params),
                ]
                actual = []
                for sql, params in queries:
                    cursor.execute(FIXTURE + sql, fixture_params + params)
                    actual.append(bool(cursor.fetchall()))
                assert tuple(actual) == expected, (name, actual, expected)
                print("PASS:", name)
    finally:
        connection.rollback()


if __name__ == "__main__":
    from backend.db import get_db

    connection = get_db()
    try:
        verify(connection)
    finally:
        connection.close()
