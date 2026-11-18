import fcntl
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD = "1111111111111111111111111111111111111111"
NEW = "2222222222222222222222222222222222222222"
OTHER = "3333333333333333333333333333333333333333"
TOKEN = "ghp_PullDeploySecretValue123"
REPO = "acme/stroyka"


def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".", "_").replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CI = load_script("pull-deploy-ci.py")


def workflow(sha, status="completed", conclusion="success", event="push", branch="main",
             run_id=10, name="CI", path=".github/workflows/ci.yml"):
    return {
        "id": run_id,
        "name": name,
        "path": path,
        "head_sha": sha,
        "head_branch": branch,
        "event": event,
        "status": status,
        "conclusion": conclusion,
    }


class CiDecisionTests(unittest.TestCase):
    def test_newest_green_main_push_is_allowed(self):
        state, message = CI.classify_ci({
            "workflow_runs": [
                workflow(NEW, conclusion="failure", run_id=1),
                workflow(NEW, conclusion="success", run_id=4),
            ],
        }, NEW)
        self.assertEqual(state, "green")
        self.assertIn("успеш", message)

    def test_newer_failure_or_cancelled_blocks_an_older_success(self):
        for conclusion in ("failure", "cancelled", "timed_out"):
            state, message = CI.classify_ci({
                "workflow_runs": [
                    workflow(NEW, conclusion="success", run_id=2),
                    workflow(NEW, conclusion=conclusion, run_id=9),
                ],
            }, NEW)
            self.assertEqual(state, "failed", conclusion)
            self.assertIn("пропускаю", message)

    def test_in_progress_rerun_waits_even_after_an_older_success(self):
        state, message = CI.classify_ci({
            "workflow_runs": [
                workflow(NEW, conclusion="success", run_id=2),
                workflow(NEW, status="in_progress", conclusion=None, run_id=8),
            ],
        }, NEW)
        self.assertEqual(state, "pending")
        self.assertIn("выполня", message)

    def test_missing_push_run_is_pending(self):
        for runs in (
            [],
            [workflow(NEW, event="pull_request")],
            [workflow(NEW, branch="feature")],
            [workflow(OTHER)],
            [workflow(NEW, name="Other", path=".github/workflows/other.yml")],
            [workflow(NEW, name="CI", path=".github/workflows/other.yml@main")],
        ):
            state, _message = CI.classify_ci({"workflow_runs": runs}, NEW)
            self.assertEqual(state, "pending")

    def test_display_name_can_change_when_the_file_is_still_ci(self):
        state, _message = CI.classify_ci({
            "workflow_runs": [workflow(NEW, name="Build and test")],
        }, NEW)
        self.assertEqual(state, "green")

    def test_workflow_path_ref_suffix_still_matches_ci(self):
        for path in (
            ".github/workflows/ci.yml@main",
            ".github/workflows/ci.yml@refs/heads/main",
            "ci.yml@main",
        ):
            state, message = CI.classify_ci({
                "workflow_runs": [workflow(NEW, name="Build and test", path=path)],
            }, NEW)
            self.assertEqual(state, "green", path)
            self.assertIn("успеш", message)

    def test_bad_payload_is_an_error(self):
        for payload in (None, [], {"message": "nope"}, {"workflow_runs": "no"}):
            state, _message = CI.classify_ci(payload, NEW)
            self.assertEqual(state, "error")
        state, _message = CI.classify_ci({"workflow_runs": []}, "not-a-sha")
        self.assertEqual(state, "error")

    def test_cli_exit_codes(self):
        with tempfile_json({"workflow_runs": []}) as path:
            pending = run_ci(path, NEW)
            self.assertEqual(pending.returncode, 10)
        with tempfile_json({"workflow_runs": [workflow(NEW, conclusion="failure")]}) as path:
            failed = run_ci(path, NEW)
            self.assertEqual(failed.returncode, 11)
            self.assertIn("пропускаю", failed.stdout)


