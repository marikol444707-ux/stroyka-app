"""Dry-run-first operator command for one accounting ownership repair."""

import argparse
import json
import re

from backend.features.accounting_exception_checks.ownership_remediation import (
    build_accounting_ownership_remediation_request,
)
from backend.features.accounting_exception_checks.ownership_remediation_runner import (
    run_accounting_ownership_remediation,
)


APPLY_CONFIRMATION = "APPLY_EXACT_ACCOUNTING_OWNERSHIP_REMEDIATION"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _positive_int_argument(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed <= 0 or str(parsed) != value:
        raise argparse.ArgumentTypeError("must be a canonical positive integer")
    return parsed


def _sha256_argument(value):
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("must be a lowercase SHA-256")
    return value


def _open_connection():
    from backend.db import get_db

    return get_db()


def _parser():
    parser = argparse.ArgumentParser(
        description="Guarded exact-record accounting ownership remediation",
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--record-id", required=True, type=_positive_int_argument)
    parser.add_argument("--company-id", required=True, type=_positive_int_argument)
    parser.add_argument("--project-id", type=_positive_int_argument)
    parser.add_argument(
        "--operator-user-id", required=True, type=_positive_int_argument,
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--expected-request-sha256", type=_sha256_argument,
    )
    parser.add_argument(
        "--expected-evidence-sha256", type=_sha256_argument,
    )
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.apply:
        if args.confirm != APPLY_CONFIRMATION:
            parser.error("--apply requires the exact confirmation phrase")
        if args.expected_request_sha256 is None:
            parser.error("--apply requires --expected-request-sha256")
        if args.expected_evidence_sha256 is None:
            parser.error("--apply requires --expected-evidence-sha256")
    elif (
        args.confirm
        or args.expected_request_sha256 is not None
        or args.expected_evidence_sha256 is not None
    ):
        parser.error("apply guards are valid only with --apply")

    try:
        request = build_accounting_ownership_remediation_request(
            source=args.source,
            record_id=args.record_id,
            company_id=args.company_id,
            project_id=args.project_id,
            operator_user_id=args.operator_user_id,
        )
    except ValueError:
        parser.error("accounting remediation arguments are invalid")
    if (
        args.apply
        and request["requestSha256"] != args.expected_request_sha256
    ):
        parser.error("the request changed after dry-run")

    connection = _open_connection()
    try:
        result = run_accounting_ownership_remediation(
            connection,
            request,
            apply=args.apply,
            expected_evidence_sha256=args.expected_evidence_sha256,
        )
    finally:
        connection.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
