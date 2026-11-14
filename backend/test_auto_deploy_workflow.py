import importlib.util
import os
import stat
import subprocess
import time
import tempfile
import textwrap
import unittest
from pathlib import Path

from backend.features.runtime_version.service import app_version


ROOT = Path(__file__).resolve().parents[1]
OLD = "1111111111111111111111111111111111111111"
NEW = "2222222222222222222222222222222222222222"
OTHER = "3333333333333333333333333333333333333333"
KEY_MATERIAL = "SUPER-SECRET-KEY-MATERIAL"


def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEALTH = load_script("check-deploy-health.py")
CI = load_script("confirm-deploy-ci.py")


class HealthContractTests(unittest.TestCase):
    def test_expected_version_matches_backend_short_sha(self):
        sha = "abcdef1234567890abcdef1234567890abcdef12"
        self.assertEqual(HEALTH.expected_version(sha), app_version(ROOT, {"APP_VERSION": sha}))
        self.assertEqual(HEALTH.expected_version(sha), sha[:12])

    def test_only_boolean_ok_and_exact_short_version_pass(self):
        version = NEW[:12]
        self.assertTrue(HEALTH.release_is_healthy({"ok": True, "version": version}, version))
        self.assertFalse(HEALTH.release_is_healthy({"ok": "true", "version": version}, version))
        self.assertFalse(HEALTH.release_is_healthy({"ok": 1, "version": version}, version))
        self.assertFalse(HEALTH.release_is_healthy({"ok": True, "version": NEW}, version))
        self.assertFalse(HEALTH.release_is_healthy({"ok": True}, version))
        self.assertFalse(HEALTH.release_is_healthy([], version))

    def test_poll_retries_until_the_release_is_healthy(self):
        calls = {"count": 0}

        def fetch(_url, _timeout):
            calls["count"] += 1
            if calls["count"] < 3:
                return {"ok": False, "version": OLD[:12]}
            return {"ok": True, "version": NEW[:12]}

        ready, version, detail = HEALTH.poll_health(
            HEALTH.HEALTH_URL, NEW, attempts=4, delay=0, timeout=1,
            fetch=fetch, sleep=lambda _delay: None,
        )
        self.assertTrue(ready)
        self.assertEqual(version, NEW[:12])
        self.assertEqual(detail, "ok")
        self.assertEqual(calls["count"], 3)

    def test_poll_rejects_other_hosts_and_exhausted_retries(self):
        with self.assertRaises(ValueError):
            HEALTH.poll_health("http://stroyka26.pro/health", NEW, 1, 0, 1, fetch=lambda *_: {}, sleep=lambda *_: None)
        ready, version, detail = HEALTH.poll_health(
            HEALTH.HEALTH_URL, NEW, attempts=2, delay=0, timeout=1,
            fetch=lambda *_args: {"ok": True, "version": "mismatch"},
            sleep=lambda _delay: None,
        )
        self.assertFalse(ready)
        self.assertEqual(version, NEW[:12])
        self.assertIn("mismatch", detail)


class CiGateTests(unittest.TestCase):
    def test_newest_green_main_push_is_allowed(self):
        allowed, message = CI.deployment_allowed([
            {"databaseId": 2, "headSha": NEW, "headBranch": "main", "event": "push",
             "status": "completed", "conclusion": "success"},
            {"databaseId": 1, "headSha": NEW, "headBranch": "main", "event": "push",
             "status": "completed", "conclusion": "failure"},
        ], NEW)
        self.assertTrue(allowed)
        self.assertIn("успеш", message)

    def test_newer_failure_blocks_an_older_success(self):
        allowed, message = CI.deployment_allowed([
            {"databaseId": 1, "headSha": NEW, "headBranch": "main", "event": "push",
             "status": "completed", "conclusion": "success"},
            {"databaseId": 9, "headSha": NEW, "headBranch": "main", "event": "push",
             "status": "completed", "conclusion": "failure"},
        ], NEW)
        self.assertFalse(allowed)
        self.assertIn("не успешный", message)

    def test_pull_request_other_branch_and_in_progress_are_blocked(self):
        base = {"databaseId": 4, "headSha": NEW, "headBranch": "main", "event": "push",
                "status": "completed", "conclusion": "success"}
        for patch in (
            {"event": "pull_request"},
            {"headBranch": "feature"},
            {"status": "in_progress", "conclusion": ""},
        ):
            allowed, _message = CI.deployment_allowed([{**base, **patch}], NEW)
            self.assertFalse(allowed)

    def test_runs_for_another_commit_do_not_count(self):
        allowed, message = CI.deployment_allowed([
            {"databaseId": 3, "headSha": OTHER, "headBranch": "main", "event": "push",
             "status": "completed", "conclusion": "success"},
        ], NEW)
        self.assertFalse(allowed)
        self.assertIn("нет запуска", message)

    def test_cli_reads_a_json_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "runs.json"
            path.write_text("[]", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(ROOT / "scripts" / "confirm-deploy-ci.py"), str(path), NEW],
                check=False, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("нет запуска", result.stdout)