class RepoAndTokenTests(unittest.TestCase):
    def test_repo_is_parsed_without_keeping_a_token_from_the_url(self):
        secret = "supersecret-from-url"
        cases = (
            "https://github.com/acme/stroyka.git",
            "https://github.com/acme/stroyka/",
            "git@github.com:acme/stroyka.git",
            "ssh://git@github.com/acme/stroyka.git",
            "https://user:%s@github.com/acme/stroyka.git" % secret,
        )
        for url in cases:
            repo = CI.parse_github_repo(url)
            self.assertEqual(repo, "acme/stroyka")
            self.assertNotIn(secret, repo)
        self.assertEqual(CI.parse_github_repo("https://gitlab.com/acme/stroyka.git"), "")

    def test_token_file_permissions(self):
        self.assertEqual(CI.token_file_decision(0o644, 0, 0), "open")
        self.assertEqual(CI.token_file_decision(0o640, 0, 0), "open")
        self.assertEqual(CI.token_file_decision(0o600, 1000, 0), "owner")
        self.assertEqual(CI.token_file_decision(0o600, 0, 1000), "owner")
        self.assertEqual(CI.token_file_decision(0o600, 1000, 1000), "ok")

    def test_cli_writes_curl_config_without_printing_the_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token_file = root / "token.env"
            token_file.write_text('GITHUB_TOKEN="%s"\n' % TOKEN, encoding="utf-8")
            token_file.chmod(0o600)
            dest = root / "curl.cfg"
            env = os.environ.copy()
            env.pop("GITHUB_TOKEN", None)
            result = subprocess.run(
                ["python3", str(ROOT / "scripts" / "pull-deploy-ci.py"),
                 "--curl-config", str(dest), str(token_file)],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "ready")
            self.assertNotIn(TOKEN, result.stdout + result.stderr)
            self.assertIn("Authorization: Bearer %s" % TOKEN, dest.read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode) & 0o077, 0)

            token_file.chmod(0o644)
            opened = subprocess.run(
                ["python3", str(ROOT / "scripts" / "pull-deploy-ci.py"),
                 "--curl-config", str(dest), str(token_file)],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(opened.stdout.strip(), "open")
            self.assertNotIn(TOKEN, opened.stdout + opened.stderr)


class tempfile_json:
    def __init__(self, payload):
        self.payload = payload
        self.directory = None

    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "ci.json"
        path.write_text(json.dumps(self.payload), encoding="utf-8")
        return path

    def __exit__(self, *_args):
        self.directory.cleanup()


def run_ci(path, sha):
    return subprocess.run(
        ["python3", str(ROOT / "scripts" / "pull-deploy-ci.py"), sha, str(path)],
        check=False, capture_output=True, text=True,
    )


FAKE_GIT = r"""
#!/usr/bin/env python3
import os, sys
root = os.environ["FAKE_GIT_ROOT"]
head, origin, branch, known, log = [
    os.path.join(root, name) for name in ("HEAD", "ORIGIN", "BRANCH", "KNOWN", "LOG")
]
args = sys.argv[1:]
with open(log, "a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\n")

def read(path):
    return open(path, encoding="utf-8").read().strip()

def write(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(value + "\n")

known_items = read(known).split()
safe = os.path.join(root, "SAFE")
if args == ["config", "--global", "--get-all", "safe.directory"]:
    if not os.path.exists(safe) or not open(safe, encoding="utf-8").read().strip():
        sys.exit(1)
    sys.stdout.write(open(safe, encoding="utf-8").read())
    sys.exit(0)
if args[:4] == ["config", "--global", "--add", "safe.directory"] and len(args) == 5:
    with open(safe, "a", encoding="utf-8") as handle:
        handle.write(args[4] + "\n")
    sys.exit(0)
if args == ["rev-parse", "HEAD"]:
    print(read(head)); sys.exit(0)
if args == ["rev-parse", "--short", "HEAD"]:
    print(read(head)[:12]); sys.exit(0)
if args == ["rev-parse", "origin/main"]:
    print(read(origin)); sys.exit(0)
if args in (["fetch", "origin", "main"], ["fetch", "--quiet", "origin", "main"]):
    sys.exit(0)
if args == ["remote", "get-url", "origin"]:
    print(os.environ.get("FAKE_REMOTE_URL", "https://github.com/acme/stroyka.git"))
    sys.exit(0)
if args[:2] == ["cat-file", "-e"] and len(args) == 3:
    sys.exit(0 if args[2].split("^", 1)[0] in known_items else 1)
if args[:2] == ["merge-base", "--is-ancestor"] and len(args) == 4:
    left, right = args[2], args[3]
    if right == "HEAD":
        right = read(head)
    if left == "HEAD":
        left = read(head)
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
    write(head, os.environ.get("FAKE_PULL_TARGET", "bad"))
    sys.exit(0)
sys.stderr.write("unexpected git %s\n" % args)
sys.exit(99)
"""


FAKE_CURL = r"""
#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
token = os.environ.get("PULL_DEPLOY_TOKEN", "")
log_path = os.environ["CURL_LOG"]
if token and token in "\n".join(args):
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write("ARG_LEAK\n")
    sys.exit(3)
note = ""
if "--config" in args:
    config = open(args[args.index("--config") + 1], encoding="utf-8").read()
    if token and ("Authorization: Bearer %s" % token) in config:
        note = "CONFIG_OK\n"
    else:
        note = "CONFIG_BAD\n"
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write("\n".join(args) + "\n" + note + "---\n")
output = None
if "-o" in args:
    output = args[args.index("-o") + 1]
fixture = os.environ.get("CURL_FIXTURE", "")
if output and fixture:
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(open(fixture, encoding="utf-8").read())
code = os.environ.get("CURL_HTTP", "200")
sys.stdout.write(code)
sys.exit(0 if code == "200" else 22)
"""


class PullDeployScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.root = root
        self.repo = root / "app"
        self.repo.mkdir()
        self.git_root = root / "gitstate"
        self.git_root.mkdir()
        (self.git_root / "HEAD").write_text(OLD + "\n", encoding="utf-8")
        (self.git_root / "ORIGIN").write_text(NEW + "\n", encoding="utf-8")
        (self.git_root / "BRANCH").write_text("main\n", encoding="utf-8")
        (self.git_root / "KNOWN").write_text(" ".join((OLD, NEW, OTHER)) + "\n", encoding="utf-8")
        (self.git_root / "LOG").write_text("", encoding="utf-8")
        fake_git = root / "git"
        fake_git.write_text(FAKE_GIT.strip() + "\n", encoding="utf-8")
        fake_git.chmod(0o755)
        fake_curl = root / "curl"
        fake_curl.write_text(FAKE_CURL.strip() + "\n", encoding="utf-8")
        fake_curl.chmod(0o755)
        self.health = root / "health"
        self.health.write_text(textwrap.dedent("""\
            #!/bin/bash
            printf '%s\\n' "$1" >> "$HEALTH_LOG"
            if [[ -f "$HEALTH_FAIL_FILE" ]] && grep -qx "$1" "$HEALTH_FAIL_FILE"; then
              exit 1
            fi
            exit 0
        """), encoding="utf-8")
        self.health.chmod(0o755)
        self.deploy_log = root / "deploy-log"
        self.fail_flag = root / "fail"
        self.health_log = root / "health-log"
        self.health_fail = root / "health-fail"
        self.curl_log = root / "curl-log"
        self.curl_fixture = root / "ci.json"
        self.lock_file = root / "deploy.lock"
        self.state = root / "state"
        self.state.mkdir(mode=0o700)
        stub = root / "deploy.sh"
        stub.write_text(textwrap.dedent("""\
            #!/bin/bash
            set -euo pipefail
            if [[ -n "${GITHUB_TOKEN:-}" ]]; then
              echo "TOKEN_VISIBLE_TO_DEPLOY" >&2
              exit 1
            fi
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
        self.env.pop("GITHUB_TOKEN", None)
        self.env.update({
            "PATH": str(root) + os.pathsep + self.env["PATH"],
            "FAKE_GIT_ROOT": str(self.git_root),
            "FAKE_PULL_TARGET": OTHER,
            "STROYKA_APP_ROOT": str(self.repo),
            "STROYKA_DEPLOY_SCRIPT": str(stub),
            "STROYKA_TEST_LOG": str(self.deploy_log),
            "STROYKA_FAIL_FLAG": str(self.fail_flag),
            "DEPLOY_LOCK_FILE": str(self.lock_file),
            "STROYKA_DEPLOY_STATE_DIR": str(self.state),
            "STROYKA_GITHUB_REPO": REPO,
            "STROYKA_HEALTH_CHECK": str(self.health),
            "HEALTH_LOG": str(self.health_log),
            "HEALTH_FAIL_FILE": str(self.health_fail),
            "CURL_LOG": str(self.curl_log),
            "CURL_FIXTURE": str(self.curl_fixture),
            "PULL_DEPLOY_TOKEN": TOKEN,
            "STROYKA_GITHUB_TOKEN_FILE": str(root / "missing-token.env"),
        })
        self.write_ci(NEW)

    def write_ci(self, sha, **kwargs):
        self.curl_fixture.write_text(
            json.dumps({"workflow_runs": [workflow(sha, **kwargs)]}),
            encoding="utf-8",
        )

    def run_script(self):
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / "pull-deploy.sh")],
            check=False, capture_output=True, text=True, env=self.env,
        )

    def head(self):
        return (self.git_root / "HEAD").read_text(encoding="utf-8").strip()

    def deploys(self):
        if not self.deploy_log.exists():
            return []
        return [line.split()[1] for line in self.deploy_log.read_text(encoding="utf-8").splitlines()]

    def git_commands(self):
        return (self.git_root / "LOG").read_text(encoding="utf-8").splitlines()

    def curl_calls(self):
        if not self.curl_log.exists():
            return 0
        return self.curl_log.read_text(encoding="utf-8").count("---\n")

    def failed_sha(self):
        path = self.state / "failed-sha"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def test_other_checkout_is_trusted_once_and_only_that_directory(self):
        (self.git_root / "ORIGIN").write_text(OLD + "\n", encoding="utf-8")
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout, "")
        recorded = (self.git_root / "SAFE").read_text(encoding="utf-8").splitlines()
        self.assertEqual(recorded, [str(self.repo)])
        self.assertNotIn("*", recorded)
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual((self.git_root / "SAFE").read_text(encoding="utf-8").splitlines(), [str(self.repo)])

    def test_unchanged_commit_is_quiet_and_does_not_call_github(self):
        (self.git_root / "ORIGIN").write_text(OLD + "\n", encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.curl_calls(), 0)
        self.assertEqual(self.deploys(), [])
        self.assertEqual(self.head(), OLD)

    def test_busy_lock_is_quiet(self):
        fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_script()
        finally:
            os.close(fd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.curl_calls(), 0)
        self.assertEqual(self.deploys(), [])
        self.assertEqual(self.head(), OLD)

    def test_pending_ci_waits_and_is_checked_again(self):
        self.write_ci(NEW, status="in_progress", conclusion=None)
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("выполня", first.stdout)
        self.assertEqual(self.deploys(), [])
        self.assertEqual(self.failed_sha(), "")
        self.assertEqual(self.head(), OLD)
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.curl_calls(), 2)

    def test_failed_ci_is_remembered_and_not_polled_again(self):
        self.write_ci(NEW, conclusion="failure")
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("пропускаю", first.stdout)
        self.assertEqual(self.failed_sha(), NEW)
        self.assertEqual(self.deploys(), [])
        self.assertEqual(self.curl_calls(), 1)
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, "")
        self.assertEqual(self.curl_calls(), 1)

    def test_green_commit_deploys_once_and_health_checks_it(self):
        self.env["GITHUB_TOKEN"] = TOKEN
        result = self.run_script()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertEqual(self.head(), NEW)
        self.assertEqual(self.deploys(), [NEW])
        self.assertEqual(self.health_log.read_text(encoding="utf-8").splitlines(), [NEW])
        self.assertIn("Выложено: %s" % NEW, result.stdout)
        self.assertNotIn(TOKEN, combined)
        self.assertNotIn("TOKEN_VISIBLE_TO_DEPLOY", combined)
        self.assertNotIn("ARG_LEAK", self.curl_log.read_text(encoding="utf-8"))
        self.assertIn("CONFIG_OK", self.curl_log.read_text(encoding="utf-8"))
        self.assertEqual(self.curl_calls(), 1)
        self.assertIn("repos/%s/actions/workflows/ci.yml/runs?head_sha=%s" % (REPO, NEW),
                      self.curl_log.read_text(encoding="utf-8"))
        self.assertNotIn("pull --ff-only", "\n".join(self.git_commands()))
        self.assertEqual(self.failed_sha(), "")

    def test_health_failure_rolls_back_and_remembers_the_sha(self):
        self.health_fail.write_text(NEW + "\n", encoding="utf-8")
        result = self.run_script()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, combined)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [NEW, OLD])
        self.assertEqual(self.health_log.read_text(encoding="utf-8").splitlines(), [NEW, OLD])
        self.assertEqual(self.failed_sha(), NEW)
        self.assertIn("Возвращаю", result.stderr)

    def test_deploy_failure_rolls_back_and_checks_the_previous_health(self):
        self.fail_flag.write_text("1", encoding="utf-8")
        result = self.run_script()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, combined)
        self.assertEqual(self.head(), OLD)
        self.assertEqual(self.deploys(), [NEW, OLD])
        self.assertEqual(self.health_log.read_text(encoding="utf-8").splitlines(), [OLD])
        self.assertEqual(self.failed_sha(), NEW)
        self.assertNotIn("pull --ff-only", "\n".join(self.git_commands()))

    def test_a_later_commit_is_not_blocked_by_an_older_failure(self):
        (self.state / "failed-sha").write_text(NEW + "\n", encoding="utf-8")
        (self.git_root / "ORIGIN").write_text(OTHER + "\n", encoding="utf-8")
        self.write_ci(OTHER)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.head(), OTHER)
        self.assertEqual(self.deploys(), [OTHER])

    def test_origin_that_is_not_a_fast_forward_is_not_installed(self):
        (self.git_root / "KNOWN").write_text(" ".join((NEW, OLD, OTHER)) + "\n", encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("не продолжает", result.stdout)
        self.assertEqual(self.deploys(), [])
        self.assertEqual(self.curl_calls(), 0)
        self.assertEqual(self.head(), OLD)

    def test_github_outage_does_not_mark_the_commit_failed(self):
        self.env["CURL_HTTP"] = "503"
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("недоступен", result.stdout)
        self.assertEqual(self.failed_sha(), "")
        self.assertEqual(self.deploys(), [])

    def test_world_readable_token_file_is_ignored(self):
        token_file = self.root / "token.env"
        token_file.write_text("GITHUB_TOKEN=%s\n" % TOKEN, encoding="utf-8")
        token_file.chmod(0o644)
        self.env["STROYKA_GITHUB_TOKEN_FILE"] = str(token_file)
        result = self.run_script()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("не только владельцу", result.stdout)
        self.assertNotIn(TOKEN, combined)
        self.assertNotIn("CONFIG_OK", self.curl_log.read_text(encoding="utf-8"))
        self.assertEqual(self.deploys(), [NEW])

    def test_private_token_file_is_used_and_not_logged(self):
        token_file = self.root / "token.env"
        token_file.write_text("GITHUB_TOKEN=%s\n" % TOKEN, encoding="utf-8")
        token_file.chmod(0o600)
        self.env["STROYKA_GITHUB_TOKEN_FILE"] = str(token_file)
        result = self.run_script()
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertNotIn(TOKEN, combined)
        self.assertIn("CONFIG_OK", self.curl_log.read_text(encoding="utf-8"))
        self.assertNotIn("ARG_LEAK", self.curl_log.read_text(encoding="utf-8"))

    def test_repo_from_origin_drops_credentials(self):
        secret = "origin-url-secret"
        del self.env["STROYKA_GITHUB_REPO"]
        self.env["FAKE_REMOTE_URL"] = "https://git:%s@github.com/acme/stroyka.git" % secret
        result = self.run_script()
        combined = result.stdout + result.stderr + self.curl_log.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, combined)
        self.assertIn("repos/acme/stroyka/", combined)


class UnitAndInstallerTests(unittest.TestCase):
    def test_systemd_units_exist_and_poll_every_five_minutes(self):
        service = (ROOT / "deploy" / "systemd" / "stroyka-pull-deploy.service").read_text(encoding="utf-8")
        timer = (ROOT / "deploy" / "systemd" / "stroyka-pull-deploy.timer").read_text(encoding="utf-8")
        self.assertIn("Type=oneshot", service)
        self.assertIn("User=root", service)
        self.assertIn("WorkingDirectory=/var/www/stroyka-app", service)
        self.assertIn("ExecStart=/bin/bash /var/www/stroyka-app/scripts/pull-deploy.sh", service)
        self.assertIn("TimeoutStartSec=60min", service)
        self.assertIn("OnCalendar=*:0/5", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("RandomizedDelaySec=30", timer)
        self.assertIn("WantedBy=timers.target", timer)
        analyze = shutil.which("systemd-analyze")
        if analyze is None:
            self.skipTest("systemd-analyze is not installed")
        verified = subprocess.run(
            [
                analyze, "verify",
                str(ROOT / "deploy" / "systemd" / "stroyka-pull-deploy.service"),
                str(ROOT / "deploy" / "systemd" / "stroyka-pull-deploy.timer"),
            ],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)

    def test_scripts_pass_shellcheck(self):
        shellcheck = shutil.which("shellcheck")
        if shellcheck is None:
            self.skipTest("shellcheck is not installed")
        result = subprocess.run(
            [
                shellcheck,
                str(ROOT / "scripts" / "pull-deploy.sh"),
                str(ROOT / "scripts" / "install-pull-deploy.sh"),
            ],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_installer_refuses_a_normal_user_and_is_idempotent_in_a_prefix(self):
        script = str(ROOT / "scripts" / "install-pull-deploy.sh")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "systemctl.log"
            fake_id = root / "id"
            # Always report a normal user, even if this test itself is root.
            # Otherwise the refusal check would install the real timer.
            fake_id.write_text(
                "#!/bin/bash\nif [[ \"${1:-}\" == \"-u\" ]]; then printf '1000\\n'; exit 0; fi\nexit 1\n",
                encoding="utf-8",
            )
            fake_id.chmod(0o755)
            fake = root / "systemctl"
            fake.write_text(
                "#!/bin/bash\nprintf '%s\\n' \"$*\" >> \"$SYSTEMCTL_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            gitconfig = root / "gitconfig"
            app_root = root / "app-root"
            app_root.mkdir()
            env = os.environ.copy()
            env.pop("STROYKA_INSTALL_PREFIX", None)
            env.update({
                "PATH": str(root) + os.pathsep + env["PATH"],
                "SYSTEMCTL_LOG": str(log),
                "STROYKA_GIT_CONFIG_GLOBAL": str(gitconfig),
                "STROYKA_APP_ROOT": str(app_root),
            })
            refused = subprocess.run(
                ["bash", script],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertIn("root", refused.stderr)
            self.assertFalse(log.exists())

            env["STROYKA_INSTALL_PREFIX"] = str(root / "prefix")
            first = subprocess.run(["bash", script], check=False, capture_output=True, text=True, env=env)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            unit_dir = root / "prefix" / "etc" / "systemd" / "system"
            service = unit_dir / "stroyka-pull-deploy.service"
            timer = unit_dir / "stroyka-pull-deploy.timer"
            state = root / "prefix" / "var" / "lib" / "stroyka-deploy"
            self.assertEqual(service.read_text(encoding="utf-8"),
                             (ROOT / "deploy" / "systemd" / "stroyka-pull-deploy.service").read_text(encoding="utf-8"))
            self.assertTrue(timer.is_file())
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            recorded = log.read_text(encoding="utf-8")
            self.assertIn("daemon-reload", recorded)
            self.assertIn("enable --now stroyka-pull-deploy.timer", recorded)
            second = subprocess.run(["bash", script], check=False, capture_output=True, text=True, env=env)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            trusted = subprocess.run(
                ["git", "config", "--file", str(gitconfig), "--get-all", "safe.directory"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(trusted.returncode, 0, trusted.stderr)
            self.assertEqual(trusted.stdout.splitlines(), [str(app_root)])
            self.assertNotIn("*", trusted.stdout)
            removed = subprocess.run(
                ["bash", script, "--uninstall"],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            self.assertFalse(service.exists())
            self.assertFalse(timer.exists())
            self.assertTrue(state.is_dir())
            self.assertIn("disable --now stroyka-pull-deploy.timer", log.read_text(encoding="utf-8"))
            again = subprocess.run(
                ["bash", script, "--uninstall"],
                check=False, capture_output=True, text=True, env=env,
            )
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)


if __name__ == "__main__":
    unittest.main()
