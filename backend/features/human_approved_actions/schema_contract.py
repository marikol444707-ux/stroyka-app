"""Private A12.2 append-only ledger schema and guarded migration.

The module is intentionally unregistered.  Dry-run is the default and an
apply requires the exact catalog-derived change count and plan SHA-256.
"""

import copy
import hashlib
import json
import re

import psycopg2.extras


CONTRACT_VERSION = 1
PROPOSAL_TABLE = "human_action_proposals"
EVENT_TABLE = "human_action_events"
APPLY_CONFIRMATION = "APPLY_HUMAN_ACTION_LEDGER_SCHEMA"
ADVISORY_LOCK_ID = 12012002
_PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACTION_KIND = "warehouse_anomaly_review_acknowledged"
_EFFECT_KIND = "audit_only"
_PROPOSAL_SEQUENCE = "human_action_proposal_id_seq"
_EVENT_SEQUENCE = "human_action_event_id_seq"

PARENT_REQUIRED_COLUMNS = {
    "agent_jobs": {"id", "company_id", "project_id"},
    "companies": {"id"},
    "projects": {"id", "company_id"},
    "users": {"id"},
    "user_company_roles": {"id", "user_id", "company_id", "active"},
}

_PARENT_RELATIONS = {
    name: {"relkind": "r", "persistence": "p"}
    for name in PARENT_REQUIRED_COLUMNS
}


def _column(position, data_type, *, default=None, identity="", collation=None):
    return {
        "position": position,
        "type": data_type,
        "notNull": True,
        "default": default,
        "identity": identity,
        "generated": "",
        "collation": collation,
    }


_PROPOSAL_COLUMNS = {
    "id": _column(1, "bigint", identity="a"),
    "contract_version": _column(2, "smallint"),
    "action_kind": _column(3, "text", collation="pg_catalog.C"),
    "effect_kind": _column(4, "text", collation="pg_catalog.C"),
    "company_id": _column(5, "integer"),
    "project_id": _column(6, "integer"),
    "source_job_id": _column(7, "bigint"),
    "subject_kind": _column(8, "text", collation="pg_catalog.C"),
    "subject_id": _column(9, "bigint"),
    "anomaly_code": _column(10, "text", collation="pg_catalog.C"),
    "source_content_version": _column(11, "smallint"),
    "source_content_sha256": _column(12, "text", collation="pg_catalog.C"),
    "proposer_user_id": _column(13, "integer"),
    "proposer_membership_id": _column(14, "integer"),
    "created_at": _column(15, "timestamp with time zone"),
    "expires_at": _column(16, "timestamp with time zone"),
    "idempotency_key": _column(17, "text", collation="pg_catalog.C"),
    "proposal_sha256": _column(18, "text", collation="pg_catalog.C"),
}

_EVENT_COLUMNS = {
    "id": _column(1, "bigint", identity="a"),
    "contract_version": _column(2, "smallint"),
    "event_kind": _column(3, "text", collation="pg_catalog.C"),
    "proposal_id": _column(4, "bigint"),
    "proposal_sha256": _column(5, "text", collation="pg_catalog.C"),
    "action_kind": _column(6, "text", collation="pg_catalog.C"),
    "company_id": _column(7, "integer"),
    "project_id": _column(8, "integer"),
    "subject_kind": _column(9, "text", collation="pg_catalog.C"),
    "subject_id": _column(10, "bigint"),
    "proposer_user_id": _column(11, "integer"),
    "proposer_membership_id": _column(12, "integer"),
    "actor_user_id": _column(13, "integer"),
    "actor_membership_id": _column(14, "integer"),
    "proposal_created_at": _column(15, "timestamp with time zone"),
    "proposal_expires_at": _column(16, "timestamp with time zone"),
    "occurred_at": _column(17, "timestamp with time zone"),
    "event_sha256": _column(18, "text", collation="pg_catalog.C"),
}

_SUBJECTS = (
    "lotMovement",
    "receiptLot",
    "warehouseHistory",
    "warehouseInvoice",
    "warehouseMovement",
)
_ANOMALIES = (
    "warehouse_invoice_delivery_mismatch",
    "warehouse_invoice_items_invalid",
    "warehouse_invoice_project_mismatch",
    "warehouse_invoice_request_mismatch",
    "warehouse_invoice_supplier_invoice_mismatch",
    "warehouse_lot_movement_missing",
    "warehouse_lot_movement_parent_mismatch",
    "warehouse_lot_movement_source_mismatch",
    "warehouse_movement_invoice_mismatch",
    "warehouse_movement_line_invalid",
    "warehouse_movement_lot_missing",
    "warehouse_movement_package_mismatch",
    "warehouse_receipt_invoice_mismatch",
    "warehouse_receipt_line_invalid",
    "warehouse_receipt_lot_invoice_mismatch",
    "warehouse_receipt_lot_line_invalid",
    "warehouse_receipt_lot_project_mismatch",
    "warehouse_receipt_package_mismatch",
)


def _sql_list(values):
    return ",".join("'" + value.replace("'", "''") + "'" for value in values)