class WorkflowFileTests(unittest.TestCase):
    def test_deploy_waits_for_green_main_push_and_serializes(self):
        text = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn('workflows: ["CI"]', text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("conclusion == 'success'", text)
        self.assertIn("event == 'push'", text)
        self.assertIn("head_branch == 'main'", text)
        self.assertIn("head_repository.full_name == github.repository", text)
        self.assertIn("group: stroyka-production-deploy", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("github.event.workflow_run.head_sha", text)
        self.assertIn("refs/heads/main", text)
        self.assertNotIn("pull_request:", text)


class SshPreparationTests(unittest.TestCase):
    def script_env(self, temporary, **extra):
        runner = Path(temporary) / "runner"
        runner.mkdir()
        env = os.environ.copy()
        env.update({
            "GITHUB_ENV": str(Path(temporary) / "github.env"),
            "RUNNER_TEMP": str(runner),
            "DEPLOY_HOST": "server.example",
            "DEPLOY_USER": "deploy",
            "DEPLOY_PORT": "22",
            "DEPLOY_SSH_KEY": "-----BEGIN OPENSSH PRIVATE KEY-----\n%s\n-----END OPENSSH PRIVATE KEY-----\n" % KEY_MATERIAL,
            "DEPLOY_KNOWN_HOSTS": "",
        })
        env.update(extra)
        Path(env["GITHUB_ENV"]).write_text("", encoding="utf-8")
        return env

    def run_prepare(self, env, path_dir=None):
        if path_dir is not None:
            env["PATH"] = str(path_dir) + os.pathsep + env["PATH"]
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / "prepare-deploy-ssh.sh")],
            check=False, capture_output=True, text=True, env=env,
        )

    def test_known_hosts_secret_is_used_and_key_is_not_printed(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = self.script_env(temporary, DEPLOY_KNOWN_HOSTS="pinned-host-key")
            keyscan = Path(temporary) / "ssh-keyscan"
            keyscan.write_text("#!/bin/bash\nexit 97\n", encoding="utf-8")
            keyscan.chmod(0o755)
            result = self.run_prepare(env, path_dir=Path(temporary))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(KEY_MATERIAL, result.stdout)
            self.assertNotIn(KEY_MATERIAL, result.stderr)
            self.assertNotIn("server.example", result.stdout)
            saved = Path(env["GITHUB_ENV"]).read_text(encoding="utf-8")
            values = dict(line.split("=", 1) for line in saved.splitlines())
            key_path = Path(values["SSH_KEY"])
            known_path = Path(values["SSH_KNOWN_HOSTS"])
            self.assertEqual(stat.S_IMODE(key_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(known_path.stat().st_mode), 0o600)
            self.assertIn(KEY_MATERIAL, key_path.read_text(encoding="utf-8"))
            self.assertEqual(known_path.read_text(encoding="utf-8").strip(), "pinned-host-key")
            subprocess.run(
                ["bash", str(ROOT / "scripts" / "cleanup-deploy-ssh.sh")],
                check=True, env={**env, "SSH_KEY": values["SSH_KEY"], "SSH_KNOWN_HOSTS": values["SSH_KNOWN_HOSTS"]},
            )
            self.assertFalse(key_path.exists())
            self.assertFalse(known_path.exists())

    def test_keyscan_is_fallback_and_its_output_stays_out_of_the_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = self.script_env(temporary)
            keyscan = Path(temporary) / "ssh-keyscan"
            keyscan.write_text(textwrap.dedent("""\
                #!/bin/bash
                printf 'ssh-ed25519 AAAATEST\\n'
                echo "leaked-$4" >&2
            """), encoding="utf-8")
            keyscan.chmod(0o755)
            result = self.run_prepare(env, path_dir=Path(temporary))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("server.example", result.stdout)
            self.assertNotIn("leaked-", result.stdout)
            self.assertNotIn("leaked-", result.stderr)
            self.assertNotIn(KEY_MATERIAL, result.stdout + result.stderr)
            self.assertIn("ssh-keyscan", result.stdout)

    def test_missing_secret_names_the_secret_without_echoing_the_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = self.script_env(temporary, DEPLOY_HOST="")
            result = self.run_prepare(env)
            self.assertEqual(result.returncode, 1)
            self.assertIn("DEPLOY_HOST", result.stderr)
            self.assertNotIn(KEY_MATERIAL, result.stdout + result.stderr)


class RemoteDeployTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.repo = root / "app"
        self.repo.mkdir()
        self.git_root = root / "gitstate"
        self.git_root.mkdir()
        self.log = root / "deploy-log"
        self.fail_flag = root / "fail"
        self.git_log = self.git_root / "LOG"
        (self.git_root / "HEAD").write_text(OLD + "\n", encoding="utf-8")
        (self.git_root / "BRANCH").write_text("main\n", encoding="utf-8")
        (self.git_root / "KNOWN").write_text(OLD + " " + NEW + "\n", encoding="utf-8")
        fake_git = root / "git"
        fake_git.write_text(textwrap.dedent(r"""
            #!/usr/bin/env python3
            import os, sys
            root = os.environ["FAKE_GIT_ROOT"]
            head, branch, known, log = [os.path.join(root, name) for name in ("HEAD", "BRANCH", "KNOWN", "LOG")]
            args = sys.argv[1:]
            with open(log, "a", encoding="utf-8") as handle:
                handle.write(" ".join(args) + "\n")
            def read(path):
                return open(path, encoding="utf-8").read().strip()
            def write(path, value):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(value + "\n")
            known_items = read(known).split()
            if args == ["rev-parse", "HEAD"]:
                print(read(head)); sys.exit(0)
            if args == ["rev-parse", "--short", "HEAD"]:
                print(read(head)[:12]); sys.exit(0)
            if args[:2] == ["fetch", "origin"] and len(args) == 3:
                sys.exit(0 if args[2] == "main" or args[2] in known_items else 1)
            if args[:2] == ["cat-file", "-e"] and len(args) == 3:
                sys.exit(0 if args[2].split("^", 1)[0] in known_items else 1)
            if args[:2] == ["merge-base", "--is-ancestor"] and len(args) == 4:
                left, right = args[2], args[3]
                if right == "HEAD":
                    right = read(head)
                if left not in known_items or right not in known_items:
                    sys.exit(1)
                sys.exit(0 if known_items.index(left) <= known_items.index(right) else 1)
            if args == ["symbolic-ref", "-q", "HEAD"]:
                name = read(branch)
                if not name:
                    sys.exit(1)
                print("refs/heads/" + name); sys.exit(0)
            if args[:2] == ["reset", "--hard"] and len(args) == 3:
                sha = read(head) if args[2] == "HEAD" else args[2]
                if sha not in known_items:
                    sys.exit(1)
                write(head, sha); sys.exit(0)
            if args[:3] == ["checkout", "-B", "main"] and len(args) == 4:
                if args[3] not in known_items:
                    sys.exit(1)
                write(head, args[3]); write(branch, "main"); sys.exit(0)
            if args and args[0] == "pull":
                write(head, os.environ["FAKE_PULL_TARGET"])
                sys.exit(0)
            sys.stderr.write("unexpected git %s\n" % args)
            sys.exit(99)
        """).strip() + "\n", encoding="utf-8")
        fake_git.chmod(0o755)
        stub = self.repo / "deploy.sh"
        self.lock_file = root / "deploy.lock"
        stub.write_text(textwrap.dedent("""\
            #!/bin/bash
            set -euo pipefail
            exec 9>"$DEPLOY_LOCK_FILE"
            if ! flock -n 9; then
              echo "deploy.sh не получил блокировку" >&2
              exit 1
            fi
            echo "deploy $(git rev-parse HEAD)" >> "$STROYKA_TEST_LOG"
            git reset --hard HEAD
            git pull --ff-only
            if [[ -n "${STROYKA_FAIL_FLAG:-}" && -f "$STROYKA_FAIL_FLAG" ]]; then
              rm -f "$STROYKA_FAIL_FLAG"
              exit 9
            fi
        """), encoding="utf-8")
        stub.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(root) + os.pathsep + self.env["PATH"],
            "FAKE_GIT_ROOT": str(self.git_root),
            "FAKE_PULL_TARGET": OTHER,
            "STROYKA_APP_ROOT": str(self.repo),
            "STROYKA_DEPLOY_SCRIPT": str(stub),
            "STROYKA_TEST_LOG": str(self.log),
            "STROYKA_FAIL_FLAG": str(self.fail_flag),
            "DEPLOY_LOCK_FILE": str(self.lock_file),
        })

    def head(self):
        return (self.git_root / "HEAD").read_text(encoding="utf-8").strip()

    def deploys(self):
        if not self.log.exists():
            return []
        return [line.split()[1] for line in self.log.read_text(encoding="utf-8").splitlines()]

    def git_commands(self):
        if not self.git_log.exists():
            return []
        return self.git_log.read_text(encoding="utf-8").splitlines()

    def run_remote(self, *args):
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / "auto-deploy-remote.sh"), *args],
            check=False, capture_output=True, text=True, env=self.env,
        )

    def test_success_stays_on_the_exact_commit_and_does_not_pull_forward(self):
        result = self.run_remote(NEW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(), NEW)
        self.assertEqual(self.deploys(), [NEW])
        self.assertIn("git pull пропущен", result.stdout)
        self.assertNotIn("pull --ff-only", "\n".join(self.git_commands()))
        self.assertIn("reset --hard HEAD", self.git_commands())
        self.assertIn("STROYKA_ROLLBACK_SHA=%s" % OLD, result.stdout)

    def test_deploy_failure_rolls_back_and_turns_red(self):
        self.fail_flag.write_text("1", encoding="utf-8")
        result = self.run_remote(NEW)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [NEW, OLD])
        self.assertIn("Откат выполнен: %s" % OLD, result.stderr)
        self.assertNotIn("pull --ff-only", "\n".join(self.git_commands()))

    def test_failure_before_switch_does_not_rerun_deploy(self):
        (self.git_root / "KNOWN").write_text(OLD + "\n", encoding="utf-8")
        result = self.run_remote(NEW)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [])
        self.assertIn("остался на %s" % OLD, result.stderr)

    def test_apply_only_failure_does_not_roll_forward(self):
        (self.git_root / "HEAD").write_text(NEW + "\n", encoding="utf-8")
        self.fail_flag.write_text("1", encoding="utf-8")
        result = self.run_remote("--apply-only", OLD)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [OLD])
        self.assertNotIn("Откат выполнен", result.stderr)

    def test_older_commit_does_not_replace_a_newer_server(self):
        (self.git_root / "HEAD").write_text(NEW + "\n", encoding="utf-8")
        result = self.run_remote(OLD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.head(), NEW)
        self.assertEqual(self.deploys(), [])
        self.assertIn("STROYKA_SKIP=newer", result.stdout)

    def test_busy_lock_does_not_change_the_checkout(self):
        self.env["STROYKA_LOCK_WAIT"] = "0"
        holder = subprocess.Popen(
            ["flock", str(self.lock_file), "sleep", "30"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        def stop_holder():
            if holder.poll() is None:
                holder.kill()
                holder.wait()

        self.addCleanup(stop_holder)
        deadline = time.time() + 5
        while time.time() < deadline:
            probe = subprocess.run(
                ["flock", "-n", str(self.lock_file), "true"],
                check=False, capture_output=True,
            )
            if probe.returncode != 0:
                break
            time.sleep(0.05)
        else:
            self.fail("lock was not acquired")
        result = self.run_remote(NEW)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [])
        self.assertIn("Сервер не менялся", result.stderr)

    def test_bad_sha_is_rejected(self):
        result = self.run_remote("not-a-sha")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [])


