"""Shared bounded schema-column probe for read-only impact previews."""

import json


SCHEMA_SCAN_LIMIT_EXCEEDED = "schema_scan_limit_exceeded"


def required_column_count(required_columns):
    """Return the exact number of allowlisted table/column pairs."""

    return sum(len(columns) for columns in required_columns.values())


def collect_missing_columns(cur, required_columns):
    """Read only allowlisted public columns with one hard row sentinel."""

    requirements = [
        {"table_name": table, "column_name": column}
        for table, columns in sorted(required_columns.items())
        for column in sorted(columns)
    ]
    limit = len(requirements)
    cur.execute(
        """SELECT required.table_name,required.column_name
             FROM jsonb_to_recordset(%s::jsonb)
                  AS required(table_name text,column_name text)
             JOIN LATERAL (
                  SELECT 1
                    FROM pg_catalog.pg_class relation
                    JOIN pg_catalog.pg_attribute attribute
                      ON attribute.attrelid=relation.oid
                   WHERE relation.relnamespace=(
                             SELECT namespace.oid
                               FROM pg_catalog.pg_namespace namespace
                              WHERE namespace.nspname=%s
                                AND NOT pg_catalog.pg_is_other_temp_schema(
                                    namespace.oid
                                )
                              LIMIT 1
                         )
                     AND relation.relname=required.table_name
                     AND relation.relkind=ANY('{r,v,f,p}'::"char"[])
                     AND attribute.attname=required.column_name
                     AND attribute.attnum>0
                     AND NOT attribute.attisdropped
                     AND (
                           pg_catalog.pg_has_role(
                               relation.relowner,'USAGE'
                           )
                           OR pg_catalog.has_column_privilege(
                               relation.oid,attribute.attnum,
                               'SELECT, INSERT, UPDATE, REFERENCES'
                           )
                         )
                   LIMIT 1
             ) AS actual ON TRUE
            ORDER BY required.table_name,required.column_name
            LIMIT %s""",
        (
            json.dumps(
                requirements,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "public",
            limit + 1,
        ),
    )
    rows = list(cur.fetchall() or [])
    if len(rows) > limit:
        return [SCHEMA_SCAN_LIMIT_EXCEEDED]
    present = {
        (str(row.get("table_name") or ""), str(row.get("column_name") or ""))
        for row in rows
    }
    return sorted(
        table + "." + column
        for table, columns in required_columns.items()
        for column in columns
        if (table, column) not in present
    )


__all__ = [
    "SCHEMA_SCAN_LIMIT_EXCEEDED",
    "collect_missing_columns",
    "required_column_count",
]
