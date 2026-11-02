"""QA maintenance only. Import is inert; all DB calls require explicit entry.

No reconnect/retry of a reset. The durable journal survives process death;
SIGKILL/power loss require reviewed recovery, not an automatic success claim.
"""
import json
import os
from pathlib import Path

QA = 'stroyka_qa'
TARGET = '0109_legacy_payment_requests'


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.file = os.fdopen(fd, 'w')
        parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)

    def record(self, **event):
        self.file.write(json.dumps(event, sort_keys=True) + '\n')
        self.file.flush()
        os.fsync(self.file.fileno())

    def close(self):
        self.file.close()


def identity(conn):
    return tuple(conn.exec_driver_sql('''SELECT current_database(),
        (SELECT oid::bigint FROM pg_database WHERE datname=current_database()),
        (SELECT system_identifier::text FROM pg_control_system()),
        inet_server_addr()::text, inet_server_port(), pg_backend_pid()''').one())


def maintain(control, work, *, service_database, expected_host, statements, upgrade, journal):
    """Connections are already open. Control must be AUTOCOMMIT; work idle.

    Only this fixed QA database may be altered. The caller obtains fresh,
    action-specific consent before creating these connections.
    """
    c = identity(control)
    w = identity(work)
    work.rollback()  # finish the read-only identity transaction
    require(c[0] == service_database and service_database != QA, 'Wrong control database')
    require(w[0] == QA and c[2:5] == w[2:5] and c[3] == expected_host
            and c[4] == 5432 and c[5] != w[5], 'QA server identity mismatch')
    require(control.get_execution_options().get('isolation_level') == 'AUTOCOMMIT', 'Control must use AUTOCOMMIT')
    # AUTOCOMMIT is separately set by the sole real connection factory below.
    locked = control.exec_driver_sql('SELECT pg_try_advisory_lock(193701, hashtext(%s))', (QA,)).scalar()
    require(locked is True, 'Another maintenance operation is active')
    altered = False
    safe_restore = True
    try:
        require(control.exec_driver_sql('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').scalar() is True,
                'Existing maintenance privileges insufficient; no grants are made')
        original = control.exec_driver_sql(
            'SELECT datallowconn FROM pg_database WHERE oid=%s AND datname=%s', (w[1], QA)).scalar()
        require(original is True, 'QA already closed; explicit journal recovery required')
        require(control.exec_driver_sql('SELECT count(*) FROM pg_prepared_xacts WHERE database=%s', (QA,)).scalar() == 0,
                'Prepared QA transactions require separate review')
        require(control.exec_driver_sql('SELECT count(*) FROM pg_subscription WHERE subdbid=%s', (w[1],)).scalar() == 0,
                'QA subscriptions require separate review')
        journal.record(phase='before_gate', database=QA, database_oid=w[1],
                       system_identifier=w[2], server_address=w[3], server_port=w[4],
                       control_database=c[0], worker_pid=w[5], original_allow_connections=original)
        altered = True  # includes an uncertain ALTER response
        control.exec_driver_sql('ALTER DATABASE stroyka_qa ALLOW_CONNECTIONS false')
        journal.record(phase='gate_closed')
        for attempt in range(5):
            sessions = control.exec_driver_sql(
                'SELECT pid, backend_type FROM pg_stat_activity WHERE datid=%s AND pid<>%s', (w[1], w[5])).all()
            if not sessions:
                break
            require(all(kind == 'client backend' for _, kind in sessions), 'Unexpected QA background worker')
            for pid, _ in sessions:
                require(control.exec_driver_sql('SELECT pg_terminate_backend(%s, 5000)', (pid,)).scalar() is True,
                        'QA session termination not confirmed')
        else:
            raise ValueError('QA sessions did not drain')
        require(control.exec_driver_sql('SELECT datallowconn FROM pg_database WHERE oid=%s', (w[1],)).scalar() is False,
                'QA connection gate changed')
        journal.record(phase='transaction_start')
        tx = work.begin()
        safe_restore = False
        commit_attempted = False
        try:
            work.exec_driver_sql('SET LOCAL lock_timeout = \'5s\'')
            work.exec_driver_sql('SET LOCAL statement_timeout = \'120s\'')
            require(work.exec_driver_sql("SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%'").scalar() == 0,
                    'Unexpected schema')
            require(work.exec_driver_sql("SELECT count(*) FROM pg_extension WHERE extname<>'plpgsql'").scalar() == 0,
                    'Unexpected extension')
            work.exec_driver_sql('DROP SCHEMA public CASCADE')
            work.exec_driver_sql('CREATE SCHEMA public AUTHORIZATION CURRENT_USER')
            for statement in statements:
                work.exec_driver_sql(statement, execution_options={'no_parameters': True})
            upgrade(work)
            require(work.exec_driver_sql('SELECT version_num FROM public.alembic_version').all() == [(TARGET,)],
                    'Migration head mismatch')
            journal.record(phase='commit_requested')
            commit_attempted = True
            tx.commit()
            safe_restore = True
            journal.record(phase='committed')
        except BaseException:
            if tx.is_active:
                tx.rollback()
                safe_restore = not commit_attempted
                journal.record(phase='rollback_after_commit_error' if commit_attempted else 'rolled_back')
            raise
    finally:
        try:
            if altered and safe_restore:
                # Same live control connection; never reconnect or guess an identity.
                require(identity(control) == c, 'Control identity changed during recovery')
                control.exec_driver_sql('ALTER DATABASE stroyka_qa ALLOW_CONNECTIONS true')
                require(control.exec_driver_sql('SELECT datallowconn FROM pg_database WHERE oid=%s', (w[1],)).scalar() is True,
                        'QA access restoration unconfirmed')
                journal.record(phase='access_restored')
            elif altered:
                journal.record(phase='outcome_unknown_access_closed', recovery_required=True)
        finally:
            control.exec_driver_sql('SELECT pg_advisory_unlock(193701, hashtext(%s))', (QA,))