_PROPOSAL_TABLE_SQL = f"""
CREATE TABLE public.{PROPOSAL_TABLE} (
  id BIGINT GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.{_PROPOSAL_SEQUENCE}
  ),
  contract_version SMALLINT NOT NULL,
  action_kind TEXT COLLATE pg_catalog."C" NOT NULL,
  effect_kind TEXT COLLATE pg_catalog."C" NOT NULL,
  company_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  source_job_id BIGINT NOT NULL,
  subject_kind TEXT COLLATE pg_catalog."C" NOT NULL,
  subject_id BIGINT NOT NULL,
  anomaly_code TEXT COLLATE pg_catalog."C" NOT NULL,
  source_content_version SMALLINT NOT NULL,
  source_content_sha256 TEXT COLLATE pg_catalog."C" NOT NULL,
  proposer_user_id INTEGER NOT NULL,
  proposer_membership_id INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  idempotency_key TEXT COLLATE pg_catalog."C" NOT NULL,
  proposal_sha256 TEXT COLLATE pg_catalog."C" NOT NULL,
  CONSTRAINT pk_hap_proposals PRIMARY KEY (id),
  CONSTRAINT uq_hap_idempotency UNIQUE (company_id,idempotency_key),
  CONSTRAINT fk_hap_company FOREIGN KEY (company_id)
    REFERENCES public.companies(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hap_project FOREIGN KEY (project_id)
    REFERENCES public.projects(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hap_source_job FOREIGN KEY (source_job_id)
    REFERENCES public.agent_jobs(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hap_proposer_user FOREIGN KEY (proposer_user_id)
    REFERENCES public.users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hap_proposer_membership FOREIGN KEY (proposer_membership_id)
    REFERENCES public.user_company_roles(id) ON DELETE RESTRICT,
  CONSTRAINT ck_hap_version CHECK (contract_version=1),
  CONSTRAINT ck_hap_action CHECK (
    action_kind='{_ACTION_KIND}' AND effect_kind='{_EFFECT_KIND}'
  ),
  CONSTRAINT ck_hap_ids CHECK (
    id>0 AND company_id>0 AND project_id>0 AND source_job_id>0
    AND subject_id>0
    AND proposer_user_id>0 AND proposer_membership_id>0
  ),
  CONSTRAINT ck_hap_subject CHECK (subject_kind IN ({_sql_list(_SUBJECTS)})),
  CONSTRAINT ck_hap_anomaly CHECK (anomaly_code IN ({_sql_list(_ANOMALIES)})),
  CONSTRAINT ck_hap_hashes CHECK (
    source_content_version=1
    AND source_content_sha256 ~ '^[0-9a-f]{{64}}$'
    AND proposal_sha256 ~ '^[0-9a-f]{{64}}$'
    AND idempotency_key ~ '^human-action:v1:[0-9a-f]{{64}}$'
  ),
  CONSTRAINT ck_hap_expiry CHECK (
    expires_at=created_at+INTERVAL '15 minutes'
  )
)
""".strip()

_EVENT_TABLE_SQL = f"""
CREATE TABLE public.{EVENT_TABLE} (
  id BIGINT GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.{_EVENT_SEQUENCE}
  ),
  contract_version SMALLINT NOT NULL,
  event_kind TEXT COLLATE pg_catalog."C" NOT NULL,
  proposal_id BIGINT NOT NULL,
  proposal_sha256 TEXT COLLATE pg_catalog."C" NOT NULL,
  action_kind TEXT COLLATE pg_catalog."C" NOT NULL,
  company_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  subject_kind TEXT COLLATE pg_catalog."C" NOT NULL,
  subject_id BIGINT NOT NULL,
  proposer_user_id INTEGER NOT NULL,
  proposer_membership_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  actor_membership_id INTEGER NOT NULL,
  proposal_created_at TIMESTAMPTZ NOT NULL,
  proposal_expires_at TIMESTAMPTZ NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  event_sha256 TEXT COLLATE pg_catalog."C" NOT NULL,
  CONSTRAINT pk_hae_events PRIMARY KEY (id),
  CONSTRAINT uq_hae_event_sha256 UNIQUE (event_sha256),
  CONSTRAINT fk_hae_proposal FOREIGN KEY (proposal_id)
    REFERENCES public.human_action_proposals(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hae_company FOREIGN KEY (company_id)
    REFERENCES public.companies(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hae_project FOREIGN KEY (project_id)
    REFERENCES public.projects(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hae_proposer_user FOREIGN KEY (proposer_user_id)
    REFERENCES public.users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hae_proposer_membership FOREIGN KEY (proposer_membership_id)
    REFERENCES public.user_company_roles(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hae_actor_user FOREIGN KEY (actor_user_id)
    REFERENCES public.users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_hae_actor_membership FOREIGN KEY (actor_membership_id)
    REFERENCES public.user_company_roles(id) ON DELETE RESTRICT,
  CONSTRAINT ck_hae_version CHECK (contract_version=1),
  CONSTRAINT ck_hae_kind CHECK (
    event_kind IN ('proposed','approved','rejected','applied','apply_failed')
  ),
  CONSTRAINT ck_hae_action CHECK (
    action_kind='{_ACTION_KIND}'
  ),
  CONSTRAINT ck_hae_ids CHECK (
    id>0 AND proposal_id>0 AND company_id>0 AND project_id>0
    AND subject_id>0 AND proposer_user_id>0 AND proposer_membership_id>0
    AND actor_user_id>0 AND actor_membership_id>0
  ),
  CONSTRAINT ck_hae_hashes CHECK (
    proposal_sha256 ~ '^[0-9a-f]{{64}}$'
    AND event_sha256 ~ '^[0-9a-f]{{64}}$'
  ),
  CONSTRAINT ck_hae_times CHECK (
    proposal_expires_at=proposal_created_at+INTERVAL '15 minutes'
    AND occurred_at>=proposal_created_at
  )
)
""".strip()

_IMMUTABLE_FUNCTION_SQL = """
CREATE FUNCTION public.reject_human_action_ledger_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'human_action_ledger_immutable' USING ERRCODE='55000';
END;
$$
""".strip()

