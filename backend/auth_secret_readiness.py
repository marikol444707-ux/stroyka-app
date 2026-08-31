"""Read-only authentication key readiness report."""

from __future__ import annotations

import argparse
import json

from backend.config import AUTH_SECRET_READINESS


def build_report() -> dict[str, object]:
    return {
        "ok": bool(AUTH_SECRET_READINESS["readyForEnforcement"]),
        "dryRun": True,
        "writesAttempted": 0,
        **AUTH_SECRET_READINESS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit unsuccessfully when the key is not ready for enforcement",
    )
    args = parser.parse_args()
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