def run(payload, environment):
    """Internal child entry. No CLI which bypasses unified_release confirmation."""
    import ast
    import ipaddress
    import signal
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from sqlalchemy.pool import NullPool
    from alembic.config import Config
    from alembic import command
    require(payload.get('confirmed_scope') == 'qa_connection_gate_and_session_termination', 'Exact consent missing')
    service = payload['maintenance_database']
    require(service == 'postgres', 'Only the existing postgres maintenance database is supported')
    require(environment['DB_NAME'] == QA and environment['DB_PORT'] == '5432', 'Wrong QA target')
    host = str(ipaddress.ip_address(environment['DB_HOST']))
    root = Path(payload['root'])
    require(str(root) == '/opt/stroyka-jev-qa-7e89d73', 'Wrong candidate root')
    tree = ast.parse((root / 'backend/bootstrap_schema.py').read_text())
    steps = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'LEGACY_STEPS' for t in n.targets))
    statements = [sql for kind, sql in steps if kind == 'schema']
    require(statements, 'No base schema')
    def engine(database):
        return create_engine(URL.create('postgresql+psycopg2', host=host, port=5432,
            database=database, username=environment['DB_USER'], password=environment['DB_PASSWORD']),
            poolclass=NullPool, isolation_level='READ COMMITTED', connect_args={'connect_timeout': 5,
                'options': '-c statement_timeout=120000 -c lock_timeout=5000'})
    def interrupted(signum, frame):
        raise InterruptedError('QA maintenance interrupted')
    previous = signal.signal(signal.SIGTERM, interrupted)
    journal = Journal(payload['journal'])
    control_engine = engine(service)
    work_engine = engine(QA)
    try:
        with control_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as control, work_engine.connect() as work:
            def upgrade(connection):
                cfg = Config(str(root / 'alembic.ini'))
                cfg.set_main_option('script_location', str(root / 'migrations'))
                cfg.attributes['connection'] = connection
                command.upgrade(cfg, TARGET)
            maintain(control, work, service_database=service, expected_host=host,
                     statements=statements, upgrade=upgrade, journal=journal)
    finally:
        control_engine.dispose()
        work_engine.dispose()
        journal.close()
        signal.signal(signal.SIGTERM, previous)