class RunnerWrapperTests(unittest.TestCase):
    def test_wrapper_records_status_and_apply_only_returns_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_ssh = root / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/bash
                cat >/dev/null
                echo "STROYKA_ROLLBACK_SHA=%s"
                exit "${FAKE_SSH_STATUS:-0}"
            """ % OLD), encoding="utf-8")
            fake_ssh.chmod(0o755)
            key = root / "key"
            known = root / "known"
            key.write_text("key", encoding="utf-8")
            known.write_text("known", encoding="utf-8")
            output = root / "output"
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env["PATH"],
                "SSH_KEY": str(key),
                "SSH_KNOWN_HOSTS": str(known),
                "SSH_PORT": "22",
                "SSH_USER": "deploy",
                "SSH_HOST": "server.example",
                "GITHUB_OUTPUT": str(output),
                "TARGET_SHA": NEW,
                "FAKE_SSH_STATUS": "7",
            })
            failed = subprocess.run(
                ["bash", str(ROOT / "scripts" / "run-remote-deploy.sh")],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(failed.returncode, 0, failed.stderr)
            recorded = output.read_text(encoding="utf-8")
            self.assertIn("deploy_status=7", recorded)
            self.assertIn("rollback_sha=%s" % OLD, recorded)
            apply_only = subprocess.run(
                ["bash", str(ROOT / "scripts" / "run-remote-deploy.sh"), "--apply-only", OLD],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(apply_only.returncode, 7)

    def test_newer_server_is_recorded_as_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_ssh = root / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/bash
                cat >/dev/null
                echo "STROYKA_ROLLBACK_SHA=%s"
                echo "STROYKA_SKIP=newer"
            """ % NEW), encoding="utf-8")
            fake_ssh.chmod(0o755)
            key = root / "key"
            known = root / "known"
            key.write_text("key", encoding="utf-8")
            known.write_text("known", encoding="utf-8")
            output = root / "output"
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env["PATH"],
                "SSH_KEY": str(key),
                "SSH_KNOWN_HOSTS": str(known),
                "SSH_PORT": "22",
                "SSH_USER": "deploy",
                "SSH_HOST": "server.example",
                "GITHUB_OUTPUT": str(output),
                "TARGET_SHA": OLD,
            })
            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "run-remote-deploy.sh")],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("deploy_status=skipped", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