_CREATE_STEPS = (
    {
        "name": "create_human_action_proposals",
        "sql": _PROPOSAL_TABLE_SQL,
        "rollbackSql": "DROP TABLE IF EXISTS public.human_action_proposals CASCADE;",
    },
    {
        "name": "create_human_action_events",
        "sql": _EVENT_TABLE_SQL,
        "rollbackSql": "DROP TABLE IF EXISTS public.human_action_events CASCADE;",
    },
    {
        "name": "create_hap_history_index",
        "sql": "CREATE INDEX idx_hap_company_project_id ON public.human_action_proposals USING btree (company_id,project_id,id)",
        "rollbackSql": "DROP INDEX IF EXISTS public.idx_hap_company_project_id;",
    },
    {
        "name": "create_hae_history_index",
        "sql": "CREATE INDEX idx_hae_company_project_id ON public.human_action_events USING btree (company_id,project_id,id)",
        "rollbackSql": "DROP INDEX IF EXISTS public.idx_hae_company_project_id;",
    },
    {
        "name": "create_hae_proposed_unique_index",
        "sql": "CREATE UNIQUE INDEX uq_hae_proposed ON public.human_action_events USING btree (proposal_id) WHERE event_kind='proposed'",
        "rollbackSql": "DROP INDEX IF EXISTS public.uq_hae_proposed;",
    },
    {
        "name": "create_hae_decision_unique_index",
        "sql": "CREATE UNIQUE INDEX uq_hae_decision ON public.human_action_events USING btree (proposal_id) WHERE event_kind IN ('approved','rejected')",
        "rollbackSql": "DROP INDEX IF EXISTS public.uq_hae_decision;",
    },
    {
        "name": "create_hae_applied_unique_index",
        "sql": "CREATE UNIQUE INDEX uq_hae_applied ON public.human_action_events USING btree (proposal_id) WHERE event_kind='applied'",
        "rollbackSql": "DROP INDEX IF EXISTS public.uq_hae_applied;",
    },
    {
        "name": "create_human_action_immutable_function",
        "sql": _IMMUTABLE_FUNCTION_SQL,
        "rollbackSql": "DROP FUNCTION IF EXISTS public.reject_human_action_ledger_mutation();",
    },
    {
        "name": "create_hap_immutable_trigger",
        "sql": "CREATE TRIGGER hap_immutable BEFORE UPDATE OR DELETE ON public.human_action_proposals FOR EACH ROW EXECUTE FUNCTION public.reject_human_action_ledger_mutation()",
        "rollbackSql": "DROP TRIGGER IF EXISTS hap_immutable ON public.human_action_proposals;",
    },
    {
        "name": "create_hap_no_truncate_trigger",
        "sql": "CREATE TRIGGER hap_no_truncate BEFORE TRUNCATE ON public.human_action_proposals FOR EACH STATEMENT EXECUTE FUNCTION public.reject_human_action_ledger_mutation()",
        "rollbackSql": "DROP TRIGGER IF EXISTS hap_no_truncate ON public.human_action_proposals;",
    },
    {
        "name": "create_hae_immutable_trigger",
        "sql": "CREATE TRIGGER hae_immutable BEFORE UPDATE OR DELETE ON public.human_action_events FOR EACH ROW EXECUTE FUNCTION public.reject_human_action_ledger_mutation()",
        "rollbackSql": "DROP TRIGGER IF EXISTS hae_immutable ON public.human_action_events;",
    },
    {
        "name": "create_hae_no_truncate_trigger",
        "sql": "CREATE TRIGGER hae_no_truncate BEFORE TRUNCATE ON public.human_action_events FOR EACH STATEMENT EXECUTE FUNCTION public.reject_human_action_ledger_mutation()",
        "rollbackSql": "DROP TRIGGER IF EXISTS hae_no_truncate ON public.human_action_events;",
    },
)


def _normalized(value):
    return " ".join(str(value or "").split())


def _body_sha256(value):
    return hashlib.sha256(_normalized(value).encode("utf-8")).hexdigest()


_RELATIONS = {
    PROPOSAL_TABLE: {
        "relkind": "r", "persistence": "p", "rowSecurity": False,
        "forceRowSecurity": False, "hasRules": False, "hasParents": False,
        "hasChildren": False, "hasPolicies": False,
        "ownedByCurrentUser": True,
    },
    EVENT_TABLE: {
        "relkind": "r", "persistence": "p", "rowSecurity": False,
        "forceRowSecurity": False, "hasRules": False, "hasParents": False,
        "hasChildren": False, "hasPolicies": False,
        "ownedByCurrentUser": True,
    },
    _PROPOSAL_SEQUENCE: {
        "relkind": "S", "persistence": "p", "ownedByCurrentUser": True,
    },
    _EVENT_SEQUENCE: {
        "relkind": "S", "persistence": "p", "ownedByCurrentUser": True,
    },
    "pk_hap_proposals": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "uq_hap_idempotency": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "pk_hae_events": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "uq_hae_event_sha256": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "idx_hap_company_project_id": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "idx_hae_company_project_id": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "uq_hae_proposed": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "uq_hae_decision": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
    "uq_hae_applied": {"relkind": "i", "persistence": "p", "ownedByCurrentUser": True},
}

_TYPE_HOLDERS = {
    PROPOSAL_TABLE: {"type": "c", "relationName": PROPOSAL_TABLE},
    EVENT_TABLE: {"type": "c", "relationName": EVENT_TABLE},
}

_SEQUENCES = {
    _PROPOSAL_SEQUENCE: {
        "dataType": "bigint", "start": 1, "increment": 1, "minimum": 1,
        "maximum": 9223372036854775807, "cache": 1, "cycle": False,
        "ownedTable": PROPOSAL_TABLE, "ownedColumn": "id",
        "dependencyType": "i",
    },
    _EVENT_SEQUENCE: {
        "dataType": "bigint", "start": 1, "increment": 1, "minimum": 1,
        "maximum": 9223372036854775807, "cache": 1, "cycle": False,
        "ownedTable": EVENT_TABLE, "ownedColumn": "id",
        "dependencyType": "i",
    },
}

def _definition_contract(kind, definition):
    return {
        "type": kind,
        "validated": True,
        "definitionSha256": _body_sha256(definition),
    }


def _text_array(values):
    return ", ".join(f"'{value}'::text" for value in values)


