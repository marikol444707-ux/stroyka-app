#!/usr/bin/env python3
"""Read one GitHub response and decide whether pull-deploy may install that commit.

The server asks the public API once per tick. This file turns that JSON into
green / pending / failed / error and can write a curl config for an optional
token. It never prints the token.
"""

import json
import os
import re
import stat
import sys

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
EXIT_CODE = {"green": 0, "pending": 10, "failed": 11, "error": 12}


def parse_github_repo(url):
    text = str(url or "").strip()
    text = re.sub(r"\.git/*$", "", text, flags=re.IGNORECASE).rstrip("/")
    patterns = (
        r"^https?://(?:[^@/\s]+@)?github\.com/([^/\s]+)/([^/\s]+)$",
        r"^ssh://(?:[^@/\s]+@)?github\.com/([^/\s]+)/([^/\s]+)$",
        r"^git@github\.com:([^/\s]+)/([^/\s]+)$",
    )
    for pattern in patterns:
        matched = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if not matched:
            continue
        repo = "%s/%s" % (matched.group(1), matched.group(2))
        if REPO_RE.fullmatch(repo):
            return repo
    return ""


def _is_main_ci(run):
    path = str(run.get("path") or "")
    name = str(run.get("name") or "")
    if path:
        return path == "ci.yml" or path.endswith("/ci.yml")
    return name in ("", "CI")


def _run_id(run):
    try:
        return int(run.get("id") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def classify_ci(payload, expected_sha):
    """Return (green|pending|failed|error, short message)."""
    expected = str(expected_sha or "").strip().lower()
    if SHA_RE.fullmatch(expected) is None:
        return "error", "Некорректный SHA для проверки CI."
    if not isinstance(payload, dict) or "workflow_runs" not in payload:
        return "error", "Ответ GitHub не содержит список CI."
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        return "error", "Список CI имеет неожиданный вид."

    matching = []
    for run in runs:
        if not isinstance(run, dict):
            return "error", "В списке CI есть некорректная запись."
        head = str(run.get("head_sha") or "").strip().lower()
        if head and head != expected:
            continue
        if not _is_main_ci(run):
            continue
        if run.get("head_branch") != "main" or run.get("event") != "push":
            continue
        matching.append(run)
    if not matching:
        return "pending", "CI для %s ещё не появился. Проверю снова." % expected[:12]

    latest = max(matching, key=_run_id)
    if _run_id(latest) <= 0:
        return "error", "У запуска CI нет номера."
    if str(latest.get("status") or "") != "completed":
        return "pending", "CI для %s ещё выполняется. Проверю снова." % expected[:12]
    if latest.get("conclusion") == "success":
        return "green", "CI для %s успешный." % expected[:12]
    return "failed", "CI для %s неуспешен (%s). Этот коммит пропускаю." % (
        expected[:12], latest.get("conclusion") or "пусто",
    )


def token_file_decision(mode, file_uid, euid):
    """Whether a token file may be read. open/owner mean ignore the file."""
    if mode & 0o077:
        return "open"
    if euid == 0 and file_uid != 0:
        return "owner"
    if euid != 0 and file_uid != euid:
        return "owner"
    return "ok"


def _strip_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_token_assignment(text):
    for line in str(text or "").splitlines():
        if line.startswith("GITHUB_TOKEN="):
            return _strip_quotes(line.split("=", 1)[1].strip())
    return ""


def load_token_file(path):
    """Return (status, token). Token is empty unless status is ready.

    status: absent, empty, open, owner, invalid, ready.
    """
    if not os.path.isfile(path):
        return "absent", ""
    try:
        info = os.stat(path)
    except OSError:
        return "invalid", ""
    decision = token_file_decision(stat.S_IMODE(info.st_mode), info.st_uid, os.geteuid())
    if decision != "ok":
        return decision, ""
    try:
        with open(path, encoding="utf-8") as handle:
            token = read_token_assignment(handle.read())
    except (OSError, UnicodeError):
        return "invalid", ""
    if not token:
        return "empty", ""
    if TOKEN_RE.fullmatch(token) is None:
        return "invalid", ""
    return "ready", token


def write_curl_config(path, token):
    if TOKEN_RE.fullmatch(token or "") is None:
        raise ValueError("bad token")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write('header = "Authorization: Bearer %s"\n' % token)


def prepare_curl_config(dest, token_file=None):
    """Write dest when a token is usable. Return a status word, never the token."""
    env_token = os.environ.get("GITHUB_TOKEN") or ""
    if env_token:
        if TOKEN_RE.fullmatch(env_token) is None:
            return "invalid"
        write_curl_config(dest, env_token)
        return "ready"
    if not token_file:
        return "absent"
    status, token = load_token_file(token_file)
    if status != "ready":
        return status
    write_curl_config(dest, token)
    return "ready"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--repo":
        if len(argv) != 2:
            print("ОШИБКА: укажите адрес origin.", file=sys.stderr)
            return 2
        repo = parse_github_repo(argv[1])
        if not repo:
            print("ОШИБКА: origin не похож на github.com/owner/repo.", file=sys.stderr)
            return 1
        print(repo)
        return 0
    if argv and argv[0] == "--curl-config":
        if len(argv) not in (2, 3):
            print("ОШИБКА: укажите файл конфигурации curl.", file=sys.stderr)
            return 2
        token_file = argv[2] if len(argv) == 3 else None
        try:
            print(prepare_curl_config(argv[1], token_file))
        except (OSError, ValueError):
            print("invalid")
            return 0
        return 0
    if len(argv) != 2:
        print("ОШИБКА: укажите SHA и файл ответа GitHub.", file=sys.stderr)
        return 2
    sha, path = argv
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("Не удалось прочитать ответ CI.", file=sys.stderr)
        return EXIT_CODE["error"]
    state, message = classify_ci(payload, sha)
    stream = sys.stdout if state != "error" else sys.stderr
    print(message, file=stream)
    return EXIT_CODE[state]


if __name__ == "__main__":
    sys.exit(main())
