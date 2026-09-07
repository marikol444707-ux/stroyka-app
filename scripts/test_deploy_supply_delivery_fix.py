#!/usr/bin/env python3
"""Exercise the deployment runner in a temporary fake host, never production.

Run with: python3 scripts/test_deploy_supply_delivery_fix.py
Only the runner's three hardcoded filesystem locations are substituted. Its
control flow, traps, background child, and rollback execute in a real shell.
Network, database, git, and service commands are local, fail-closed fakes.
"""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


RUNNER = Path(__file__).with_name("deploy-supply-delivery-fix.sh")
BEFORE = "a559ae9aaa3218e51cb31e997047d0d1e8718a13"
TARGET = "1" * 40
ORIGINAL_FRONTEND = '{"release":"before"}\n'


FAKE_COMMAND = r'''
import json, os, pathlib, shutil, signal, sys

root = pathlib.Path(os.environ["FAKE_HOST"])
command = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]

def event(kind, **details):
    record = {"command": kind, "args": args, **details}
    fd = os.open(root / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(record) + "\n").encode())
    finally:
        os.close(fd)

def fail(message):
    print("FAKE HOST REJECTED: " + message, file=sys.stderr)
    sys.exit(97)

def local_path(value):
    value = pathlib.Path(value).resolve()
    if root not in value.parents:
        fail("path outside fake host")
    return value

event(command)
head_file = root / "head"
if command == "git":
    if args == ["rev-parse", "HEAD"]:
        print(head_file.read_text().strip())
    elif args == ["branch", "--show-current"]:
        print("main")
    elif args == ["rev-parse", "FETCH_HEAD"]:
        print(os.environ.get("FAKE_FETCH_HEAD", os.environ["SUPPLY_RELEASE_COMMIT"]))
    elif args[:1] == ["diff"]:
        if os.environ.get("FAKE_DIRTY") == "unstaged" and args == ["diff", "--quiet"]:
            sys.exit(1)
        if os.environ.get("FAKE_DIRTY") == "staged" and args == ["diff", "--cached", "--quiet"]:
            sys.exit(1)
        if args not in (["diff", "--quiet"], ["diff", "--cached", "--quiet"]):
            if len(args) < 5 or args[1] != "--quiet" or args[4] != "--":
                fail("unexpected git diff")
    elif args == ["fetch", "origin", "main"]:
        pass
    elif args[:2] == ["merge-base", "--is-ancestor"]:
        pass
    elif args == ["merge", "--ff-only", os.environ["SUPPLY_RELEASE_COMMIT"]]:
        head_file.write_text(args[2])
    elif args == ["switch", "--detach", os.environ["FAKE_BEFORE"]]:
        head_file.write_text(args[2])
    else:
        fail("unexpected or destructive git command " + repr(args))
elif command == "flock":
    if args != ["-n", "8"]:
        fail("unexpected lock invocation")
    if os.environ.get("FAKE_LOCK_FAILURE") == "1":
        sys.exit(1)
elif command == "systemctl":
    if args[:2] == ["is-active", "--quiet"] and len(args) == 3:
        if args[2] == "stroyka-agent-job-worker.service":
            sys.exit(0 if os.environ.get("FAKE_WORKER_ACTIVE", "1") == "1" else 3)
        if args[2] not in ("stroyka", "nginx"):
            fail("unknown service")
    elif args == ["restart", "stroyka-agent-job-worker.service"]:
        if os.environ.get("FAKE_WORKER_ROLLBACK_FAILURE") == "1":
            sys.exit(1)
    elif args != ["restart", "stroyka"]:
        fail("unexpected service mutation")
elif command == "nginx":
    if args != ["-t"]:
        fail("unexpected nginx command")
elif command == "setsid":
    if len(args) != 2 or args[0] != "bash":
        fail("unexpected child launch")
    script = local_path(args[1])
    os.setsid()
    (root / "deploy-pid").write_text(str(os.getpid()))
    os.execv("/bin/bash", ["bash", str(script)])
elif command == "python3":
    if args == ["-m", "alembic", "current"]:
        print("0006_user_company_staff_links (head)")
    elif args[:1] == ["-"]:
        sys.stdin.read()  # Deliberately never execute embedded network code.
        if len(args) == 2:
            event("health", version=args[1])
            if args[1] != head_file.read_text().strip():
                fail("health checked a different checkout")
        elif len(args) == 1:
            event("frontend-check")
        else:
            fail("unexpected embedded Python arguments")
    elif args == ["deploy-step"]:
        app = local_path(os.environ["STROYKA_APP_ROOT"])
        local_path(os.environ["DEPLOY_LOCK_FILE"])
        event("deploy-step", readonly=os.environ.get("SMOKE_BUSINESS_READ_ONLY"),
              app=str(app), lock=os.environ["DEPLOY_LOCK_FILE"])
        (app / "build" / "asset-manifest.json").write_text('{"release":"after"}\n')
        if os.environ.get("FAKE_DEPLOY_WAIT") == "1":
            def terminated(_signum, _frame):
                event("child-terminated")
                sys.exit(143)
            signal.signal(signal.SIGTERM, terminated)
            (root / "child-started").write_text(str(os.getpid()))
            while True:
                signal.pause()
        sys.exit(int(os.environ.get("FAKE_DEPLOY_STATUS", "0")))
    elif args[:1] == ["restore-frontend"] and len(args) == 3:
        source = local_path(args[1])
        destination = local_path(args[2])
        event("restore-frontend", source=str(source), destination=str(destination))
        shutil.copy2(source / "asset-manifest.json", destination / "asset-manifest.json")
    else:
        fail("unexpected Python command " + repr(args))
else:
    fail("unknown command " + command)
'''


class DeploymentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="supply-deploy-test-")
        self.addCleanup(self.temp.cleanup)
        self.host = Path(self.temp.name).resolve()
        self.app = self.host / "app"
        self.bin = self.host / "bin"
        self.backups = self.host / "backups"
        for directory in (self.app / "build", self.app / "scripts", self.bin, self.backups):
            directory.mkdir(parents=True)
        self.manifest = self.app / "build" / "asset-manifest.json"
        self.manifest.write_text(ORIGINAL_FRONTEND)
        (self.host / "head").write_text(BEFORE)
        # These intentionally forbidden lines prove that the runner removes them.
        (self.app / "deploy.sh").write_text(
            "#!/usr/bin/env bash\nset -e\ngit reset --hard HEAD\n"
            "git pull --ff-only\npython3 deploy-step\n"
        )
        (self.app / "scripts" / "publish-frontend.sh").write_text(
            '#!/usr/bin/env bash\nset -e\npython3 restore-frontend "$1" "$2"\n'
        )
        fake = self.bin / "fake-command"
        fake.write_text("#!" + sys.executable + "\n" + FAKE_COMMAND)
        fake.chmod(0o700)
        for name in ("git", "systemctl", "nginx", "python3", "setsid", "flock"):
            (self.bin / name).symlink_to(fake)
        # No default PATH: an unanticipated curl, ssh, npm, or database command
        # fails instead of escaping the fake host. Only safe local tools remain.
        for name in ("bash", "cp", "grep", "sed", "mktemp", "sleep"):
            executable = shutil.which(name, path="/usr/bin:/bin")
            self.assertIsNotNone(executable, name)
            (self.bin / name).symlink_to(executable)
        source = RUNNER.read_text()
        locations = {
            "/var/www/stroyka-app": str(self.app),
            "/var/lock/stroyka-deploy.lock": str(self.host / "deploy.lock"),
            "/root/stroyka-supply-fix-XXXXXXXX": str(self.backups / "release-XXXXXXXX"),
        }
        for production, local in locations.items():
            self.assertIn(production, source)
            source = source.replace(production, local)
        for forbidden in ("/var/www/", "/var/lock/", "/root/"):
            self.assertNotIn(forbidden, source)
        self.runner = self.host / "runner.sh"
        self.runner.write_text(source)
        self.env = {
            "PATH": str(self.bin),
            "FAKE_HOST": str(self.host),
            "FAKE_BEFORE": BEFORE,
            "SUPPLY_RELEASE_COMMIT": TARGET,
        }

    def events(self):
        path = self.host / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_runner(self, **settings):
        return subprocess.run(
            ["/bin/bash", str(self.runner)], cwd=self.host,
            env={**self.env, **settings}, capture_output=True, text=True, timeout=20,
        )

    def assert_stopped_before_merge(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.host / "head").read_text(), BEFORE)
        self.assertEqual(self.manifest.read_text(), ORIGINAL_FRONTEND)
        self.assertFalse(any(event["command"] == "setsid" for event in self.events()))
        self.assertFalse(any(event["command"] == "git" and event["args"][:1] == ["merge"]
                             for event in self.events()))
        self.assertNotIn("SUPPLY_FIX_DEPLOYED", result.stdout)

    def test_target_mismatch_stops_before_merge(self):
        self.assert_stopped_before_merge(self.run_runner(FAKE_FETCH_HEAD="2" * 40))

    def test_unstaged_changes_stop_before_fetch_or_merge(self):
        self.assert_stopped_before_merge(self.run_runner(FAKE_DIRTY="unstaged"))
        self.assertFalse(any(event["args"][:1] == ["fetch"] for event in self.events()))

    def test_staged_changes_stop_before_fetch_or_merge(self):
        self.assert_stopped_before_merge(self.run_runner(FAKE_DIRTY="staged"))
        self.assertFalse(any(event["args"][:1] == ["fetch"] for event in self.events()))

    def test_lock_failure_stops_before_git_or_services(self):
        self.assert_stopped_before_merge(self.run_runner(FAKE_LOCK_FAILURE="1"))
        self.assertEqual([event["command"] for event in self.events()], ["flock"])

    def test_success_pins_release_and_runs_readonly_without_reset_or_pull(self):
        result = self.run_runner()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SUPPLY_FIX_DEPLOYED " + TARGET[:12], result.stdout)
        self.assertEqual((self.host / "head").read_text(), TARGET)
        events = self.events()
        deploy = next(event for event in events if event["command"] == "deploy-step")
        self.assertEqual(deploy["readonly"], "1")
        self.assertEqual(deploy["app"], str(self.app))
        self.assertTrue(Path(deploy["lock"]).is_relative_to(self.backups))
        self.assertEqual([event["version"] for event in events if event["command"] == "health"],
                         [BEFORE, TARGET])
        self.assertTrue(any(event["command"] == "frontend-check" for event in events))
        self.assertFalse(any(event["command"] == "git" and event["args"][0] in ("reset", "pull")
                             for event in events))
        self.assertFalse(any(event["command"] == "restore-frontend" for event in events))

    def test_deploy_failure_restores_previous_checkout_and_frontend(self):
        result = self.run_runner(FAKE_DEPLOY_STATUS="42")
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertIn("APPLICATION_ROLLED_BACK", result.stdout)
        self.assertNotIn("SUPPLY_FIX_DEPLOYED", result.stdout)
        self.assertEqual((self.host / "head").read_text(), BEFORE)
        self.assertEqual(self.manifest.read_text(), ORIGINAL_FRONTEND)
        events = self.events()
        switch = next(i for i, event in enumerate(events)
                      if event["command"] == "git" and event["args"] == ["switch", "--detach", BEFORE])
        restore = next(i for i, event in enumerate(events) if event["command"] == "restore-frontend")
        restart = next(i for i, event in enumerate(events)
                       if event["command"] == "systemctl" and event["args"] == ["restart", "stroyka"])
        self.assertLess(switch, restore)
        self.assertLess(restore, restart)
        self.assertEqual([event["version"] for event in events if event["command"] == "health"],
                         [BEFORE, BEFORE])

    def test_worker_rollback_failure_never_claims_successful_rollback(self):
        result = self.run_runner(FAKE_DEPLOY_STATUS="42", FAKE_WORKER_ROLLBACK_FAILURE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ROLLBACK_HEALTH_FAILED", result.stdout)
        self.assertNotIn("APPLICATION_ROLLED_BACK", result.stdout)
        self.assertNotIn("SUPPLY_FIX_DEPLOYED", result.stdout)
        self.assertEqual(self.manifest.read_text(), ORIGINAL_FRONTEND)

    def test_inactive_worker_is_not_started_during_rollback(self):
        result = self.run_runner(FAKE_DEPLOY_STATUS="42", FAKE_WORKER_ACTIVE="0")
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertIn("APPLICATION_ROLLED_BACK", result.stdout)
        self.assertFalse(any(event["command"] == "systemctl"
                             and event["args"] == ["restart", "stroyka-agent-job-worker.service"]
                             for event in self.events()))

    def test_term_stops_and_reaps_deployment_before_restoring_frontend(self):
        process = subprocess.Popen(
            ["/bin/bash", str(self.runner)], cwd=self.host,
            env={**self.env, "FAKE_DEPLOY_WAIT": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 10
            while not (self.host / "child-started").exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    self.fail("Fake deployment did not enter its wait state")
                time.sleep(0.02)
            child_pid = int((self.host / "deploy-pid").read_text())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 143, stdout + stderr)
            self.assertIn("APPLICATION_ROLLED_BACK", stdout)
            self.assertEqual(self.manifest.read_text(), ORIGINAL_FRONTEND)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
            commands = [event["command"] for event in self.events()]
            self.assertLess(commands.index("child-terminated"), commands.index("restore-frontend"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            pid_path = self.host / "deploy-pid"
            if pid_path.exists():
                try:
                    os.killpg(int(pid_path.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