_CONSTRAINTS = {
    f"{PROPOSAL_TABLE}.ck_hap_action": _definition_contract(
        "c", "CHECK (action_kind = 'warehouse_anomaly_review_acknowledged'::text AND effect_kind = 'audit_only'::text)",
    ),
    f"{PROPOSAL_TABLE}.ck_hap_anomaly": _definition_contract(
        "c", "CHECK (anomaly_code = ANY (ARRAY[" + _text_array(_ANOMALIES) + "]))",
    ),
    f"{PROPOSAL_TABLE}.ck_hap_expiry": _definition_contract(
        "c", "CHECK (expires_at = (created_at + '00:15:00'::interval))",
    ),
    f"{PROPOSAL_TABLE}.ck_hap_hashes": _definition_contract(
        "c", "CHECK (source_content_version = 1 AND source_content_sha256 ~ '^[0-9a-f]{64}$'::text AND proposal_sha256 ~ '^[0-9a-f]{64}$'::text AND idempotency_key ~ '^human-action:v1:[0-9a-f]{64}$'::text)",
    ),
    f"{PROPOSAL_TABLE}.ck_hap_ids": _definition_contract(
        "c", "CHECK (id > 0 AND company_id > 0 AND project_id > 0 AND source_job_id > 0 AND subject_id > 0 AND proposer_user_id > 0 AND proposer_membership_id > 0)",
    ),
    f"{PROPOSAL_TABLE}.ck_hap_subject": _definition_contract(
        "c", "CHECK (subject_kind = ANY (ARRAY[" + _text_array(_SUBJECTS) + "]))",
    ),
    f"{PROPOSAL_TABLE}.ck_hap_version": _definition_contract(
        "c", "CHECK (contract_version = 1)",
    ),
    f"{PROPOSAL_TABLE}.fk_hap_company": _definition_contract(
        "f", "FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT",
    ),
    f"{PROPOSAL_TABLE}.fk_hap_project": _definition_contract(
        "f", "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT",
    ),
    f"{PROPOSAL_TABLE}.fk_hap_source_job": _definition_contract(
        "f", "FOREIGN KEY (source_job_id) REFERENCES agent_jobs(id) ON DELETE RESTRICT",
    ),
    f"{PROPOSAL_TABLE}.fk_hap_proposer_membership": _definition_contract(
        "f", "FOREIGN KEY (proposer_membership_id) REFERENCES user_company_roles(id) ON DELETE RESTRICT",
    ),
    f"{PROPOSAL_TABLE}.fk_hap_proposer_user": _definition_contract(
        "f", "FOREIGN KEY (proposer_user_id) REFERENCES users(id) ON DELETE RESTRICT",
    ),
    f"{PROPOSAL_TABLE}.pk_hap_proposals": _definition_contract(
        "p", "PRIMARY KEY (id)",
    ),
    f"{PROPOSAL_TABLE}.uq_hap_idempotency": _definition_contract(
        "u", "UNIQUE (company_id, idempotency_key)",
    ),
    f"{EVENT_TABLE}.ck_hae_action": _definition_contract(
        "c", "CHECK (action_kind = 'warehouse_anomaly_review_acknowledged'::text)",
    ),
    f"{EVENT_TABLE}.ck_hae_hashes": _definition_contract(
        "c", "CHECK (proposal_sha256 ~ '^[0-9a-f]{64}$'::text AND event_sha256 ~ '^[0-9a-f]{64}$'::text)",
    ),
    f"{EVENT_TABLE}.ck_hae_ids": _definition_contract(
        "c", "CHECK (id > 0 AND proposal_id > 0 AND company_id > 0 AND project_id > 0 AND subject_id > 0 AND proposer_user_id > 0 AND proposer_membership_id > 0 AND actor_user_id > 0 AND actor_membership_id > 0)",
    ),
    f"{EVENT_TABLE}.ck_hae_kind": _definition_contract(
        "c", "CHECK (event_kind = ANY (ARRAY[" + _text_array(("proposed", "approved", "rejected", "applied", "apply_failed")) + "]))",
    ),
    f"{EVENT_TABLE}.ck_hae_times": _definition_contract(
        "c", "CHECK (proposal_expires_at = (proposal_created_at + '00:15:00'::interval) AND occurred_at >= proposal_created_at)",
    ),
    f"{EVENT_TABLE}.ck_hae_version": _definition_contract(
        "c", "CHECK (contract_version = 1)",
    ),
    f"{EVENT_TABLE}.fk_hae_actor_membership": _definition_contract(
        "f", "FOREIGN KEY (actor_membership_id) REFERENCES user_company_roles(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.fk_hae_actor_user": _definition_contract(
        "f", "FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.fk_hae_company": _definition_contract(
        "f", "FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.fk_hae_project": _definition_contract(
        "f", "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.fk_hae_proposal": _definition_contract(
        "f", "FOREIGN KEY (proposal_id) REFERENCES human_action_proposals(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.fk_hae_proposer_membership": _definition_contract(
        "f", "FOREIGN KEY (proposer_membership_id) REFERENCES user_company_roles(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.fk_hae_proposer_user": _definition_contract(
        "f", "FOREIGN KEY (proposer_user_id) REFERENCES users(id) ON DELETE RESTRICT",
    ),
    f"{EVENT_TABLE}.pk_hae_events": _definition_contract(
        "p", "PRIMARY KEY (id)",
    ),
    f"{EVENT_TABLE}.uq_hae_event_sha256": _definition_contract(
        "u", "UNIQUE (event_sha256)",
    ),
}


def _index_contract(table, definition):
    return {
        "table": table,
        "valid": True,
        "ready": True,
        "live": True,
        "checkXmin": False,
        "definitionSha256": _body_sha256(definition),
    }


_INDEXES = {
    "idx_hae_company_project_id": _index_contract(
        EVENT_TABLE,
        "CREATE INDEX idx_hae_company_project_id ON public.human_action_events USING btree (company_id, project_id, id)",
    ),
    "idx_hap_company_project_id": _index_contract(
        PROPOSAL_TABLE,
        "CREATE INDEX idx_hap_company_project_id ON public.human_action_proposals USING btree (company_id, project_id, id)",
    ),
    "pk_hae_events": _index_contract(
        EVENT_TABLE,
        "CREATE UNIQUE INDEX pk_hae_events ON public.human_action_events USING btree (id)",
    ),
    "pk_hap_proposals": _index_contract(
        PROPOSAL_TABLE,
        "CREATE UNIQUE INDEX pk_hap_proposals ON public.human_action_proposals USING btree (id)",
    ),
    "uq_hae_applied": _index_contract(
        EVENT_TABLE,
        "CREATE UNIQUE INDEX uq_hae_applied ON public.human_action_events USING btree (proposal_id) WHERE (event_kind = 'applied'::text)",
    ),
    "uq_hae_decision": _index_contract(
        EVENT_TABLE,
        "CREATE UNIQUE INDEX uq_hae_decision ON public.human_action_events USING btree (proposal_id) WHERE (event_kind = ANY (ARRAY['approved'::text, 'rejected'::text]))",
    ),
    "uq_hae_event_sha256": _index_contract(
        EVENT_TABLE,
        "CREATE UNIQUE INDEX uq_hae_event_sha256 ON public.human_action_events USING btree (event_sha256)",
    ),
    "uq_hae_proposed": _index_contract(
        EVENT_TABLE,
        "CREATE UNIQUE INDEX uq_hae_proposed ON public.human_action_events USING btree (proposal_id) WHERE (event_kind = 'proposed'::text)",
    ),
    "uq_hap_idempotency": _index_contract(
        PROPOSAL_TABLE,
        "CREATE UNIQUE INDEX uq_hap_idempotency ON public.human_action_proposals USING btree (company_id, idempotency_key)",
    ),
}

_FUNCTIONS = {
    "reject_human_action_ledger_mutation": {
        "language": "plpgsql",
        "returns": "trigger",
        "securityDefiner": False,
        "leakproof": False,
        "volatility": "v",
        "parallel": "u",
        "strict": False,
        "kind": "f",
        "config": [],
        "bodySha256": _body_sha256(
            "BEGIN RAISE EXCEPTION 'human_action_ledger_immutable' "
            "USING ERRCODE='55000'; END;"
        ),
    },
}

_TRIGGERS = {
    "human_action_proposals.hap_immutable": {
        "enabled": "O", "type": 27,
        "function": "public.reject_human_action_ledger_mutation",
        "condition": None, "argumentsHex": "", "columns": "",
        "constraint": False, "oldTable": None, "newTable": None,
    },
    "human_action_proposals.hap_no_truncate": {
        "enabled": "O", "type": 34,
        "function": "public.reject_human_action_ledger_mutation",
        "condition": None, "argumentsHex": "", "columns": "",
        "constraint": False, "oldTable": None, "newTable": None,
    },
    "human_action_events.hae_immutable": {
        "enabled": "O", "type": 27,
        "function": "public.reject_human_action_ledger_mutation",
        "condition": None, "argumentsHex": "", "columns": "",
        "constraint": False, "oldTable": None, "newTable": None,
    },
    "human_action_events.hae_no_truncate": {
        "enabled": "O", "type": 34,
        "function": "public.reject_human_action_ledger_mutation",
        "condition": None, "argumentsHex": "", "columns": "",
        "constraint": False, "oldTable": None, "newTable": None,
    },
}


def human_action_schema_contract():
    return copy.deepcopy({
        "parentColumnsMissing": [],
        "parentRelations": _PARENT_RELATIONS,
        "catalogComplete": True,
        "relations": _RELATIONS,
        "typeHolders": _TYPE_HOLDERS,
        "sequences": _SEQUENCES,
        "columns": {
            PROPOSAL_TABLE: _PROPOSAL_COLUMNS,
            EVENT_TABLE: _EVENT_COLUMNS,
        },
        "constraints": _CONSTRAINTS,
        "indexes": _INDEXES,
        "functions": _FUNCTIONS,
        "triggers": _TRIGGERS,
    })


def _plan_sha256(changes):
    payload = {
        "domain": "stroyka.human_approved_actions.schema.plan",
        "contractVersion": CONTRACT_VERSION,
        "parentRequiredColumns": {
            table: sorted(columns)
            for table, columns in PARENT_REQUIRED_COLUMNS.items()
        },
        "contract": human_action_schema_contract(),
        "changes": [
            {
                "name": item["name"],
                "sql": _normalized(item["sql"]),
                "rollbackSql": _normalized(item["rollbackSql"]),
            }
            for item in changes
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_human_action_schema_plan(catalog):
    expected_keys = set(human_action_schema_contract())
    blockers = []
    if type(catalog) is not dict or set(catalog) != expected_keys:
        blockers.append("human_action_schema_catalog_invalid")
        catalog = {key: None for key in expected_keys}
    if (
        catalog.get("parentColumnsMissing") != []
        or catalog.get("parentRelations") != _PARENT_RELATIONS
    ):
        blockers.append("human_action_schema_parent_not_ready")
    if catalog.get("catalogComplete") is not True:
        blockers.append("human_action_schema_catalog_incomplete")

    relations = catalog.get("relations")
    absent = relations == {}
    collision_fields = (
        "typeHolders", "sequences", "columns", "constraints", "indexes",
        "functions", "triggers",
    )
    if absent:
        if any(catalog.get(field) not in ({}, []) for field in collision_fields):
            blockers.append("human_action_schema_object_collision")
    elif catalog != human_action_schema_contract():
        blockers.append("human_action_schema_drift")

    changes = []
    if absent and not blockers:
        changes = [dict(item) for item in _CREATE_STEPS]
    complete = not absent and not blockers
    return {
        "contractVersion": CONTRACT_VERSION,
        "ok": not blockers,
        "complete": complete,
        "schemaReady": complete,
        "readyForApply": absent and not blockers,
        "requiresMaintenanceWindow": True,
        "blockers": sorted(set(blockers)),
        "changeCount": len(changes),
        "changes": changes,
        "rollbackSql": [item["rollbackSql"] for item in reversed(changes)],
        "planSha256": _plan_sha256(changes),
    }


def _rows(cur, limit):
    rows = [dict(row or {}) for row in (cur.fetchall() or [])]
    return rows if len(rows) <= limit else None


def _collect_catalog(cur):
    complete = True
    required_pairs = sorted(
        (table, column)
        for table, columns in PARENT_REQUIRED_COLUMNS.items()
        for column in columns
    )
    parent_predicate = " OR ".join(
        "(table_name=%s AND column_name=%s)" for _pair in required_pairs
    )
    parent_params = ["public"]
    for table, column in required_pairs:
        parent_params.extend((table, column))
    parent_params.append(len(required_pairs) + 1)
    cur.execute(
        "SELECT table_name,column_name FROM information_schema.columns "
        "WHERE table_schema=%s AND (" + parent_predicate + ") LIMIT %s",
        tuple(parent_params),
    )
    parent_rows = _rows(cur, len(required_pairs))
    if parent_rows is None:
        parent_rows = []
        complete = False
    present_pairs = {
        (row.get("table_name"), row.get("column_name")) for row in parent_rows
    }
    parent_missing = [
        f"{table}.{column}" for table, column in required_pairs
        if (table, column) not in present_pairs
    ]

    cur.execute(
        """SELECT relation.relname AS object_name,
                  relation.relkind::text AS relkind,
                  relation.relpersistence::text AS persistence
             FROM pg_catalog.pg_class relation
             JOIN pg_catalog.pg_namespace namespace
               ON namespace.oid=relation.relnamespace
            WHERE namespace.nspname=%s
              AND relation.relname=ANY(%s) LIMIT %s""",
        (
            "public", sorted(_PARENT_RELATIONS),
            len(_PARENT_RELATIONS) + 1,
        ),
    )
    parent_relation_rows = _rows(cur, len(_PARENT_RELATIONS))
    if parent_relation_rows is None:
        parent_relation_rows = []
        complete = False
    parent_relations = {
        row.get("object_name"): {
            "relkind": row.get("relkind"),
            "persistence": row.get("persistence"),
        }
        for row in parent_relation_rows if row.get("object_name")
    }

    cur.execute(
        """SELECT relation.relname AS object_name,
                  relation.relkind::text AS relkind,
                  relation.relpersistence::text AS persistence,
                  relation.relrowsecurity AS row_security,
                  relation.relforcerowsecurity AS force_row_security,
                  relation.relhasrules AS has_rules,
                  pg_catalog.pg_get_userbyid(relation.relowner)=CURRENT_USER
                    AS owned_by_current_user,
                  EXISTS (SELECT 1 FROM pg_catalog.pg_inherits parent_edge
                           WHERE parent_edge.inhrelid=relation.oid LIMIT 1)
                    AS has_parents,
                  EXISTS (SELECT 1 FROM pg_catalog.pg_inherits child_edge
                           WHERE child_edge.inhparent=relation.oid LIMIT 1)
                    AS has_children,
                  EXISTS (SELECT 1 FROM pg_catalog.pg_policy policy
                           WHERE policy.polrelid=relation.oid LIMIT 1)
                    AS has_policies
             FROM pg_catalog.pg_class relation
             JOIN pg_catalog.pg_namespace namespace
               ON namespace.oid=relation.relnamespace
            WHERE namespace.nspname=%s
              AND relation.relname=ANY(%s) LIMIT %s""",
        ("public", sorted(_RELATIONS), len(_RELATIONS) + 1),
    )
    relation_rows = _rows(cur, len(_RELATIONS))
    if relation_rows is None:
        relation_rows = []
        complete = False
    relations = {}
    for row in relation_rows:
        relation = {
            "relkind": row.get("relkind"),
            "persistence": row.get("persistence"),
            "ownedByCurrentUser": row.get("owned_by_current_user") is True,
        }
        if row.get("object_name") in {PROPOSAL_TABLE, EVENT_TABLE}:
            relation.update({
                "rowSecurity": row.get("row_security") is True,
                "forceRowSecurity": row.get("force_row_security") is True,
                "hasRules": row.get("has_rules") is True,
                "hasParents": row.get("has_parents") is True,
                "hasChildren": row.get("has_children") is True,
                "hasPolicies": row.get("has_policies") is True,
            })
        if row.get("object_name"):
            relations[row["object_name"]] = relation

    cur.execute(
        """SELECT type_state.typname AS type_name,
                  type_state.typtype::text AS type_kind,
                  relation.relname AS relation_name
             FROM pg_catalog.pg_type type_state
             JOIN pg_catalog.pg_namespace namespace
               ON namespace.oid=type_state.typnamespace
             LEFT JOIN pg_catalog.pg_class relation
               ON relation.oid=type_state.typrelid
            WHERE namespace.nspname=%s
              AND type_state.typname=ANY(%s) LIMIT %s""",
        ("public", [PROPOSAL_TABLE, EVENT_TABLE], len(_TYPE_HOLDERS) + 1),
    )
    type_rows = _rows(cur, len(_TYPE_HOLDERS))
    if type_rows is None:
        type_rows = []
        complete = False
    type_holders = {
        row.get("type_name"): {
            "type": row.get("type_kind"),
            "relationName": row.get("relation_name"),
        }
        for row in type_rows if row.get("type_name")
    }

    cur.execute(
        """SELECT sequence_relation.relname AS sequence_name,
                  pg_catalog.format_type(sequence_state.seqtypid,NULL)
                    AS data_type,
                  sequence_state.seqstart::bigint AS start_value,
                  sequence_state.seqincrement::bigint AS increment_value,
                  sequence_state.seqmin::bigint AS minimum_value,
                  sequence_state.seqmax::bigint AS maximum_value,
                  sequence_state.seqcache::bigint AS cache_value,
                  sequence_state.seqcycle AS cycle,
                  owned_relation.relname AS owned_table,
                  owned_attribute.attname AS owned_column,
                  dependency.deptype::text AS dependency_type
             FROM pg_catalog.pg_class sequence_relation
             JOIN pg_catalog.pg_namespace namespace
               ON namespace.oid=sequence_relation.relnamespace
             JOIN pg_catalog.pg_sequence sequence_state
               ON sequence_state.seqrelid=sequence_relation.oid
             LEFT JOIN pg_catalog.pg_depend dependency
               ON dependency.classid='pg_catalog.pg_class'::regclass
              AND dependency.objid=sequence_relation.oid
              AND dependency.objsubid=0
              AND dependency.refclassid='pg_catalog.pg_class'::regclass
              AND dependency.deptype='i'
             LEFT JOIN pg_catalog.pg_class owned_relation
               ON owned_relation.oid=dependency.refobjid
             LEFT JOIN pg_catalog.pg_attribute owned_attribute
               ON owned_attribute.attrelid=dependency.refobjid
              AND owned_attribute.attnum=dependency.refobjsubid
            WHERE namespace.nspname=%s
              AND sequence_relation.relname=ANY(%s) LIMIT %s""",
        ("public", sorted(_SEQUENCES), len(_SEQUENCES) + 1),
    )
    sequence_rows = _rows(cur, len(_SEQUENCES))
    if sequence_rows is None:
        sequence_rows = []
        complete = False
    sequences = {
        row.get("sequence_name"): {
            "dataType": row.get("data_type"),
            "start": row.get("start_value"),
            "increment": row.get("increment_value"),
            "minimum": row.get("minimum_value"),
            "maximum": row.get("maximum_value"),
            "cache": row.get("cache_value"),
            "cycle": row.get("cycle") is True,
            "ownedTable": row.get("owned_table"),
            "ownedColumn": row.get("owned_column"),
            "dependencyType": row.get("dependency_type"),
        }
        for row in sequence_rows if row.get("sequence_name")
    }

    cur.execute(
        """SELECT relation.relname AS table_name,
                  attribute.attname AS column_name,
                  attribute.attnum::integer AS position,
                  pg_catalog.format_type(attribute.atttypid,attribute.atttypmod)
                    AS data_type,
                  attribute.attnotnull AS not_null,
                  attribute.attidentity::text AS identity_kind,
                  attribute.attgenerated::text AS generated_kind,
                  pg_catalog.pg_get_expr(default_value.adbin,default_value.adrelid,true)
                    AS default_expression,
                  CASE WHEN attribute.attcollation=0 THEN NULL
                       ELSE collation_namespace.nspname || '.' || collation_state.collname
                  END AS collation_name
             FROM pg_catalog.pg_attribute attribute
             JOIN pg_catalog.pg_class relation ON relation.oid=attribute.attrelid
             JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace
             LEFT JOIN pg_catalog.pg_attrdef default_value
               ON default_value.adrelid=attribute.attrelid
              AND default_value.adnum=attribute.attnum
             LEFT JOIN pg_catalog.pg_collation collation_state
               ON collation_state.oid=attribute.attcollation
             LEFT JOIN pg_catalog.pg_namespace collation_namespace
               ON collation_namespace.oid=collation_state.collnamespace
            WHERE namespace.nspname=%s AND relation.relname=ANY(%s)
              AND attribute.attnum>0 AND NOT attribute.attisdropped
            ORDER BY relation.relname,attribute.attnum LIMIT %s""",
        (
            "public", [PROPOSAL_TABLE, EVENT_TABLE],
            len(_PROPOSAL_COLUMNS) + len(_EVENT_COLUMNS) + 1,
        ),
    )
    column_rows = _rows(cur, len(_PROPOSAL_COLUMNS) + len(_EVENT_COLUMNS))
    if column_rows is None:
        column_rows = []
        complete = False
    columns = {}
    for row in column_rows:
        columns.setdefault(row.get("table_name"), {})[row.get("column_name")] = {
            "position": row.get("position"),
            "type": row.get("data_type"),
            "notNull": row.get("not_null") is True,
            "default": (
                None if row.get("default_expression") is None
                else _normalized(row.get("default_expression"))
            ),
            "identity": row.get("identity_kind") or "",
            "generated": row.get("generated_kind") or "",
            "collation": row.get("collation_name"),
        }

    constraint_names = sorted(
        name.split(".", 1)[1] for name in _CONSTRAINTS
    )
    cur.execute(
        """SELECT relation.relname AS table_name,constraint_row.conname,
                  constraint_row.contype::text AS type,
                  constraint_row.convalidated AS validated,
                  pg_catalog.pg_get_constraintdef(constraint_row.oid,TRUE)
                    AS definition
             FROM pg_catalog.pg_constraint constraint_row
             JOIN pg_catalog.pg_class relation ON relation.oid=constraint_row.conrelid
             JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace
            WHERE namespace.nspname=%s AND relation.relname=ANY(%s)
              LIMIT %s""",
        (
            "public", [PROPOSAL_TABLE, EVENT_TABLE],
            len(constraint_names) + 1,
        ),
    )
    constraint_rows = _rows(cur, len(constraint_names))
    if constraint_rows is None:
        constraint_rows = []
        complete = False
    constraints = {
        f"{row.get('table_name')}.{row.get('conname')}": {
            "type": row.get("type"),
            "validated": row.get("validated") is True,
            "definitionSha256": _body_sha256(row.get("definition")),
        }
        for row in constraint_rows
        if row.get("table_name") and row.get("conname")
    }

    cur.execute(
        """SELECT table_relation.relname AS tablename,
                  index_relation.relname AS indexname,
                  pg_catalog.pg_get_indexdef(index_state.indexrelid) AS indexdef,
                  index_state.indisvalid AS valid,index_state.indisready AS ready,
                  index_state.indislive AS live,index_state.indcheckxmin AS check_xmin
             FROM pg_catalog.pg_index index_state
             JOIN pg_catalog.pg_class index_relation
               ON index_relation.oid=index_state.indexrelid
             JOIN pg_catalog.pg_class table_relation
               ON table_relation.oid=index_state.indrelid
             JOIN pg_catalog.pg_namespace namespace
               ON namespace.oid=table_relation.relnamespace
            WHERE namespace.nspname=%s AND table_relation.relname=ANY(%s)
            LIMIT %s""",
        (
            "public", [PROPOSAL_TABLE, EVENT_TABLE],
            len(_INDEXES) + 1,
        ),
    )
    index_rows = _rows(cur, len(_INDEXES))
    if index_rows is None:
        index_rows = []
        complete = False
    indexes = {
        row.get("indexname"): {
            "table": row.get("tablename"),
            "valid": row.get("valid") is True,
            "ready": row.get("ready") is True,
            "live": row.get("live") is True,
            "checkXmin": row.get("check_xmin") is True,
            "definitionSha256": _body_sha256(row.get("indexdef")),
        }
        for row in index_rows if row.get("indexname")
    }

    cur.execute(
        """SELECT procedure.proname AS function_name,language.lanname AS language,
                  pg_catalog.pg_get_function_result(procedure.oid) AS returns,
                  procedure.prosecdef AS security_definer,
                  procedure.proleakproof AS leakproof,
                  procedure.provolatile::text AS volatility,
                  procedure.proparallel::text AS parallel,
                  procedure.proisstrict AS strict,
                  procedure.prokind::text AS kind,
                  COALESCE(procedure.proconfig,ARRAY[]::text[]) AS config,
                  procedure.prosrc AS body
             FROM pg_catalog.pg_proc procedure
             JOIN pg_catalog.pg_namespace namespace ON namespace.oid=procedure.pronamespace
             JOIN pg_catalog.pg_language language ON language.oid=procedure.prolang
            WHERE namespace.nspname=%s AND procedure.proname=ANY(%s)
              AND procedure.pronargs=0 LIMIT %s""",
        ("public", sorted(_FUNCTIONS), len(_FUNCTIONS) + 1),
    )
    function_rows = _rows(cur, len(_FUNCTIONS))
    if function_rows is None:
        function_rows = []
        complete = False
    functions = {
        row.get("function_name"): {
            "language": row.get("language"),
            "returns": row.get("returns"),
            "securityDefiner": row.get("security_definer") is True,
            "leakproof": row.get("leakproof") is True,
            "volatility": row.get("volatility"),
            "parallel": row.get("parallel"),
            "strict": row.get("strict") is True,
            "kind": row.get("kind"),
            "config": [str(item) for item in (row.get("config") or [])],
            "bodySha256": _body_sha256(row.get("body")),
        }
        for row in function_rows if row.get("function_name")
    }

    cur.execute(
        """SELECT relation.relname AS table_name,trigger.tgname AS trigger_name,
                  trigger.tgenabled::text AS enabled,trigger.tgtype::integer AS type,
                  function_namespace.nspname || '.' || procedure.proname AS function_name,
                  pg_catalog.pg_get_expr(trigger.tgqual,trigger.tgrelid,TRUE)
                    AS condition,
                  pg_catalog.encode(trigger.tgargs,'hex') AS arguments_hex,
                  trigger.tgattr::text AS columns,
                  trigger.tgconstraint<>0 AS is_constraint,
                  trigger.tgoldtable AS old_table,trigger.tgnewtable AS new_table
             FROM pg_catalog.pg_trigger trigger
             JOIN pg_catalog.pg_class relation ON relation.oid=trigger.tgrelid
             JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relation.relnamespace
             JOIN pg_catalog.pg_proc procedure ON procedure.oid=trigger.tgfoid
             JOIN pg_catalog.pg_namespace function_namespace
               ON function_namespace.oid=procedure.pronamespace
            WHERE namespace.nspname=%s AND relation.relname=ANY(%s)
              AND NOT trigger.tgisinternal LIMIT %s""",
        ("public", [PROPOSAL_TABLE, EVENT_TABLE], len(_TRIGGERS) + 1),
    )
    trigger_rows = _rows(cur, len(_TRIGGERS))
    if trigger_rows is None:
        trigger_rows = []
        complete = False
    triggers = {
        f"{row.get('table_name')}.{row.get('trigger_name')}": {
            "enabled": row.get("enabled"),
            "type": row.get("type"),
            "function": row.get("function_name"),
            "condition": (
                None if row.get("condition") is None
                else _normalized(row.get("condition"))
            ),
            "argumentsHex": row.get("arguments_hex") or "",
            "columns": row.get("columns") or "",
            "constraint": row.get("is_constraint") is True,
            "oldTable": row.get("old_table"),
            "newTable": row.get("new_table"),
        }
        for row in trigger_rows
        if row.get("table_name") and row.get("trigger_name")
    }
    return {
        "parentColumnsMissing": parent_missing,
        "parentRelations": parent_relations,
        "catalogComplete": complete,
        "relations": relations,
        "typeHolders": type_holders,
        "sequences": sequences,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "functions": functions,
        "triggers": triggers,
    }


class HumanActionSchemaMigrationError(RuntimeError):
    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def _validate_invocation(*, apply, confirm, expected_change_count, expected_plan_sha256):
    guards = (confirm, expected_change_count, expected_plan_sha256)
    if type(apply) is not bool:
        raise HumanActionSchemaMigrationError(
            "human_action_schema_apply_guard_invalid"
        )
    if not apply:
        if any(value is not None for value in guards):
            raise HumanActionSchemaMigrationError(
                "human_action_schema_apply_guard_invalid"
            )
        return
    if (
        type(confirm) is not str
        or confirm != APPLY_CONFIRMATION
        or type(expected_change_count) is not int
        or expected_change_count < 0
        or type(expected_plan_sha256) is not str
        or _PLAN_SHA256_RE.fullmatch(expected_plan_sha256) is None
    ):
        raise HumanActionSchemaMigrationError(
            "human_action_schema_apply_guard_invalid"
        )


def _report(
    plan, *, dry_run, writes=0, committed=False, rolled_back=None,
):
    result = copy.deepcopy(plan)
    result.update({
        "mode": "dry-run" if dry_run else "apply",
        "dryRun": dry_run,
        "writesAttempted": writes,
        "committed": committed,
        "rolledBack": dry_run if rolled_back is None else rolled_back,
    })
    return result


def run_human_action_schema_migration(
    connection,
    *,
    apply=False,
    confirm=None,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    """Inspect or atomically install the exact inert A12 ledger schema."""

    _validate_invocation(
        apply=apply,
        confirm=confirm,
        expected_change_count=expected_change_count,
        expected_plan_sha256=expected_plan_sha256,
    )
    cursor = None
    primary_error = None
    rollback_error = False
    cleanup_error = False
    committed = False
    result = None
    writes = 0
    commit_uncertain = False
    try:
        connection.set_session(
            readonly=not apply,
            autocommit=False,
            isolation_level="SERIALIZABLE" if apply else "REPEATABLE READ",
        )
        cursor = connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        if apply:
            cursor.execute("SET LOCAL search_path=pg_catalog,public")
            cursor.execute("SET LOCAL lock_timeout='5s'")
            cursor.execute("SET LOCAL statement_timeout='60s'")
            cursor.execute(
                "SELECT pg_catalog.pg_advisory_xact_lock(%s) LIMIT %s",
                (ADVISORY_LOCK_ID, 1),
            )
        before = build_human_action_schema_plan(_collect_catalog(cursor))
        if not apply:
            result = _report(before, dry_run=True)
        elif (
            before["changeCount"] != expected_change_count
            or before["planSha256"] != expected_plan_sha256
        ):
            raise HumanActionSchemaMigrationError(
                "human_action_schema_apply_guard_mismatch"
            )
        elif before["complete"]:
            result = _report(before, dry_run=False, rolled_back=True)
        elif not before["readyForApply"]:
            raise HumanActionSchemaMigrationError(
                "human_action_schema_not_ready"
            )
        else:
            for change in before["changes"]:
                cursor.execute(change["sql"])
                writes += 1
            after = build_human_action_schema_plan(_collect_catalog(cursor))
            if not after["complete"] or after["blockers"]:
                raise HumanActionSchemaMigrationError(
                    "human_action_schema_postcheck_failed"
                )
            try:
                connection.commit()
            except BaseException:
                commit_uncertain = True
                raise HumanActionSchemaMigrationError(
                    "human_action_schema_commit_outcome_unknown"
                )
            committed = True
            result = _report(
                after, dry_run=False, writes=writes, committed=True
            )
            result.update({
                "changeCount": before["changeCount"],
                "changes": before["changes"],
                "rollbackSql": before["rollbackSql"],
                "planSha256": before["planSha256"],
            })
    except BaseException as exc:
        primary_error = exc
    finally:
        if not committed:
            try:
                connection.rollback()
            except BaseException:
                rollback_error = True
        if cursor is not None:
            try:
                cursor.close()
            except BaseException:
                cleanup_error = True

    if commit_uncertain:
        raise HumanActionSchemaMigrationError(
            "human_action_schema_commit_outcome_unknown"
        ) from None
    if isinstance(primary_error, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        raise primary_error
    if rollback_error:
        raise HumanActionSchemaMigrationError(
            "human_action_schema_rollback_failed"
        ) from None
    if cleanup_error:
        raise HumanActionSchemaMigrationError(
            "human_action_schema_cleanup_failed"
        ) from None
    if isinstance(primary_error, HumanActionSchemaMigrationError):
        raise primary_error from None
    if primary_error is not None:
        raise HumanActionSchemaMigrationError(
            "human_action_schema_migration_failed"
        ) from None
    return result


__all__ = []
