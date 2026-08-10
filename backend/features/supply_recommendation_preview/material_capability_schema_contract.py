"""Pure A8.4b1 append-only schema contract and deterministic plan."""

import copy
import hashlib
import json
import re


CONTRACT_VERSION = 1
TABLE_NAME = "supplier_material_capability_assertions"
APPLY_CONFIRMATION = "APPLY_SUPPLIER_MATERIAL_CAPABILITY_SCHEMA"
ADVISORY_LOCK_ID = 8248404
PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTITY_SEQUENCE_NAME = "smca_assertion_id_seq"


def _canonical_sql(value):
    """Preserve the exact deparser expression; trim only outer whitespace."""

    return str(value or "").strip()


def _body_sha256(value):
    normalized = " ".join(str(value or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

PARENT_REQUIRED_COLUMNS = {
    "companies": {"id", "platform_account_id", "active"},
    "platform_accounts": {"id", "active", "status"},
    "company_supplier_links": {
        "id", "company_id", "supplier_id", "platform_account_id", "status",
    },
    "suppliers": {"id", "status", "user_id"},
    "users": {"id", "role", "active"},
    "user_company_roles": {
        "id", "user_id", "company_id", "platform_account_id", "role",
        "active",
    },
}

PARENT_RELATION_CONTRACT = {
    name: {"relkind": "r", "persistence": "p"}
    for name in PARENT_REQUIRED_COLUMNS
}

def _column_contract(
    position,
    data_type,
    *,
    not_null=True,
    default=None,
    identity="",
    collation=None,
):
    return {
        "position": position,
        "type": data_type,
        "notNull": not_null,
        "default": default,
        "identity": identity,
        "generated": "",
        "collation": collation,
    }


COLUMN_CONTRACT = {
    "id": _column_contract(1, "bigint", identity="a"),
    "confirmation_version": _column_contract(2, "smallint"),
    "event_kind": _column_contract(
        3, "character varying(16)", collation="pg_catalog.C"
    ),
    "company_id": _column_contract(4, "integer"),
    "company_supplier_link_id": _column_contract(5, "integer"),
    "supplier_id": _column_contract(6, "integer"),
    "material_identity_sha256": _column_contract(
        7, "character varying(64)", collation="pg_catalog.C"
    ),
    "confirmation_subject_sha256": _column_contract(
        8, "character varying(64)", collation="pg_catalog.C"
    ),
    "actor_membership_id": _column_contract(9, "integer"),
    "actor_user_id": _column_contract(10, "integer"),
    "actor_role": _column_contract(
        11, "character varying(100)", collation="pg_catalog.C"
    ),
    "source_kind": _column_contract(
        12, "character varying(32)", collation="pg_catalog.C"
    ),
    "revokes_assertion_id": _column_contract(
        13, "bigint", not_null=False
    ),
    "created_at": _column_contract(
        14, "timestamp with time zone", default="CURRENT_TIMESTAMP"
    ),
}

CONSTRAINT_CONTRACT = {
    "pk_smca_assertions": {
        "type": "p", "validated": True, "deferrable": False,
        "deferred": False, "definition": "PRIMARY KEY (id)",
    },
    "fk_smca_revokes": {
        "type": "f", "validated": True, "deferrable": False,
        "deferred": False,
        "definition": (
            "FOREIGN KEY (revokes_assertion_id) REFERENCES "
            "supplier_material_capability_assertions(id) ON DELETE RESTRICT"
        ),
    },
    "ck_smca_version": {
        "type": "c", "validated": True, "deferrable": False,
        "deferred": False, "definition": "CHECK (confirmation_version = 1)",
    },
    "ck_smca_event_kind": {
        "type": "c", "validated": True, "deferrable": False,
        "deferred": False,
        "definition": (
            "CHECK (event_kind::text = ANY "
            "(ARRAY['confirmed'::character varying, "
            "'revoked'::character varying]::text[]))"
        ),
    },
    "ck_smca_ids": {
        "type": "c", "validated": True, "deferrable": False,
        "deferred": False,
        "definition": (
            "CHECK (id > 0 AND company_id > 0 AND "
            "company_supplier_link_id > 0 AND supplier_id > 0 AND "
            "actor_membership_id > 0 AND actor_user_id > 0 AND "
            "(revokes_assertion_id IS NULL OR revokes_assertion_id > 0))"
        ),
    },
    "ck_smca_hashes": {
        "type": "c", "validated": True, "deferrable": False,
        "deferred": False,
        "definition": (
            "CHECK (material_identity_sha256::text ~ "
            "'^[0-9a-f]{64}$'::text AND "
            "confirmation_subject_sha256::text ~ "
            "'^[0-9a-f]{64}$'::text)"
        ),
    },
    "ck_smca_actor": {
        "type": "c", "validated": True, "deferrable": False,
        "deferred": False,
        "definition": (
            "CHECK (actor_role::text = 'директор'::text AND "
            "source_kind::text = 'director_manual'::text)"
        ),
    },
    "ck_smca_event_shape": {
        "type": "c", "validated": True, "deferrable": False,
        "deferred": False,
        "definition": (
            "CHECK (event_kind::text = 'confirmed'::text AND "
            "revokes_assertion_id IS NULL OR event_kind::text = "
            "'revoked'::text AND revokes_assertion_id IS NOT NULL)"
        ),
    },
}

for _constraint_name, _constraint_contract in CONSTRAINT_CONTRACT.items():
    _constraint_contract["definition"] = _canonical_sql(
        _constraint_contract["definition"]
    )
    _constraint_contract["noInherit"] = _constraint_name in {
        "pk_smca_assertions", "fk_smca_revokes",
    }
    _constraint_contract["inheritedCount"] = 0
    _constraint_contract["hasParent"] = False
    _constraint_contract["referencesSelf"] = (
        _constraint_name == "fk_smca_revokes"
    )

INDEX_CONTRACT = {
    "pk_smca_assertions": {
        "accessMethod": "btree", "unique": True, "primary": True,
        "exclusion": False,
        "valid": True, "ready": True, "live": True, "checkXmin": False,
        "hasExpressions": False, "predicate": None,
        "keyCount": 1, "attributeCount": 1,
        "keyNames": ["id"], "keyOptions": [0],
        "operatorClasses": ["pg_catalog.int8_ops"],
        "collationsMatchColumns": True,
    },
    "idx_smca_company_subject_id": {
        "accessMethod": "btree", "unique": False, "primary": False,
        "exclusion": False,
        "valid": True, "ready": True, "live": True, "checkXmin": False,
        "hasExpressions": False, "predicate": None,
        "keyCount": 3, "attributeCount": 3,
        "keyNames": ["company_id", "confirmation_subject_sha256", "id"],
        "keyOptions": [0, 0, 0],
        "operatorClasses": [
            "pg_catalog.int4_ops", "pg_catalog.text_ops",
            "pg_catalog.int8_ops",
        ],
        "collationsMatchColumns": True,
    },
    "uq_smca_confirmed_subject": {
        "accessMethod": "btree", "unique": True, "primary": False,
        "exclusion": False,
        "valid": True, "ready": True, "live": True, "checkXmin": False,
        "hasExpressions": False,
        "predicate": "event_kind::text = 'confirmed'::text",
        "keyCount": 2, "attributeCount": 2,
        "keyNames": ["company_id", "confirmation_subject_sha256"],
        "keyOptions": [0, 0],
        "operatorClasses": [
            "pg_catalog.int4_ops", "pg_catalog.text_ops",
        ],
        "collationsMatchColumns": True,
    },
    "uq_smca_revocation_target": {
        "accessMethod": "btree", "unique": True, "primary": False,
        "exclusion": False,
        "valid": True, "ready": True, "live": True, "checkXmin": False,
        "hasExpressions": False,
        "predicate": "event_kind::text = 'revoked'::text",
        "keyCount": 1, "attributeCount": 1,
        "keyNames": ["revokes_assertion_id"],
        "keyOptions": [0],
        "operatorClasses": ["pg_catalog.int8_ops"],
        "collationsMatchColumns": True,
    },
}

for _index_contract in INDEX_CONTRACT.values():
    if _index_contract["predicate"] is not None:
        _index_contract["predicate"] = _canonical_sql(
            _index_contract["predicate"]
        )

TRIGGER_CONTRACT = {
    "smca_assertion_insert_guard": {
        "enabled": "O", "type": 7,
        "function": "public.guard_supplier_material_capability_assertion_insert",
        "condition": None, "argumentsHex": "", "columns": [],
        "constraint": False, "deferrable": False,
        "initiallyDeferred": False, "oldTable": None, "newTable": None,
    },
    "smca_assertion_immutable": {
        "enabled": "O", "type": 27,
        "function": (
            "public.reject_supplier_material_capability_assertion_mutation"
        ),
        "condition": None, "argumentsHex": "", "columns": [],
        "constraint": False, "deferrable": False,
        "initiallyDeferred": False, "oldTable": None, "newTable": None,
    },
    "smca_assertion_no_truncate": {
        "enabled": "O", "type": 34,
        "function": (
            "public.reject_supplier_material_capability_assertion_mutation"
        ),
        "condition": None, "argumentsHex": "", "columns": [],
        "constraint": False, "deferrable": False,
        "initiallyDeferred": False, "oldTable": None, "newTable": None,
    },
}

TABLE_CONTRACT = {
    "relkind": "r",
    "persistence": "p",
    "rowSecurity": False,
    "forceRowSecurity": False,
    "hasRules": False,
    "hasParents": False,
    "hasChildren": False,
    "hasPolicies": False,
}

TABLE_TYPE_CONTRACT = {"type": "c"}

IDENTITY_SEQUENCE_CONTRACT = {
    "name": IDENTITY_SEQUENCE_NAME,
    "relkind": "S",
    "dataType": "bigint",
    "start": 1,
    "increment": 1,
    "minimum": 1,
    "maximum": 9223372036854775807,
    "cache": 1,
    "cycle": False,
    "ownedColumn": "id",
    "dependencyType": "i",
}

RELATION_NAMES = tuple(sorted({
    TABLE_NAME,
    IDENTITY_SEQUENCE_NAME,
    *INDEX_CONTRACT,
}))


CREATE_TABLE_SQL = """
CREATE TABLE public.supplier_material_capability_assertions (
  id BIGINT GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.smca_assertion_id_seq
  ),
  confirmation_version SMALLINT NOT NULL,
  event_kind VARCHAR(16) COLLATE pg_catalog."C" NOT NULL,
  company_id INTEGER NOT NULL,
  company_supplier_link_id INTEGER NOT NULL,
  supplier_id INTEGER NOT NULL,
  material_identity_sha256 VARCHAR(64) COLLATE pg_catalog."C" NOT NULL,
  confirmation_subject_sha256 VARCHAR(64) COLLATE pg_catalog."C" NOT NULL,
  actor_membership_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  actor_role VARCHAR(100) COLLATE pg_catalog."C" NOT NULL,
  source_kind VARCHAR(32) COLLATE pg_catalog."C" NOT NULL,
  revokes_assertion_id BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT pk_smca_assertions PRIMARY KEY (id),
  CONSTRAINT fk_smca_revokes FOREIGN KEY (revokes_assertion_id)
    REFERENCES public.supplier_material_capability_assertions(id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_smca_version CHECK (confirmation_version=1),
  CONSTRAINT ck_smca_event_kind CHECK (
    event_kind IN ('confirmed','revoked')
  ),
  CONSTRAINT ck_smca_ids CHECK (
    id>0 AND company_id>0 AND company_supplier_link_id>0 AND supplier_id>0
    AND actor_membership_id>0 AND actor_user_id>0
    AND (revokes_assertion_id IS NULL OR revokes_assertion_id>0)
  ),
  CONSTRAINT ck_smca_hashes CHECK (
    material_identity_sha256 ~ '^[0-9a-f]{64}$'
    AND confirmation_subject_sha256 ~ '^[0-9a-f]{64}$'
  ),
  CONSTRAINT ck_smca_actor CHECK (
    actor_role='директор' AND source_kind='director_manual'
  ),
  CONSTRAINT ck_smca_event_shape CHECK (
    (event_kind='confirmed' AND revokes_assertion_id IS NULL)
    OR (event_kind='revoked' AND revokes_assertion_id IS NOT NULL)
  )
)
"""

INSERT_GUARD_SQL = """
CREATE FUNCTION public.guard_supplier_material_capability_assertion_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target public.supplier_material_capability_assertions%ROWTYPE;
BEGIN
  PERFORM 1
    FROM public.user_company_roles membership
    JOIN public.users actor_user ON actor_user.id=membership.user_id
    JOIN public.companies company ON company.id=membership.company_id
   WHERE membership.id=NEW.actor_membership_id
     AND membership.user_id=NEW.actor_user_id
     AND membership.company_id=NEW.company_id
     AND membership.role='директор'
     AND membership.active IS TRUE
     AND actor_user.active IS TRUE
     AND company.active IS TRUE
     AND membership.platform_account_id=company.platform_account_id
   LIMIT 1
   FOR SHARE OF membership,actor_user,company;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'supplier_material_capability_director_invalid'
      USING ERRCODE='42501';
  END IF;

  IF NEW.event_kind='confirmed' THEN
    PERFORM 1
      FROM public.companies company
      JOIN public.platform_accounts account
        ON account.id=company.platform_account_id
      JOIN public.company_supplier_links link
        ON link.company_id=company.id
      JOIN public.suppliers supplier ON supplier.id=link.supplier_id
      JOIN public.users supplier_user ON supplier_user.id=supplier.user_id
     WHERE company.id=NEW.company_id
       AND company.active IS TRUE
       AND account.active IS TRUE
       AND account.status='active'
       AND link.id=NEW.company_supplier_link_id
       AND link.company_id=NEW.company_id
       AND link.supplier_id=NEW.supplier_id
       AND link.status='Активный'
       AND (link.platform_account_id IS NULL
            OR link.platform_account_id=company.platform_account_id)
       AND supplier.status='Активный'
       AND supplier_user.role='поставщик'
       AND supplier_user.active IS TRUE
       AND NOT EXISTS (
         SELECT 1
           FROM public.suppliers other_supplier
          WHERE other_supplier.user_id=supplier.user_id
            AND other_supplier.id<>supplier.id
          LIMIT 1
       )
     LIMIT 1
     FOR SHARE OF company,account,link,supplier,supplier_user;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'supplier_material_capability_scope_invalid'
        USING ERRCODE='23514';
    END IF;
  ELSE
    SELECT * INTO target
      FROM public.supplier_material_capability_assertions
     WHERE id=NEW.revokes_assertion_id
     LIMIT 1
     FOR SHARE;
    IF NOT FOUND
       OR target.event_kind<>'confirmed'
       OR target.confirmation_version<>NEW.confirmation_version
       OR target.company_id<>NEW.company_id
       OR target.company_supplier_link_id<>NEW.company_supplier_link_id
       OR target.supplier_id<>NEW.supplier_id
       OR target.material_identity_sha256<>NEW.material_identity_sha256
       OR target.confirmation_subject_sha256<>NEW.confirmation_subject_sha256
    THEN
      RAISE EXCEPTION 'supplier_material_capability_revocation_invalid'
        USING ERRCODE='23514';
    END IF;
  END IF;

  NEW.created_at=transaction_timestamp();
  RETURN NEW;
END;
$$
"""

IMMUTABLE_FUNCTION_SQL = """
CREATE FUNCTION public.reject_supplier_material_capability_assertion_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'supplier_material_capability_assertion_immutable'
    USING ERRCODE='55000';
END;
$$
"""


def _declared_function_body(create_sql):
    before_end, marker, _after_end = str(create_sql).rpartition("$$")
    if not marker:
        raise RuntimeError("material capability function body is missing")
    _before_start, marker, body = before_end.partition("AS $$")
    if not marker:
        raise RuntimeError("material capability function body is missing")
    return body


def _function_contract(create_sql):
    return {
        "language": "plpgsql",
        "returns": "trigger",
        "kind": "f",
        "securityDefiner": False,
        "leakproof": False,
        "volatility": "v",
        "parallel": "u",
        "strict": False,
        "config": [],
        "bodySha256": _body_sha256(_declared_function_body(create_sql)),
    }


FUNCTION_CONTRACT = {
    "guard_supplier_material_capability_assertion_insert": (
        _function_contract(INSERT_GUARD_SQL)
    ),
    "reject_supplier_material_capability_assertion_mutation": (
        _function_contract(IMMUTABLE_FUNCTION_SQL)
    ),
}

CREATE_STEPS = (
    {
        "name": "create_supplier_material_capability_assertions",
        "sql": CREATE_TABLE_SQL.strip(),
        "rollbackSql": (
            "DROP TABLE IF EXISTS "
            "public.supplier_material_capability_assertions;"
        ),
    },
    {
        "name": "create_smca_company_subject_index",
        "sql": """CREATE INDEX idx_smca_company_subject_id
          ON public.supplier_material_capability_assertions
          USING btree (company_id,confirmation_subject_sha256,id)""",
        "rollbackSql": "DROP INDEX IF EXISTS public.idx_smca_company_subject_id;",
    },
    {
        "name": "create_smca_confirmed_subject_unique_index",
        "sql": """CREATE UNIQUE INDEX uq_smca_confirmed_subject
          ON public.supplier_material_capability_assertions
          USING btree (company_id,confirmation_subject_sha256)
          WHERE event_kind='confirmed'""",
        "rollbackSql": "DROP INDEX IF EXISTS public.uq_smca_confirmed_subject;",
    },
    {
        "name": "create_smca_revocation_target_unique_index",
        "sql": """CREATE UNIQUE INDEX uq_smca_revocation_target
          ON public.supplier_material_capability_assertions
          USING btree (revokes_assertion_id)
          WHERE event_kind='revoked'""",
        "rollbackSql": "DROP INDEX IF EXISTS public.uq_smca_revocation_target;",
    },
    {
        "name": "create_smca_insert_guard_function",
        "sql": INSERT_GUARD_SQL.strip(),
        "rollbackSql": (
            "DROP FUNCTION IF EXISTS public."
            "guard_supplier_material_capability_assertion_insert();"
        ),
    },
    {
        "name": "create_smca_insert_guard_trigger",
        "sql": """CREATE TRIGGER smca_assertion_insert_guard
          BEFORE INSERT ON public.supplier_material_capability_assertions
          FOR EACH ROW EXECUTE FUNCTION
          public.guard_supplier_material_capability_assertion_insert()""",
        "rollbackSql": """DROP TRIGGER IF EXISTS smca_assertion_insert_guard
          ON public.supplier_material_capability_assertions;""",
    },
    {
        "name": "create_smca_immutable_function",
        "sql": IMMUTABLE_FUNCTION_SQL.strip(),
        "rollbackSql": (
            "DROP FUNCTION IF EXISTS public."
            "reject_supplier_material_capability_assertion_mutation();"
        ),
    },
    {
        "name": "create_smca_immutable_trigger",
        "sql": """CREATE TRIGGER smca_assertion_immutable
          BEFORE UPDATE OR DELETE
          ON public.supplier_material_capability_assertions
          FOR EACH ROW EXECUTE FUNCTION
          public.reject_supplier_material_capability_assertion_mutation()""",
        "rollbackSql": """DROP TRIGGER IF EXISTS smca_assertion_immutable
          ON public.supplier_material_capability_assertions;""",
    },
    {
        "name": "create_smca_no_truncate_trigger",
        "sql": """CREATE TRIGGER smca_assertion_no_truncate
          BEFORE TRUNCATE ON public.supplier_material_capability_assertions
          FOR EACH STATEMENT EXECUTE FUNCTION
          public.reject_supplier_material_capability_assertion_mutation()""",
        "rollbackSql": """DROP TRIGGER IF EXISTS smca_assertion_no_truncate
          ON public.supplier_material_capability_assertions;""",
    },
)


def material_capability_schema_contract():
    return copy.deepcopy({
        "parentRelations": PARENT_RELATION_CONTRACT,
        "table": TABLE_CONTRACT,
        "tableType": TABLE_TYPE_CONTRACT,
        "identitySequence": IDENTITY_SEQUENCE_CONTRACT,
        "columns": COLUMN_CONTRACT,
        "constraints": CONSTRAINT_CONTRACT,
        "indexes": INDEX_CONTRACT,
        "functions": FUNCTION_CONTRACT,
        "triggers": TRIGGER_CONTRACT,
        "relationNames": list(RELATION_NAMES),
    })


def _columns_ready(actual):
    return type(actual) is dict and actual == COLUMN_CONTRACT


def _positive_int(value):
    return (
        type(value) is int
        and value > 0
    )


def _table_ready(table):
    if type(table) is not dict or not _positive_int(table.get("oid")):
        return False
    return {
        key: table.get(key) for key in TABLE_CONTRACT
    } == TABLE_CONTRACT and set(table) == {"oid", *TABLE_CONTRACT}


def _sequence_ready(sequence, table_oid):
    if type(sequence) is not dict:
        return False
    if not _positive_int(sequence.get("oid")):
        return False
    if sequence.get("tableOid") != table_oid:
        return False
    expected_keys = {"oid", "tableOid", *IDENTITY_SEQUENCE_CONTRACT}
    return (
        set(sequence) == expected_keys
        and {
            key: sequence.get(key) for key in IDENTITY_SEQUENCE_CONTRACT
        } == IDENTITY_SEQUENCE_CONTRACT
    )


def _type_holder_ready(holder, table_oid):
    return (
        type(holder) is dict
        and set(holder) == {"oid", "type", "relationOid"}
        and _positive_int(holder.get("oid"))
        and holder.get("type") == TABLE_TYPE_CONTRACT["type"]
        and holder.get("relationOid") == table_oid
    )


def _indexes_ready(indexes, table_oid):
    if type(indexes) is not dict or set(indexes) != set(INDEX_CONTRACT):
        return False
    for name, expected in INDEX_CONTRACT.items():
        actual = indexes.get(name)
        if type(actual) is not dict:
            return False
        if not _positive_int(actual.get("oid")):
            return False
        if actual.get("tableOid") != table_oid:
            return False
        if set(actual) != {"oid", "tableOid", *expected}:
            return False
        if {key: actual.get(key) for key in expected} != expected:
            return False
    return True


def _holders_ready(holders, table, sequence, indexes):
    if type(holders) is not dict or set(holders) != set(RELATION_NAMES):
        return False
    expected = {
        TABLE_NAME: {"oid": table["oid"], "relkind": "r"},
        IDENTITY_SEQUENCE_NAME: {
            "oid": sequence["oid"], "relkind": "S",
        },
    }
    expected.update({
        name: {"oid": indexes[name]["oid"], "relkind": "i"}
        for name in INDEX_CONTRACT
    })
    return holders == expected


def calculate_material_capability_schema_plan_sha256(changes):
    payload = {
        "domain": "stroyka.supply.material_capability_schema.plan",
        "contractVersion": CONTRACT_VERSION,
        "table": TABLE_NAME,
        "contract": material_capability_schema_contract(),
        "changes": [
            {
                "name": item.get("name"),
                "sql": " ".join(str(item.get("sql") or "").split()),
                "rollbackSql": " ".join(
                    str(item.get("rollbackSql") or "").split()
                ),
            }
            for item in (changes or [])
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_material_capability_schema_plan(catalog):
    expected_keys = {
        "parentColumnsMissing", "parentRelations", "table", "columns", "constraints",
        "indexes", "functions", "triggers", "identitySequence",
        "nameHolders", "typeHolder", "catalogComplete",
    }
    blockers = []
    if not isinstance(catalog, dict) or set(catalog) != expected_keys:
        blockers.append("material_capability_schema_catalog_invalid")
        catalog = {key: None for key in expected_keys}
    missing = catalog.get("parentColumnsMissing")
    if (
        not isinstance(missing, list)
        or missing
        or catalog.get("parentRelations") != PARENT_RELATION_CONTRACT
    ):
        blockers.append("material_capability_parent_schema_not_ready")
    catalog_complete = catalog.get("catalogComplete") is True
    if not catalog_complete:
        blockers.append("material_capability_schema_catalog_incomplete")

    table = catalog.get("table")
    table_absent = table is None
    if table_absent:
        if any(catalog.get(key) for key in (
            "columns", "constraints", "indexes", "functions", "triggers",
            "identitySequence", "nameHolders", "typeHolder",
        )):
            blockers.append("material_capability_schema_object_collision")
    elif catalog_complete:
        table_ready = _table_ready(table)
        table_oid = table.get("oid") if table_ready else None
        sequence_ready = _sequence_ready(
            catalog.get("identitySequence"), table_oid
        )
        indexes_ready = _indexes_ready(
            catalog.get("indexes"), table_oid
        )
        contract_ready = (
            table_ready
            and _columns_ready(catalog.get("columns"))
            and _type_holder_ready(
                catalog.get("typeHolder"), table_oid
            )
            and catalog.get("constraints") == CONSTRAINT_CONTRACT
            and indexes_ready
            and catalog.get("functions") == FUNCTION_CONTRACT
            and catalog.get("triggers") == TRIGGER_CONTRACT
            and sequence_ready
            and _holders_ready(
                catalog.get("nameHolders"), table,
                catalog.get("identitySequence"), catalog.get("indexes"),
            )
        )
        if not contract_ready:
            blockers.append("material_capability_schema_drift")

    changes = []
    if table_absent and not blockers:
        changes = [dict(item) for item in CREATE_STEPS]
    complete = not table_absent and not blockers
    rollback_sql = [
        item["rollbackSql"] for item in reversed(changes)
    ]
    plan_hash = calculate_material_capability_schema_plan_sha256(changes)
    return {
        "contractVersion": CONTRACT_VERSION,
        "ok": not blockers,
        "complete": complete,
        "schemaReady": not blockers,
        "readyForApply": table_absent and not blockers,
        "requiresMaintenanceWindow": True,
        "blockers": sorted(set(blockers)),
        "changeCount": len(changes),
        "changes": changes,
        "rollbackSql": rollback_sql,
        "planSha256": plan_hash,
    }


__all__ = [
    "ADVISORY_LOCK_ID",
    "APPLY_CONFIRMATION",
    "COLUMN_CONTRACT",
    "CONSTRAINT_CONTRACT",
    "CONTRACT_VERSION",
    "CREATE_STEPS",
    "FUNCTION_CONTRACT",
    "IDENTITY_SEQUENCE_NAME",
    "INDEX_CONTRACT",
    "PARENT_RELATION_CONTRACT",
    "PARENT_REQUIRED_COLUMNS",
    "PLAN_SHA256_RE",
    "RELATION_NAMES",
    "TABLE_NAME",
    "TRIGGER_CONTRACT",
    "build_material_capability_schema_plan",
    "calculate_material_capability_schema_plan_sha256",
    "material_capability_schema_contract",
]
