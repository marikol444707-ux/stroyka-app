"""Internal QA adapter. No CLI, automatic construction, or production target.

Only the held release tooling may eventually own this adapter. The transport is
explicitly injected; this module has no subprocess, socket or driver imports.
run(argv, stdin_file=None, stdout_file=None) must execute without a shell, preserve
file privacy, and return text only for metadata commands. It must never log secrets.
Filesystem bundle/restore attestations are injected independently of command exit
codes: a successful archive or pg_restore invocation is not verified recovery.
"""
import json
import re
from pathlib import PurePosixPath

DB = 'stroyka-qa-db'
DATABASE = 'stroyka_qa'
BACKENDS = ('stroyka-qa-backend', 'stroyka-qa-backend-candidate')
BINDS = ('/opt/stroyka-jev-d1d1e2e', '/opt/stroyka-jev-qa-7e89d73')
NETWORK = 'stroyka-qa-net'
HOLD = 'QA_BOOTSTRAP_EXECUTION_NOT_ACCEPTED'


def create_adapter(*args, **kwargs):
    raise RuntimeError(HOLD)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


class _QaServerAdapter:
    """Concrete command mapping behind a withheld transport/connection binding.

    Bundle store contract: create(manifest, dump_path), verify(bundle),
    restore_demonstrated(bundle), preserve_failure(), restore_part(bundle, name),
    verify_restored(bundle). The store must cover code/config/uploads/frontend,
    checksums and restore evidence. It is not implemented by pretend True results.
    No store or connection provider is instantiated here.
    """
    def __init__(self, transport, connection_provider, bundle_store, manifest):
        self.transport = transport
        self.connect = connection_provider
        self.store = bundle_store
        self.manifest = dict(manifest)
        _require(re.fullmatch(r'[0-9a-f]{40}', manifest.get('head', '')), 'Exact SHA required')
        _require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', manifest.get('db_user', '')), 'Explicit QA DB role required')
        python = manifest.get('python_path', '')
        _require(python.startswith('/') and '..' not in PurePosixPath(python).parts, 'Verified absolute interpreter required')
        root = manifest.get('recovery_root', '')
        _require(root.startswith('/opt/stroyka-qa-recovery/') and '..' not in PurePosixPath(root).parts,
                 'Dedicated QA recovery directory required')
        _require(manifest.get('other_writers_accounted_for') is True, 'Unknown additional writers')
        _require(manifest.get('restart_prevented') is True, 'Restart policy not controlled')
        # No implicit workers are invented. Unknown writers block construction.
        self.quiesced = False
        self.bundle = None

    def execution_bindings_ready(self):
        # Fail before backup or DDL: migration process and restore scope are not
        # established for a stopped candidate and the shared unversioned database.
        return False

    def _run(self, argv, **kwargs):
        try:
            return self.transport.run(tuple(argv), **kwargs)
        except Exception:
            # No raw Docker/PG stderr, environment, passwords or DSNs escape.
            raise RuntimeError('QA transport operation failed') from None

    def _inspect(self, name, expression):
        return json.loads(self._run(['docker', 'inspect', '--format', expression, name]))

    def verify_target(self):
        for name, bind in zip(BACKENDS, BINDS):
            # Do not inspect full Env: it can contain credentials.
            mounts = self._inspect(name, '{{json .Mounts}}')
            _require(any(m.get('Destination') == '/app' and m.get('Source') == bind
                         and m.get('Type') == 'bind' for m in mounts), 'Unexpected QA application bind')
            for key, expected in (('DB_HOST', DB), ('DB_NAME', DATABASE), ('DB_PORT', '5432')):
                # Fixed allowlisted non-secret keys only; no full environment read.
                prefix = key + '='
                expression = ('{{range .Config.Env}}{{if and (ge (len .) ' + str(len(prefix))
                              + ') (eq (slice . 0 ' + str(len(prefix)) + ') "' + prefix
                              + '")}}{{json .}}{{end}}{{end}}')
                value = self._inspect(name, expression)
                _require(value == prefix + expected, 'QA database mapping mismatch')
        for name in (*BACKENDS, DB):
            networks = self._inspect(name, '{{json .NetworkSettings.Networks}}')
            _require(NETWORK in networks, 'QA network mismatch')
        return DB, 5432, DATABASE

    def code_sha(self):
        return self._run(['git', '-C', BINDS[1], 'rev-parse', 'HEAD']).strip()

    def quiesce_both_backends_and_workers(self):
        self.verify_target()
        self._run(['docker', 'stop', *BACKENDS])
        self.quiesced = self.writers_stopped()
        _require(self.quiesced, 'QA writers did not stop')

    def writers_stopped(self):
        return all(self._inspect(name, '{{json .State.Running}}') is False for name in BACKENDS)

    def backup_database_files_code_and_config(self):
        _require(self.quiesced and self.writers_stopped(), 'Backup requires stopped writers')
        dump = self.manifest['recovery_root'] + '/database.dump'
        self._run(['docker', 'exec', DB, 'pg_dump', '--format=custom', '--no-password',
                   '--username', self.manifest['db_user'], '--dbname', DATABASE], stdout_file=dump)
        # Store must preserve both bind trees, runtime config and exact frontend/uploads.
        self.bundle = self.store.create(dict(self.manifest), dump)
        return self.bundle

    def verify_recovery_bundle(self, bundle):
        return self.store.verify(bundle) is True

    def restore_demonstrated(self, bundle):
        return self.store.restore_demonstrated(bundle) is True

    def schema_connection(self):
        _require(self.quiesced and self.writers_stopped(), 'QA writers active')
        # Provider must use the verified QA endpoint and an explicit transaction.
        conn = None
        try:
            conn = self.connect(host=DB, port=5432, dbname=DATABASE, user=self.manifest['db_user'])
            _require(conn.autocommit is False, 'Explicit transaction required')
            with conn.cursor() as cur:
                cur.execute('SELECT current_database()')
                _require(cur.fetchone() == (DATABASE,), 'Wrong connected database')
            conn.rollback()
            return conn
        except Exception:
            if conn is not None:
                conn.close()
            raise RuntimeError('QA connection validation failed') from None

    def schema_is_empty(self):
        conn = self.schema_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                            "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')")
                result = cur.fetchone() == (0,)
            conn.rollback()
            return result
        finally:
            conn.close()

    def apply_migrations(self, revisions):
        # A stopped candidate cannot docker-exec. Starting it would invoke main
        # and defeat bootstrap ordering. Do not silently run a new container.
        raise RuntimeError('QA_MIGRATION_PROCESS_BINDING_UNRESOLVED: candidate must remain stopped')

    def verify_schema(self, revision):
        return self.store.verify_schema_contract(revision) is True

    def preserve_failed_state(self):
        _require(self.quiesced and self.writers_stopped(), 'QA writers active')
        self.store.preserve_failure()

    def restore_database(self, bundle):
        _require(self.quiesced and self.writers_stopped(), 'QA writers active')
        _require(self.verify_recovery_bundle(bundle), 'Unverified recovery bundle')
        # Restoration requires scope/ownership/catalog confirmation not provided
        # by pg_restore --list. Never invent --clean/--create here.
        raise RuntimeError('QA_DATABASE_REPLACEMENT_SCOPE_UNACCEPTED')

    def restore_uploads(self, bundle):
        _require(self.quiesced and self.writers_stopped() and self.verify_recovery_bundle(bundle), 'QA restore prerequisites missing')
        self.store.restore_part(bundle, 'uploads')

    def restore_both_code_versions_and_config(self, bundle):
        _require(self.quiesced and self.writers_stopped() and self.verify_recovery_bundle(bundle), 'QA restore prerequisites missing')
        self.store.restore_part(bundle, 'both_code_versions_and_config')

    def restore_frontend(self, bundle):
        _require(self.quiesced and self.writers_stopped() and self.verify_recovery_bundle(bundle), 'QA restore prerequisites missing')
        self.store.restore_part(bundle, 'frontend')

    def verify_restored_bundle(self, bundle):
        return self.store.verify_restored(bundle) is True
