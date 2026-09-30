#!/usr/bin/env python3
"""Mirror the exact backend material-capability gate into the React build."""

import shlex
import sys
from pathlib import Path


BACKEND_KEY = "SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED"
FRONTEND_KEY = "REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED"
VALID_VALUES = frozenset({"true", "false"})


def _file_value(path):
    path = Path(path) if path else None
    if not path or not path.is_file():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == BACKEND_KEY:
            return value.strip().strip('"').strip("'")
    return None


def resolve(service_environment, backend_env_path):
    value = _file_value(backend_env_path)
    for entry in shlex.split(service_environment or ""):
        key, separator, candidate = entry.partition("=")
        if separator and key == BACKEND_KEY:
            value = candidate
    value = "false" if value is None else value
    if value not in VALID_VALUES:
        raise ValueError(f"{BACKEND_KEY}: ожидается true или false")
    return f"{FRONTEND_KEY}={value}"


if __name__ == "__main__":
    try:
        print(resolve(
            sys.argv[1] if len(sys.argv) > 1 else "",
            sys.argv[2] if len(sys.argv) > 2 else "",
        ))
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
