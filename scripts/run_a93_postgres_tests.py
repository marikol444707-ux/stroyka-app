#!/usr/bin/env python3
"""Run A9.3 PostgreSQL proofs in one launcher-owned disposable cluster."""

import getpass
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_MAJOR = 15
POSTGRES_PORT = 55432
POSTGRES_PROGRAMS = (
    "postgres",
    "initdb",
    "pg_ctl",
    "createdb",
    "dropdb",
)
TEST_MODULE = (
    "backend.features.estimate_revision_impact."
    "test_resource_limits_postgres"
)
_OWNED_PROCESS_GROUPS = set()
CAPABILITY_FILENAME = "launcher.capability"


def _postgres_programs():
    discovered = {
        name: shutil.which(name)
        for name in POSTGRES_PROGRAMS
    }
    if any(not path for path in discovered.values()):
        return None
    programs = {
        name: str(Path(path).resolve())
        for name, path in discovered.items()
    }
    directories = {
        str(Path(path).resolve().parent)
        for path in programs.values()
    }
    if len(directories) != 1:
        return None
    try:
        version = subprocess.run(
            [programs["postgres"], "--version"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            timeout=10,
            env=_subprocess_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    version_match = re.search(
        r"\b([0-9]+)\.[0-9]+",
        version.stdout or "",
    )
    if (
        version.returncode != 0
        or version_match is None
        or int(version_match.group(1)) != POSTGRES_MAJOR
    ):
        return None
    return programs


def _subprocess_environment():
    allowed = (
        "HOME",
        "LANG",
        "LC_ALL",
        "LOGNAME",
        "PATH",
        "TMPDIR",
        "USER",
    )
    environment = {
        key: os.environ[key]
        for key in allowed
        if key in os.environ
    }
    environment["LANG"] = "C"
    environment["LC_ALL"] = "C"
    return environment


def _python_driver_available(environment):
    try:
        completed = subprocess.run(
            [sys.executable, "-c", "import psycopg2"],
            cwd=str(PROJECT_ROOT),
            env=environment,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            shell=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _terminate_process_group(process, *, timeout=5):
    if process is None or process.poll() is not None:
        return True
    for termination_signal in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, termination_signal)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        try:
            process.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            continue
    return process.poll() is not None


def _run(
    command,
    *,
    environment,
    cwd=PROJECT_ROOT,
    timeout=60,
    check=True,
    pass_fds=(),
):
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=environment,
        text=True,
        shell=False,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        pass_fds=tuple(pass_fds),
    )
    _OWNED_PROCESS_GROUPS.add(process.pid)
    try:
        returncode = process.wait(timeout=timeout)
    except BaseException:
        if _terminate_process_group(process):
            _OWNED_PROCESS_GROUPS.discard(process.pid)
        raise
    _OWNED_PROCESS_GROUPS.discard(process.pid)
    completed = subprocess.CompletedProcess(command, returncode)
    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, command)
    return completed


def _stop_server(pg_ctl, data_dir, environment):
    for mode in ("fast", "immediate"):
        try:
            _run(
                [
                    pg_ctl,
                    "--pgdata", str(data_dir),
                    "--mode", mode,
                    "--wait",
                    "stop",
                ],
                environment=environment,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def _is_private_directory(path, *, parent=None):
    path = Path(path)
    metadata = os.lstat(path)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        return False
    if parent is not None and path.resolve().parent != Path(parent).resolve():
        return False
    return True


def _directory_identity(path):
    metadata = os.lstat(path)
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_uid,
        stat.S_IMODE(metadata.st_mode),
    )


def _directory_matches(path, identity, *, parent):
    if path is None or identity is None:
        return False
    try:
        return (
            _directory_identity(path) == identity
            and _is_private_directory(path, parent=parent)
        )
    except OSError:
        return False


def _create_capability_marker(root, capability):
    path = Path(root) / CAPABILITY_FILENAME
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, capability.encode("ascii"))
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _fixture_paths_match(
    root,
    data_dir,
    socket_dir,
    *,
    root_identity,
    data_identity,
    socket_identity,
):
    return (
        _directory_matches(
            root,
            root_identity,
            parent="/private/tmp",
        )
        and _directory_matches(
            data_dir,
            data_identity,
            parent=root,
        )
        and _directory_matches(
            socket_dir,
            socket_identity,
            parent=root,
        )
    )


