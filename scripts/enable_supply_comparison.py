#!/usr/bin/env python3
"""Enable the reviewed company-1 supply comparison on the existing deployment.

Default: read-only preflight. --apply: backup, build, configure, verify, publish.
The application checkout, database and other feature flags are not changed.
"""
import argparse
import fcntl
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


APP_ROOT = Path("/var/www/stroyka-app")
NGINX_ROOT = Path("/etc/nginx")
EVIDENCE_ROOT = Path("/root")
EXPECTED_COMMIT = "20cf455afd2690d99b560cf02257faf0a82744fc"
SITE_LINK = Path("/etc/nginx/sites-enabled/stroyka")
TARGETS = {
    "zones": Path("/etc/nginx/conf.d/supply-technical-comparison-rate-limits.conf"),
    "snippet": Path("/etc/nginx/snippets/supply-technical-comparison.conf"),
    "dropin": Path("/etc/systemd/system/stroyka.service.d/96-supply-technical-comparison.conf"),
    "frontend": APP_ROOT / ".env.production.local",
}
BUILD_FLAGS = {
    "REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED": "true",
    "REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS": "1",
}
BACKEND_FLAGS = {
    "SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED": "true",
    "SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS": "1",
}


def build_files(site, fragment, frontend):
    """Plan only the five reviewed configuration files; reject layout drift."""
    if "supply-technical-comparison" in site or "supply_technical_comparison" in site:
        raise ValueError("canary_already_configured")
    anchors = list(re.finditer(
        r"(?m)^(?P<indent>[ \t]*)include /etc/nginx/snippets/warehouse-anomaly-preview\.conf;[ \t]*$", site,
    ))
    if len(anchors) != 1:
        raise ValueError("nginx_anchor_changed")
    anchor = anchors[0]
    if not re.search(r"(?m)^\s*listen\s+443\b", site[:anchor.start()]):
        raise ValueError("nginx_https_anchor_missing")
    if re.search(r"(?m)^\s*location\s+~", site[:anchor.start()]):
        raise ValueError("nginx_regex_precedes_anchor")
    for prefix in re.findall(r"(?m)^\s*location\s+\^~\s+(\S+)", site):
        if "/supply-requests/".startswith(prefix.strip("\"'")):
            raise ValueError("nginx_priority_prefix_conflict")
    zone_lines = [line for line in fragment.splitlines() if line.startswith(("limit_req_zone ", "limit_conn_zone "))]
    if len(zone_lines) != 2 or fragment.count("location ~ ") != 1:
        raise ValueError("nginx_fragment_changed")
    snippet = fragment[fragment.index("location ~ "):]
    include = anchor.group("indent") + "include /etc/nginx/snippets/supply-technical-comparison.conf;\n"
    keep = [line for line in frontend.splitlines() if not re.match(
        r"^\s*(?:export\s+)?REACT_APP_SUPPLY_TECHNICAL_COMPARISON_(?:ENABLED|COMPANY_IDS)\s*=", line,
    )]
    return {
        "site": site[:anchor.start()] + include + site[anchor.start():],
        "zones": "\n".join(zone_lines) + "\n",
        "snippet": snippet,
        "frontend": "\n".join(keep + [f"{key}={value}" for key, value in BUILD_FLAGS.items()]) + "\n",
        "dropin": "[Service]\n" + "".join(f'Environment="{key}={value}"\n' for key, value in BACKEND_FLAGS.items()),
    }


def run(args, *, capture=False, env=None):
    return subprocess.run(args, cwd=APP_ROOT, env=env, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None).stdout


def atomic_write(path, content, mode, uid, gid):
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def health(base):
    with urllib.request.urlopen(base + "/health", timeout=10) as response:
        data = json.load(response)
    if data.get("ok") is not True or data.get("db", {}).get("ok") is not True:
        raise ValueError("health_not_ready")
    if data.get("version") != EXPECTED_COMMIT[:12]:
        raise ValueError("health_version_changed")


def wait_for_backend():
    for _ in range(45):
        try:
            health("http://127.0.0.1:8001")
            return
        except (OSError, ValueError):
            time.sleep(1)
    raise ValueError("backend_start_timeout")


