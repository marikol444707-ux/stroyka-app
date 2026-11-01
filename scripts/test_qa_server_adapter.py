import json
import unittest
from unittest.mock import MagicMock
from scripts.qa_server_adapter import _QaServerAdapter, create_adapter, BINDS, BACKENDS
from scripts.qa_topology import TOPOLOGY
from scripts.qa_host_runtime import PYTHON_PATH


def make():
    transport, connect, store = MagicMock(), MagicMock(), MagicMock()
    manifest = dict(head='a'*40, db_user='qa_user', python_path=PYTHON_PATH,
                    recovery_root='/opt/stroyka-qa-recovery/reviewed',
                    other_writers_accounted_for=True, restart_prevented=True)
    return _QaServerAdapter(transport, connect, store, manifest)


def metadata(argv, **kwargs):
    if argv[:2] != ('docker', 'inspect'):
        raise AssertionError('unexpected command')
    fmt, name = argv[3], argv[4]
    if fmt == '{{json .Mounts}}':
        return json.dumps([dict(Type=k, Source=s, Destination=d, RW=w) for k,s,d,w in TOPOLOGY[name][2]])
    if fmt == '{{json .Image}}':
        return json.dumps(TOPOLOGY[name][0])
    if fmt == '{{json .Config.WorkingDir}}':
        return json.dumps(TOPOLOGY[name][1])
    if fmt == '{{json .NetworkSettings.Networks}}':
        return '{"stroyka-qa-net":{}}'
    if fmt == '{{json .State.Running}}':
        return 'false'
    for key, value in [('DB_HOST', 'stroyka-qa-db'), ('DB_NAME', 'stroyka_qa'), ('DB_PORT', '5432')]:
        if key + '=' in fmt:
            return json.dumps(key + '=' + value)
    raise AssertionError('unapproved metadata')


class AdapterTests(unittest.TestCase):
    def test_real_adapter_rejected_before_any_transport_by_orchestrator(self):
        from scripts.unified_release import _qa_restore_internal, _qa_prepare_internal
        a = make()
        with self.assertRaises(ValueError):
            _qa_restore_internal(a, 'bundle')
        with self.assertRaises(ValueError):
            _qa_prepare_internal(a, expected_sha='a'*40, statements=(), revisions=())
        a.transport.run.assert_not_called()
        a.connect.assert_not_called()

    def test_factory_always_held(self):
        t = MagicMock()
        with self.assertRaises(RuntimeError):
            create_adapter(t, force=True)
        self.assertEqual(t.mock_calls, [])

    def test_target_mapping_without_full_environment_or_exec(self):
        a = make()
        a.transport.run.side_effect = metadata
        self.assertEqual(a.verify_target(), ('stroyka-qa-db', 5432, 'stroyka_qa'))
        for call in a.transport.run.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[:2], ('docker', 'inspect'))
            self.assertNotIn('{{json .Config.Env}}', argv)

    def test_wrong_bind_fails(self):
        a = make()
        a.transport.run.return_value = '[]'
        with self.assertRaises(ValueError):
            a.verify_target()

    def test_transport_exception_is_sanitized(self):
        a = make()
        a.transport.run.side_effect = RuntimeError('secret synthetic')
        with self.assertRaisesRegex(RuntimeError, '^QA transport operation failed$'):
            a.verify_target()

    def test_backup_requires_quiescence(self):
        a = make()
        with self.assertRaises(ValueError):
            a.backup_database_files_code_and_config()
        a.transport.run.assert_not_called()

    def test_backup_exact_db_and_output_file(self):
        a = make()
        a.quiesced = True
        a.transport.run.side_effect = lambda argv, **kw: 'false' if argv[1]=='inspect' else ''
        a.backup_database_files_code_and_config()
        argv = a.transport.run.call_args.args[0]
        self.assertEqual(argv[:4], ('docker', 'exec', 'stroyka-qa-db', 'pg_dump'))
        self.assertEqual(argv[-1], 'stroyka_qa')
        self.assertIn('stdout_file', a.transport.run.call_args.kwargs)

    def test_stopped_candidate_migration_binding_stays_blocked(self):
        a = make()
        with self.assertRaisesRegex(ValueError, 'HOST_MIGRATION_RUNTIME_UNVERIFIED'):
            a.apply_migrations(['anything'])
        a.transport.run.assert_not_called()

    def test_host_migration_uses_existing_runtime_not_container_start(self):
        from scripts.qa_bootstrap_plan import migration_order
        from pathlib import Path
        a = make()
        a.quiesced = True
        runtime = MagicMock()
        runtime.dependencies_verified = runtime.connectivity_verified = True
        runtime.python_path = PYTHON_PATH
        runtime.verify_current_installation.return_value = True
        runtime.environment.return_value = dict(DB_HOST='172.18.0.2', DB_PORT='5432',
            DB_NAME='stroyka_qa', DB_USER='qa_user', DB_PASSWORD='synthetic-only')
        a.migration_runtime = runtime
        def run(argv, **kw):
            if argv[0] == 'git':
                return 'a'*40
            if argv[0] == runtime.python_path:
                return ''
            if argv[3] == '{{json .NetworkSettings.Networks}}':
                return '{"stroyka-qa-net":{"IPAddress":"172.18.0.2"}}'
            return metadata(argv, **kw)
        a.transport.run.side_effect = run
        revisions = migration_order(Path(__file__).resolve().parents[1] / 'migrations/versions')
        a.apply_migrations(revisions)
        final = a.transport.run.call_args
        self.assertEqual(final.args[0][1:4], ('-I', '-m', 'alembic'))
        self.assertEqual(final.kwargs['cwd'], BINDS[1])
        self.assertTrue(final.kwargs['replace_env'])
        self.assertTrue(final.kwargs['redact_output'])
        self.assertNotIn('synthetic-only', repr(final.args))
        self.assertFalse(any('start' in c.args[0] for c in a.transport.run.call_args_list))

    def test_unverified_host_runtime_stops_before_transport(self):
        a = make()
        a.migration_runtime = MagicMock(dependencies_verified=False, connectivity_verified=True)
        with self.assertRaises(ValueError):
            a.apply_migrations([])
        a.transport.run.assert_not_called()

    def test_database_restore_never_invents_clean_command(self):
        a = make()
        a.quiesced = True
        a.transport.run.side_effect = metadata
        a.store.verify.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'REPLACEMENT_SCOPE_UNACCEPTED'):
            a.restore_database('bundle')
        self.assertTrue(all(c.args[0][1] == 'inspect' for c in a.transport.run.call_args_list))

    def test_wrong_database_closes_connection(self):
        a = make()
        a.quiesced = True
        a.transport.run.side_effect = metadata
        c = a.connect.return_value
        c.autocommit = False
        c.cursor.return_value.__enter__.return_value.fetchone.return_value = ('wrong',)
        with self.assertRaises(RuntimeError):
            a.schema_connection()
        c.close.assert_called_once()

    def test_unknown_writers_block_constructor(self):
        a = make()
        with self.assertRaises(ValueError):
            _QaServerAdapter(a.transport, a.connect, a.store,
                             dict(a.manifest, other_writers_accounted_for=False))
