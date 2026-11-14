#!/usr/bin/env python3
"""Allow a deploy only when the newest CI run for the commit is a green main push."""

import json
import sys


def _run_id(run):
    try:
        return int(run.get("databaseId"))
    except (AttributeError, TypeError, ValueError):
        return -1


def deployment_allowed(runs, expected_sha):
    expected = str(expected_sha or "").strip().lower()
    if len(expected) != 40 or any(char not in "0123456789abcdef" for char in expected):
        return False, "Некорректный SHA коммита для проверки CI."
    if not isinstance(runs, list):
        return False, "Ответ GitHub со списком CI имеет неожиданный вид."

    matching = []
    for run in runs:
        if not isinstance(run, dict):
            return False, "В списке CI есть некорректная запись."
        head = str(run.get("headSha") or "").strip().lower()
        if head and head != expected:
            continue
        matching.append(run)
    if not matching:
        return False, "Для этого коммита нет запуска CI."

    latest = max(matching, key=_run_id)
    if _run_id(latest) < 0:
        return False, "У запуска CI нет номера, решение не принято."
    if latest.get("headBranch") != "main" or latest.get("event") != "push":
        return False, "Последний CI запущен не из push в main."
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        return False, "Последний CI не успешный: status=%s conclusion=%s." % (
            latest.get("status"), latest.get("conclusion"),
        )
    return True, "CI для этого коммита успешный."


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("ОШИБКА: укажите файл со списком CI и SHA коммита.", file=sys.stderr)
        return 2
    path, sha = argv
    try:
        with open(path, encoding="utf-8") as handle:
            runs = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print("ОШИБКА: не удалось прочитать список CI (%s)." % exc.__class__.__name__, file=sys.stderr)
        return 1
    allowed, message = deployment_allowed(runs, sha)
    print(message)
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())