def check_anonymous(base):
    url = base + "/supply-requests/1/technical-comparisons/supplier_offer/1?projectId=1&fileId=1"
    request = urllib.request.Request(url, headers={"X-Company-Id": "1", "X-Company-Mode": "company"})
    try:
        with urllib.request.urlopen(request, timeout=15):
            raise ValueError("anonymous_request_unexpectedly_succeeded")
    except urllib.error.HTTPError as error:
        if error.code != 401 or "no-store" not in error.headers.get("Cache-Control", ""):
            raise ValueError("anonymous_boundary_failed") from None
        if json.load(error) != {"detail": "supply_technical_comparison_authentication_required"}:
            raise ValueError("comparison_route_not_reached")


def verify_running_flags():
    pid = int(run(["systemctl", "show", "stroyka", "-p", "MainPID", "--value"], capture=True).strip())
    environment = dict(entry.split(b"=", 1) for entry in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if b"=" in entry)
    if any(environment.get(key.encode()) != value.encode() for key, value in BACKEND_FLAGS.items()):
        raise ValueError("running_process_flags_mismatch")


def check_published_frontend(build_path):
    request = urllib.request.Request("https://stroyka26.pro/asset-manifest.json",
                                     headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=15) as response:
        actual = json.load(response)
    expected = json.loads((Path(build_path) / "asset-manifest.json").read_text())
    if actual != expected:
        raise ValueError("public_frontend_version_mismatch")


def restore(evidence, *, restart_backend=True, reload_nginx=True, restore_frontend=True):
    manifest = json.loads((evidence / "manifest.json").read_text())
    expected_paths = dict(TARGETS, site=SITE_LINK.resolve(strict=True))
    if set(manifest) != set(expected_paths):
        raise ValueError("backup_manifest_invalid")
    for label, record in manifest.items():
        path = expected_paths[label]
        if str(path) != record["path"] or path.is_symlink():
            raise ValueError("backup_target_changed")
        if record["exists"]:
            atomic_write(path, (evidence / (label + ".before")).read_bytes(),
                         record["mode"], record["uid"], record["gid"])
        elif path.exists():
            # Keep created configuration files recoverable in the private backup.
            shutil.move(str(path), str(evidence / (label + ".disabled")))
    run(["nginx", "-t"])
    if reload_nginx:
        run(["systemctl", "reload", "nginx"])
    run(["systemctl", "daemon-reload"])
    if restart_backend:
        run(["systemctl", "restart", "stroyka"])
        wait_for_backend()
    if restore_frontend:
        run(["bash", "scripts/publish-frontend.sh", str(evidence / "frontend-before"), str(APP_ROOT / "build")])
    print("SUPPLY_COMPARISON_ROLLED_BACK EVIDENCE=" + str(evidence), flush=True)


