#!/usr/bin/env python3
"""Mirror participant rollout modes into the React build; never emit other settings."""
import shlex
import sys
from pathlib import Path

NAMES = (
    "PARTICIPANT_SUPPORT_ENABLED", "PARTICIPANT_SUPPORT_ACCESS_ENABLED",
    "PARTICIPANT_CONNECTIONS_ENABLED",
    "PARTICIPANT_HISTORY_PREVIEW_ENABLED",
    "PARTICIPANT_HISTORY_MERGE_ENABLED",
    "PARTICIPANT_CORRECTION_PREVIEW_ENABLED",
    "PARTICIPANT_CORRECTIONS_ENABLED",
    "PARTICIPANT_RFQ_CORRECTIONS_ENABLED",
    "PARTICIPANT_QUOTE_CORRECTIONS_ENABLED",
    "PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED",
    "PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED",
    "PARTICIPANT_CONTRACT_ACCESS_CORRECTIONS_ENABLED",
)


def resolve(service_environment, backend_env_path):
    values = {}
    path = Path(backend_env_path) if backend_env_path else None
    if path and path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = raw_line.strip().partition("=")
            if separator and key.strip() in NAMES:
                values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    for entry in shlex.split(service_environment or ""):
        key, separator, value = entry.partition("=")
        if separator and key in NAMES:
            values[key] = value
    for name in NAMES:
        if values.get(name, "0") not in {"0", "1"}:
            raise ValueError(f"{name}: ожидается 0 или 1")
    if any(values.get(name, "0") == "1" for name in NAMES[1:]) and values.get(NAMES[0], "0") != "1":
        raise ValueError("Режимы участников требуют PARTICIPANT_SUPPORT_ENABLED=1")
    return "\n".join(f"REACT_APP_{name}={values.get(name, '0')}" for name in NAMES)


if __name__ == "__main__":
    try:
        print(resolve(sys.argv[1] if len(sys.argv) > 1 else "",
                      sys.argv[2] if len(sys.argv) > 2 else ""))
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