def _cleanup_paths_are_safe(
    root,
    data_dir,
    socket_dir,
    *,
    root_identity,
    data_identity,
    socket_identity,
):
    return not _OWNED_PROCESS_GROUPS and _fixture_paths_match(
        root,
        data_dir,
        socket_dir,
        root_identity=root_identity,
        data_identity=data_identity,
        socket_identity=socket_identity,
    )


def _clear_directory_fd(directory_fd):
    open_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        open_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        open_flags |= os.O_NOFOLLOW
    for name in os.listdir(directory_fd):
        metadata = os.stat(
            name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if stat.S_ISDIR(metadata.st_mode):
            child_fd = os.open(name, open_flags, dir_fd=directory_fd)
            try:
                child_metadata = os.fstat(child_fd)
                if (
                    child_metadata.st_dev != metadata.st_dev
                    or child_metadata.st_ino != metadata.st_ino
                ):
                    raise OSError("fixture directory identity changed")
                _clear_directory_fd(child_fd)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)


def _read_postmaster_pid(data_dir):
    try:
        value = (Path(data_dir) / "postmaster.pid").read_text(
            encoding="ascii"
        ).splitlines()[0]
        pid = int(value)
    except (IndexError, OSError, TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _process_is_gone(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (OSError, PermissionError):
        return False
    return False


def _pg_ctl_reports_stopped(pg_ctl, data_dir, environment):
    try:
        completed = subprocess.run(
            [pg_ctl, "--pgdata", str(data_dir), "status"],
            cwd=str(PROJECT_ROOT),
            env=environment,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            shell=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 3


def _server_is_dead(
    data_dir,
    socket_dir,
    *,
    pid,
    pg_ctl,
    environment,
):
    socket_name = ".s.PGSQL." + str(POSTGRES_PORT)
    artifacts_absent = not any((
        (Path(data_dir) / "postmaster.pid").exists(),
        (Path(socket_dir) / socket_name).exists(),
        (Path(socket_dir) / (socket_name + ".lock")).exists(),
    ))
    return (
        artifacts_absent
        and _pg_ctl_reports_stopped(pg_ctl, data_dir, environment)
        and _process_is_gone(pid)
    )


def _remove_fixture_root(
    root,
    data_dir,
    socket_dir,
    *,
    original_identity,
    death_confirmed,
    data_identity=None,
    socket_identity=None,
):
    if root is None or data_dir is None or socket_dir is None:
        return False
    root = Path(root)
    data_dir = Path(data_dir)
    socket_dir = Path(socket_dir)
    if not death_confirmed:
        return False
    if _OWNED_PROCESS_GROUPS:
        return False
    if not _directory_matches(
        root,
        original_identity,
        parent="/private/tmp",
    ):
        return False
    for path, identity in (
        (data_dir, data_identity),
        (socket_dir, socket_identity),
    ):
        if path is None:
            continue
        if path.exists() and identity is not None and not _directory_matches(
            path,
            identity,
            parent=root,
        ):
            return False
        if path.exists() and identity is None and not _is_private_directory(
            path,
            parent=root,
        ):
            return False
    parent = root.parent
    parent_fd = os.open(parent, os.O_RDONLY)
    root_fd = None
    try:
        open_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            open_flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            open_flags |= os.O_NOFOLLOW
        root_fd = os.open(root.name, open_flags, dir_fd=parent_fd)
        metadata = os.fstat(root_fd)
        if (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_uid,
            stat.S_IMODE(metadata.st_mode),
        ) != original_identity:
            return False
        _clear_directory_fd(root_fd)
        current = os.stat(
            root.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            current.st_dev,
            current.st_ino,
            current.st_uid,
            stat.S_IMODE(current.st_mode),
        ) != original_identity:
            return False
        os.rmdir(root.name, dir_fd=parent_fd)
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent_fd)
    return not root.exists()


def _handle_termination(signum, _frame):
    raise SystemExit(128 + int(signum))


def _test_environment(
    environment,
    *,
    root,
    socket_dir,
    database_name,
    database_user,
    capability,
    capability_fd,
):
    result = dict(environment)
    dsn = (
        "dbname=" + database_name
        + " user=" + database_user
        + " host=" + str(socket_dir)
        + " port=" + str(POSTGRES_PORT)
        + " connect_timeout=5"
    )
    result.update({
        "A93_RUN_POSTGRES_INTEGRATION": "1",
        "A93_TEST_CLUSTER_ROOT": str(root),
        "A93_TEST_CAPABILITY": capability,
        "A93_TEST_CAPABILITY_FD": str(capability_fd),
        "A93_TEST_DATABASE_DSN": dsn,
        "A93_TEST_DATABASE_USER": database_user,
        "A93_TEST_SOCKET_DIR": str(socket_dir),
        "DB_HOST": str(socket_dir),
        "DB_NAME": database_name,
        "DB_PASSWORD": "",
        "DB_PORT": str(POSTGRES_PORT),
        "DB_USER": database_user,
        "PGDATABASE": database_name,
        "PGHOST": str(socket_dir),
        "PGPORT": str(POSTGRES_PORT),
        "PGUSER": database_user,
        "PYTHONPYCACHEPREFIX": str(root / "pycache"),
    })
    return result


def main():
    programs = _postgres_programs()
    if programs is None:
        print(
            "SKIP: A9.3 PostgreSQL proof requires one local PostgreSQL 15 "
            "toolchain; nothing was downloaded or contacted."
        )
        return 0

    database_user = getpass.getuser()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", database_user):
        print("SKIP: local PostgreSQL user name is not safely representable.")
        return 0

    database_name = "a93_" + secrets.token_hex(8)
    capability = secrets.token_hex(32)
    environment = _subprocess_environment()
    if not _python_driver_available(environment):
        print(
            "SKIP: A9.3 PostgreSQL proof requires the already-installed "
            "psycopg2 driver; nothing was downloaded or contacted."
        )
        return 0
    handled_signals = tuple(
        candidate
        for candidate in (
            getattr(signal, "SIGHUP", None),
            signal.SIGINT,
            signal.SIGTERM,
        )
        if candidate is not None
    )
    previous_handlers = {}
    root = None
    data_dir = None
    socket_dir = None
    log_path = None
    root_identity = None
    data_identity = None
    socket_identity = None
    capability_fd = None
    server_start_attempted = False
    postmaster_pid = None
    database_created = False
    cluster_environment = None
    test_exit = 1
    cleanup_failed = False
    try:
        for candidate in handled_signals:
            previous_handlers[candidate] = signal.getsignal(candidate)
            signal.signal(candidate, _handle_termination)
        root = Path(tempfile.mkdtemp(
            prefix="stroyka-a93-pg-",
            dir="/private/tmp",
        )).resolve()
        data_dir = root / "data"
        socket_dir = root / "socket"
        log_path = root / "postgres.log"
        root_identity = _directory_identity(root)
        socket_dir.mkdir(mode=0o700)
        socket_identity = _directory_identity(socket_dir)
        capability_fd = _create_capability_marker(root, capability)
        cluster_environment = dict(environment)
        cluster_environment.update({
            "PGHOST": str(socket_dir),
            "PGPORT": str(POSTGRES_PORT),
            "PGUSER": database_user,
        })
        if not _is_private_directory(root, parent="/private/tmp"):
            raise RuntimeError("temporary PostgreSQL root is not private")
        if not _is_private_directory(socket_dir, parent=root):
            raise RuntimeError("temporary PostgreSQL socket is not private")
        _run(
            [
                programs["initdb"],
                "--pgdata", str(data_dir),
                "--encoding", "UTF8",
                "--locale", "C",
                "--auth-local", "trust",
                "--auth-host", "reject",
                "--username", database_user,
            ],
            environment=environment,
        )
        data_identity = _directory_identity(data_dir)
        server_start_attempted = True
        _run(
            [
                programs["pg_ctl"],
                "--pgdata", str(data_dir),
                "--log", str(log_path),
                "--options",
                "-c listen_addresses='' "
                "-c unix_socket_directories='" + str(socket_dir) + "' "
                "-c port=" + str(POSTGRES_PORT) + " "
                "-c fsync=off "
                "-c synchronous_commit=off "
                "-c full_page_writes=off",
                "--wait",
                "start",
            ],
            environment=environment,
        )
        postmaster_pid = _read_postmaster_pid(data_dir)
        if postmaster_pid is None:
            raise RuntimeError("PostgreSQL postmaster identity is unavailable")
        _run(
            [
                programs["createdb"],
                "--host", str(socket_dir),
                "--port", str(POSTGRES_PORT),
                "--username", database_user,
                database_name,
            ],
            environment=cluster_environment,
        )
        database_created = True

        completed = _run(
            [sys.executable, "-m", "unittest", TEST_MODULE],
            cwd=str(PROJECT_ROOT),
            environment=_test_environment(
                environment,
                root=root,
                socket_dir=socket_dir,
                database_name=database_name,
                database_user=database_user,
                capability=capability,
                capability_fd=capability_fd,
            ),
            timeout=300,
            check=False,
            pass_fds=(capability_fd,),
        )
        test_exit = completed.returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            "A9.3 disposable PostgreSQL command failed: "
            + type(exc).__name__,
            file=sys.stderr,
        )
        if log_path is not None and log_path.is_file():
            print(log_path.read_text(encoding="utf-8"), file=sys.stderr)
        test_exit = 1
    finally:
        for candidate in previous_handlers:
            try:
                signal.signal(candidate, signal.SIG_IGN)
            except (OSError, RuntimeError, ValueError):
                cleanup_failed = True

        if (
            server_start_attempted
            and postmaster_pid is None
            and data_dir is not None
        ):
            postmaster_pid = _read_postmaster_pid(data_dir)

        destructive_paths_valid = False
        if (
            root is not None
            and data_dir is not None
            and socket_dir is not None
            and root_identity is not None
            and data_identity is not None
            and socket_identity is not None
        ):
            destructive_paths_valid = _cleanup_paths_are_safe(
                root,
                data_dir,
                socket_dir,
                root_identity=root_identity,
                data_identity=data_identity,
                socket_identity=socket_identity,
            )

        if (
            database_created
            and cluster_environment is not None
            and destructive_paths_valid
        ):
            try:
                _run(
                    [
                        programs["dropdb"],
                        "--if-exists",
                        "--host", str(socket_dir),
                        "--port", str(POSTGRES_PORT),
                        "--username", database_user,
                        database_name,
                    ],
                    environment=cluster_environment,
                )
            except (OSError, subprocess.SubprocessError):
                cleanup_failed = True

        elif database_created:
            cleanup_failed = True

        if destructive_paths_valid:
            destructive_paths_valid = _cleanup_paths_are_safe(
                root,
                data_dir,
                socket_dir,
                root_identity=root_identity,
                data_identity=data_identity,
                socket_identity=socket_identity,
            )
        if server_start_attempted and destructive_paths_valid:
            try:
                _stop_server(
                    programs["pg_ctl"],
                    data_dir,
                    environment,
                )
            except (OSError, subprocess.SubprocessError):
                cleanup_failed = True
        elif server_start_attempted:
            cleanup_failed = True

        if capability_fd is not None:
            try:
                os.close(capability_fd)
            except OSError:
                cleanup_failed = True
            capability_fd = None

        if root is not None and root_identity is not None:
            socket_name = ".s.PGSQL." + str(POSTGRES_PORT)
            no_server_was_attempted = (
                not server_start_attempted
                and data_dir is not None
                and socket_dir is not None
                and not (data_dir / "postmaster.pid").exists()
                and not (socket_dir / socket_name).exists()
                and not (socket_dir / (socket_name + ".lock")).exists()
            )
            death_confirmed = no_server_was_attempted
            if (
                server_start_attempted
                and _cleanup_paths_are_safe(
                    root,
                    data_dir,
                    socket_dir,
                    root_identity=root_identity,
                    data_identity=data_identity,
                    socket_identity=socket_identity,
                )
            ):
                death_confirmed = _server_is_dead(
                    data_dir,
                    socket_dir,
                    pid=postmaster_pid,
                    pg_ctl=programs["pg_ctl"],
                    environment=environment,
                )
            try:
                removed = _remove_fixture_root(
                    root,
                    data_dir,
                    socket_dir,
                    original_identity=root_identity,
                    death_confirmed=death_confirmed,
                    data_identity=data_identity,
                    socket_identity=socket_identity,
                )
            except (OSError, RuntimeError):
                removed = False
            if not removed:
                cleanup_failed = True
        elif root is not None:
            cleanup_failed = True

        if cleanup_failed:
            if root is not None and root.exists():
                message = (
                    "A9.3 disposable PostgreSQL teardown is uncertain; "
                    "preserved " + str(root)
                )
            else:
                message = "A9.3 disposable PostgreSQL teardown failed"
            print(message, file=sys.stderr)

        for candidate, previous in previous_handlers.items():
            try:
                signal.signal(candidate, previous)
            except (OSError, RuntimeError, ValueError):
                cleanup_failed = True

    if cleanup_failed:
        return 1
    return test_exit


if __name__ == "__main__":
    raise SystemExit(main())