def execute(apply):
    if run(["git", "rev-parse", "HEAD"], capture=True).strip() != EXPECTED_COMMIT:
        raise ValueError("application_commit_changed")
    run(["git", "diff", "--quiet"])
    run(["git", "diff", "--cached", "--quiet"])
    for service in ("stroyka", "nginx"):
        run(["systemctl", "is-active", "--quiet", service])
    health("https://stroyka26.pro")
    site = SITE_LINK.resolve(strict=True)
    if not site.is_relative_to(NGINX_ROOT) or not site.is_file():
        raise ValueError("nginx_site_path_invalid")
    targets = dict(TARGETS, site=site)
    for label, path in targets.items():
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("configuration_target_not_regular")
        if label in ("zones", "snippet", "dropin") and path.exists():
            raise ValueError("canary_file_already_exists")
        if not path.parent.is_dir():
            raise ValueError("configuration_directory_missing")
    nginx_before = run(["nginx", "-T"], capture=True)
    if "supply_technical_comparison" in nginx_before or "supply-technical-comparison" in nginx_before:
        raise ValueError("canary_nginx_already_present")
    frontend = targets["frontend"].read_text() if targets["frontend"].exists() else ""
    files = build_files(site.read_text(), (APP_ROOT / "ops-nginx-supply-technical-comparison.conf").read_text(), frontend)
    if not apply:
        print(json.dumps({"ready": True, "companyId": 1, "filesToConfigure": 5, "writesAttempted": 0}))
        return
    evidence = Path(tempfile.mkdtemp(prefix="stroyka-supply-comparison-", dir=EVIDENCE_ROOT))
    print("EVIDENCE=" + str(evidence), flush=True)
    manifest = {}
    for label, path in targets.items():
        exists = path.exists()
        info = path.stat() if exists else None
        manifest[label] = {"path": str(path), "exists": exists,
                           "mode": stat.S_IMODE(info.st_mode) if exists else (0o600 if label == "frontend" else 0o644),
                           "uid": info.st_uid if exists else 0, "gid": info.st_gid if exists else 0}
        if exists:
            (evidence / (label + ".before")).write_bytes(path.read_bytes())
        (evidence / (label + ".planned")).write_text(files[label])
    (evidence / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (evidence / "nginx-before.txt").write_text(nginx_before)
    shutil.copytree(APP_ROOT / "build", evidence / "frontend-before", symlinks=True)
    new_build = tempfile.mkdtemp(prefix=".frontend-build.", dir=APP_ROOT)
    (evidence / "build-path.txt").write_text(new_build)
    changed = backend_started = nginx_reloaded = frontend_started = False
    stage = "frontend_build"
    try:
        env = dict(os.environ, **BUILD_FLAGS, BUILD_PATH=new_build)
        service_env = run(["systemctl", "show", "stroyka", "-p", "Environment", "--value", "--no-pager"], capture=True)
        existing_flags = run(["bash", "scripts/resolve-frontend-build-env.sh", service_env, str(APP_ROOT / "backend/.env")], capture=True)
        for entry in existing_flags.splitlines():
            key, value = entry.split("=", 1)
            if not key.startswith("REACT_APP_ASSIGNMENT_DAILY_DRAFT_"):
                raise ValueError("unexpected_build_environment")
            env[key] = value
        print("Сборка интерфейса со сравнением КП...", flush=True)
        run(["npm", "run", "build"], env=env)
        stage = "configuration"
        changed = True
        for label, path in targets.items():
            record = manifest[label]
            atomic_write(path, files[label].encode(), record["mode"], record["uid"], record["gid"])
        run(["nginx", "-t"])
        nginx_reloaded = True
        run(["systemctl", "reload", "nginx"])
        run(["systemctl", "daemon-reload"])
        stage = "backend_restart"
        backend_started = True
        run(["systemctl", "restart", "stroyka"])
        wait_for_backend()
        verify_running_flags()
        stage = "anonymous_api_verification"
        check_anonymous("http://127.0.0.1:8001")
        check_anonymous("https://stroyka26.pro")
        health("https://stroyka26.pro")
        stage = "frontend_publish"
        frontend_started = True
        run(["bash", "scripts/publish-frontend.sh", new_build, str(APP_ROOT / "build")])
        stage = "production_smoke"
        run(["bash", "scripts/prod-smoke-check.sh"])
        check_published_frontend(new_build)
        health("https://stroyka26.pro")
    except BaseException:
        print("SUPPLY_CANARY_FAILED stage=" + stage, flush=True)
        if changed:
            try:
                restore(evidence, restart_backend=backend_started, reload_nginx=nginx_reloaded, restore_frontend=frontend_started)
            except BaseException:
                print("SUPPLY_ROLLBACK_INCOMPLETE EVIDENCE=" + str(evidence), flush=True)
                raise
        raise
    print("SUPPLY_COMPARISON_COMPANY_1_ENABLED EVIDENCE=" + str(evidence), flush=True)
    print("Требуется проверка сравнения реального КП из аккаунта директора или снабженца.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("run_as_root_on_production_server")
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    os.umask(0o077)
    with open("/var/lock/stroyka-deploy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            if run(["git", "rev-parse", "HEAD"], capture=True).strip() != EXPECTED_COMMIT:
                raise ValueError("application_commit_changed")
            evidence = args.rollback.resolve(strict=True)
            if evidence.parent != EVIDENCE_ROOT or not evidence.name.startswith("stroyka-supply-comparison-"):
                raise ValueError("backup_path_invalid")
            restore(evidence)
        else:
            execute(args.apply)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        # Captured commands can contain service credentials: never print args/tracebacks.
        code = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z_]+", str(error)) else type(error).__name__
        print("SUPPLY_CANARY_STOPPED code=" + code, flush=True)
        raise SystemExit(1)
