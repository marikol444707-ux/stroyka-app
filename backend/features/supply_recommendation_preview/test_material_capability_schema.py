import copy
import inspect
import json
import subprocess
import sys
import unittest
from unittest import mock

from backend.features.supply_recommendation_preview import (
    material_capability_schema as schema,
)
from backend.features.supply_recommendation_preview import (
    material_capability_schema_contract as schema_contract,
)
from backend.features.supply_recommendation_preview import (
    material_capability_schema_probe as schema_probe,
)


def absent_catalog(**overrides):
    value = {
        "parentColumnsMissing": [],
        "parentRelations": {
            name: {"relkind": "r", "persistence": "p"}
            for name in schema.PARENT_REQUIRED_COLUMNS
        },
        "catalogComplete": True,
        "table": None,
        "typeHolder": None,
        "identitySequence": None,
        "nameHolders": {},
        "columns": {},
        "constraints": {},
        "indexes": {},
        "functions": {},
        "triggers": {},
    }
    value.update(overrides)
    return value


def exact_catalog():
    contract = schema.material_capability_schema_contract()
    table_oid = 9001
    sequence = copy.deepcopy(contract["identitySequence"])
    sequence.update({"oid": 9002, "tableOid": table_oid})
    indexes = {}
    for offset, (name, value) in enumerate(
        contract["indexes"].items(), 10
    ):
        indexes[name] = copy.deepcopy(value)
        indexes[name].update({"oid": 9000 + offset, "tableOid": table_oid})
    holders = {
        schema.TABLE_NAME: {"oid": table_oid, "relkind": "r"},
        schema.IDENTITY_SEQUENCE_NAME: {
            "oid": sequence["oid"], "relkind": "S",
        },
    }
    holders.update({
        name: {"oid": value["oid"], "relkind": "i"}
        for name, value in indexes.items()
    })
    table = copy.deepcopy(contract["table"])
    table["oid"] = table_oid
    return {
        "parentColumnsMissing": [],
        "parentRelations": {
            name: {"relkind": "r", "persistence": "p"}
            for name in schema.PARENT_REQUIRED_COLUMNS
        },
        "catalogComplete": True,
        "table": table,
        "typeHolder": {
            "oid": 8999, "type": "c", "relationOid": table_oid,
        },
        "identitySequence": sequence,
        "nameHolders": holders,
        "columns": copy.deepcopy(contract["columns"]),
        "constraints": copy.deepcopy(contract["constraints"]),
        "indexes": indexes,
        "functions": copy.deepcopy(contract["functions"]),
        "triggers": copy.deepcopy(contract["triggers"]),
    }


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, query, params=None):
        self.calls.append((" ".join(str(query).split()), params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor=None):
        self.fake_cursor = cursor or FakeCursor()
        self.session = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class RollbackFails(FakeConnection):
    def rollback(self):
        self.rollbacks += 1
        raise RuntimeError("private rollback detail")


class CloseFailsCursor(FakeCursor):
    def close(self):
        self.closed = True
        raise RuntimeError("private cleanup detail")


class MaterialCapabilitySchemaTests(unittest.TestCase):
    def test_fresh_schema_has_one_deterministic_guarded_plan(self):
        first = schema.build_material_capability_schema_plan(
            absent_catalog()
        )
        second = schema.build_material_capability_schema_plan(
            absent_catalog()
        )

        self.assertEqual(first, second)
        self.assertTrue(first["ok"])
        self.assertFalse(first["complete"])
        self.assertTrue(first["schemaReady"])
        self.assertTrue(first["readyForApply"])
        self.assertEqual(first["blockers"], [])
        self.assertEqual(first["changeCount"], 9)
        self.assertEqual(len(first["changes"]), 9)
        self.assertEqual(len(first["rollbackSql"]), 9)
        self.assertRegex(first["planSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            first["planSha256"],
            schema.calculate_material_capability_schema_plan_sha256(
                first["changes"]
            ),
        )
        self.assertTrue(all(set(change) == {
            "name", "sql", "rollbackSql",
        } for change in first["changes"]))

    def test_exact_schema_is_complete_and_zero_change_hash_binds_contract(self):
        result = schema.build_material_capability_schema_plan(
            exact_catalog()
        )
        original_hash = result["planSha256"]

        self.assertTrue(result["ok"])
        self.assertTrue(result["complete"])
        self.assertTrue(result["schemaReady"])
        self.assertFalse(result["readyForApply"])
        self.assertEqual(result["changeCount"], 0)
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["rollbackSql"], [])

        with mock.patch.object(
            schema_contract,
            "CONTRACT_VERSION",
            schema.CONTRACT_VERSION + 1,
        ):
            changed = (
                schema.calculate_material_capability_schema_plan_sha256([])
            )
        self.assertNotEqual(changed, original_hash)

    def test_parent_schema_collision_and_every_contract_drift_block_apply(self):
        cases = []
        parent = absent_catalog(parentColumnsMissing=[
            "user_company_roles.active",
        ])
        cases.append(("parent", parent))
        parent_view = absent_catalog()
        parent_view["parentRelations"]["suppliers"]["relkind"] = "v"
        cases.append(("parent-view", parent_view))
        collision = absent_catalog(functions={
            "guard_supplier_material_capability_assertion_insert":
                "private function",
        })
        cases.append(("collision", collision))
        sequence_collision = absent_catalog(nameHolders={
            schema.IDENTITY_SEQUENCE_NAME: {"oid": 1, "relkind": "S"},
        })
        cases.append(("sequence-collision", sequence_collision))
        primary_key_collision = absent_catalog(nameHolders={
            "pk_smca_assertions": {"oid": 2, "relkind": "i"},
        })
        cases.append(("primary-key-collision", primary_key_collision))
        type_collision = absent_catalog(typeHolder={
            "oid": 3, "type": "e", "relationOid": 0,
        })
        cases.append(("table-type-collision", type_collision))
        for category in (
            "columns", "constraints", "indexes", "functions", "triggers",
        ):
            value = exact_catalog()
            key = next(iter(value[category]))
            value[category][key] = {"private": "drift"}
            cases.append((category, value))

        for name, catalog in cases:
            with self.subTest(name=name):
                result = schema.build_material_capability_schema_plan(catalog)
                self.assertFalse(result["ok"])
                self.assertFalse(result["complete"])
                self.assertFalse(result["readyForApply"])
                self.assertTrue(result["blockers"])
                self.assertEqual(result["changes"], [])

    def test_catalog_contract_uses_exact_structural_facts_not_substrings(self):
        contract = schema.material_capability_schema_contract()
        guard = contract["functions"][
            "guard_supplier_material_capability_assertion_insert"
        ]
        self.assertEqual(set(guard), {
            "language", "returns", "securityDefiner", "leakproof",
            "volatility", "parallel", "strict", "config", "bodySha256",
            "kind",
        })
        self.assertRegex(guard["bodySha256"], r"^[0-9a-f]{64}$")

        index = contract["indexes"]["uq_smca_confirmed_subject"]
        self.assertEqual(index["keyNames"], [
            "company_id", "confirmation_subject_sha256",
        ])
        self.assertEqual(index["keyOptions"], [0, 0])
        self.assertEqual(index["operatorClasses"], [
            "pg_catalog.int4_ops", "pg_catalog.text_ops",
        ])
        self.assertEqual(
            index["predicate"],
            "event_kind::text = 'confirmed'::text",
        )

        trigger = contract["triggers"]["smca_assertion_immutable"]
        self.assertEqual(trigger, {
            "enabled": "O",
            "type": 27,
            "function": (
                "public."
                "reject_supplier_material_capability_assertion_mutation"
            ),
            "condition": None,
            "argumentsHex": "",
            "columns": [],
            "constraint": False,
            "deferrable": False,
            "initiallyDeferred": False,
            "oldTable": None,
            "newTable": None,
        })
        actor_check = contract["constraints"]["ck_smca_actor"]
        self.assertEqual(actor_check["type"], "c")
        self.assertTrue(actor_check["validated"])
        self.assertIn("actor_role::text = 'директор'::text", actor_check[
            "definition"
        ])

    def test_exact_contract_rejects_semantic_bypasses_and_extra_trigger(self):
        cases = []

        value = exact_catalog()
        value["functions"][
            "guard_supplier_material_capability_assertion_insert"
        ]["bodySha256"] = "0" * 64
        cases.append(("bypassed-function", value))

        value = exact_catalog()
        value["columns"]["created_at"]["default"] = (
            "public.side_effect()+current_timestamp"
        )
        cases.append(("side-effect-default", value))

        value = exact_catalog()
        value["constraints"]["ck_smca_event_shape"]["definition"] = (
            "check(((event_kind::text='confirmed'::textand"
            "revokes_assertion_idisnullor"
            "event_kind::text='revoked'::text)and"
            "revokes_assertion_idisnotnullandrevokes_assertion_id<id))"
        )
        cases.append(("regrouped-check", value))

        value = exact_catalog()
        value["indexes"]["idx_smca_company_subject_id"]["valid"] = False
        cases.append(("invalid-lookup-index", value))

        value = exact_catalog()
        value["indexes"]["idx_smca_company_subject_id"][
            "predicate"
        ] = "false"
        cases.append(("partial-lookup-index", value))

        value = exact_catalog()
        value["indexes"]["uq_smca_confirmed_subject"][
            "predicate"
        ] = schema._canonical_sql(
            "event_kind::text = 'CONFIRMED'::text"
        )
        cases.append(("case-changed-index-literal", value))

        value = exact_catalog()
        value["indexes"]["uq_smca_confirmed_subject"][
            "predicate"
        ] = schema._canonical_sql(
            "event_kind::text = 'con firmed'::text"
        )
        cases.append(("space-changed-index-literal", value))

        value = exact_catalog()
        value["identitySequence"]["increment"] = 2
        cases.append(("sequence-options", value))

        value = exact_catalog()
        value["triggers"]["zz_rewrite_after_guard"] = copy.deepcopy(
            value["triggers"]["smca_assertion_insert_guard"]
        )
        cases.append(("extra-trigger", value))

        for name, catalog in cases:
            with self.subTest(name=name):
                result = schema.build_material_capability_schema_plan(catalog)
                self.assertFalse(result["ok"])
                self.assertFalse(result["complete"])
                self.assertFalse(result["readyForApply"])
                self.assertEqual(
                    result["blockers"],
                    ["material_capability_schema_drift"],
                )

    def test_ddl_is_append_only_director_scoped_revocable_and_inert(self):
        plan = schema.build_material_capability_schema_plan(absent_catalog())
        ddl = "\n".join(change["sql"] for change in plan["changes"])
        compact = " ".join(ddl.lower().split())

        for fragment in (
            "create table public.supplier_material_capability_assertions",
            "confirmation_version",
            "event_kind",
            "company_supplier_link_id",
            "material_identity_sha256",
            "confirmation_subject_sha256",
            "actor_membership_id",
            "actor_user_id",
            "actor_role",
            "source_kind",
            "revokes_assertion_id",
            "event_kind='confirmed'",
            "event_kind='revoked'",
            "actor_role='директор'",
            "source_kind='director_manual'",
            "where event_kind='confirmed'",
            "where event_kind='revoked'",
            "before insert",
            "membership.active is true",
            "actor_user.active is true",
            "company.active is true",
            "link.status='активный'",
            "supplier.status='активный'",
            "supplier_user.role='поставщик'",
            "not exists",
            "other_supplier.user_id=supplier.user_id",
            "before update or delete",
            "before truncate",
        ):
            self.assertIn(fragment, compact)
        for forbidden in (
            "supplier_catalog", "yandex", "llm", "smtp", "email",
            "messenger_outbox", "supplier_offers", "supply_request_recipients",
        ):
            self.assertNotIn(forbidden, compact)

    def test_dry_run_is_readonly_rolled_back_and_executes_no_schema_change(self):
        connection = FakeConnection()
        with mock.patch.object(
            schema, "_collect_catalog", return_value=absent_catalog()
        ):
            result = schema.run_material_capability_schema_migration(
                lambda: connection
            )

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertTrue(connection.closed)
        self.assertTrue(result["dryRun"])
        self.assertTrue(result["rolledBack"])
        self.assertFalse(result["committed"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        sql = " ".join(query for query, _ in connection.fake_cursor.calls)
        for forbidden in ("CREATE ", "ALTER ", "DROP ", "TRUNCATE "):
            self.assertNotIn(forbidden, sql.upper())

    def test_apply_requires_exact_count_and_hash_then_postchecks_and_commits(self):
        before = schema.build_material_capability_schema_plan(absent_catalog())
        connection = FakeConnection()
        with mock.patch.object(
            schema,
            "_collect_catalog",
            side_effect=(absent_catalog(), exact_catalog()),
        ):
            result = schema.run_material_capability_schema_migration(
                lambda: connection,
                apply=True,
                confirm=schema.APPLY_CONFIRMATION,
                expected_change_count=before["changeCount"],
                expected_plan_sha256=before["planSha256"],
            )

        self.assertEqual(connection.session, {
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        })
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(result["committed"])
        self.assertFalse(result["dryRun"])
        self.assertEqual(
            result["schemaWritesAttempted"], before["changeCount"]
        )
        calls = [query for query, _ in connection.fake_cursor.calls]
        lock_index = next(
            index for index, query in enumerate(calls)
            if query.startswith("LOCK TABLE")
        )
        advisory_index = next(
            index for index, query in enumerate(calls)
            if "pg_advisory_xact_lock" in query
        )
        first_create = next(
            index for index, query in enumerate(calls)
            if query.upper().startswith("CREATE ")
        )
        self.assertLess(lock_index, advisory_index)
        self.assertLess(advisory_index, first_create)

    def test_apply_guards_and_cleanup_failures_use_fixed_codes(self):
        invalid = (
            {},
            {"apply": True},
            {
                "apply": True,
                "confirm": "wrong",
                "expected_change_count": 9,
                "expected_plan_sha256": "a" * 64,
            },
            {
                "apply": True,
                "confirm": schema.APPLY_CONFIRMATION,
                "expected_change_count": True,
                "expected_plan_sha256": "a" * 64,
            },
        )
        for index, kwargs in enumerate(invalid[1:], 1):
            with self.subTest(index=index):
                with self.assertRaises(
                    schema.MaterialCapabilitySchemaMigrationError
                ) as error:
                    schema.run_material_capability_schema_migration(
                        lambda: FakeConnection(), **kwargs
                    )
                self.assertEqual(
                    error.exception.code,
                    "material_capability_schema_apply_guard_invalid",
                )

        rollback_connection = RollbackFails()
        with mock.patch.object(
            schema, "_collect_catalog", return_value=absent_catalog()
        ):
            with self.assertRaises(
                schema.MaterialCapabilitySchemaMigrationError
            ) as error:
                schema.run_material_capability_schema_migration(
                    lambda: rollback_connection
                )
        self.assertEqual(
            error.exception.code,
            "material_capability_schema_rollback_failed",
        )
        self.assertNotIn("private", str(error.exception))

        cleanup_connection = FakeConnection(CloseFailsCursor())
        with mock.patch.object(
            schema, "_collect_catalog", return_value=absent_catalog()
        ):
            with self.assertRaises(
                schema.MaterialCapabilitySchemaMigrationError
            ) as error:
                schema.run_material_capability_schema_migration(
                    lambda: cleanup_connection
                )
        self.assertEqual(
            error.exception.code,
            "material_capability_schema_cleanup_failed",
        )
        self.assertNotIn("private", str(error.exception))

    def test_catalog_collection_is_bounded_and_import_has_no_runtime_side_effect(self):
        source = inspect.getsource(schema_probe)
        self.assertNotIn("information_schema", source.lower())
        self.assertIn("LIMIT", source.upper())
        self.assertIn("trigger_state.tgenabled::text", source)
        self.assertNotIn("backend.main", inspect.getsource(schema))

        script = """
import atexit
import json
import sys
before = len(getattr(atexit, '_exithandlers', ()))
import backend.features.supply_recommendation_preview.material_capability_schema
print(json.dumps({
    'mainLoaded': 'backend.main' in sys.modules,
    'handlersAdded': len(getattr(atexit, '_exithandlers', ())) - before,
}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(schema.Path(__file__).resolve().parents[3])
            if hasattr(schema, "Path") else None,
            text=True,
            capture_output=True,
            check=True,
        )
        report = json.loads(completed.stdout)
        self.assertFalse(report["mainLoaded"])
        self.assertEqual(report["handlersAdded"], 0)


if __name__ == "__main__":
    unittest.main()
