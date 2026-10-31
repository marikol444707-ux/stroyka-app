#!/usr/bin/env python3
"""Read-only audit of anonymous and authenticated access to registered S3 files."""

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import psycopg2.extras

from backend.db import get_db
from backend.features.public_file_ownership.s3_private_acl import (
    NoRedirectHandler,
    _candidate_storage_keys,
    _inspect_object_acl,
    _normalized_registry_rows,
    _storage_config,
    load_s3_private_acl_rows,
    probe_s3_object_access,
    _verify_authenticated_access,
)


def positive_limit(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    if parsed < 1:
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    return parsed


def probe_public_base(base, key, *, opener=None, timeout=15):
    url = str(base or "").rstrip("/") + "/" + urllib.parse.quote(key, safe="/")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return "unavailable"
    request = urllib.request.Request(
        url,
        headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
        method="GET",
    )
    request_opener = opener or urllib.request.build_opener(NoRedirectHandler())
    try:
        response = request_opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        status = int(error.code or 0)
        error.close()
        if status in (401, 403):
            return "private"
        if status == 404:
            return "missing"
        return "unavailable"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "unavailable"
    try:
        status = int(getattr(response, "status", response.getcode()) or 0)
        return "public" if status in (200, 206) else "unavailable"
    finally:
        response.close()


def run_audit(*, limit=None):
    config = _storage_config()
    conn = get_db()
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SET LOCAL statement_timeout='60s'")
            rows = load_s3_private_acl_rows(cur)
            normalized, invalid_reasons = _normalized_registry_rows(rows)
            counts = Counter()
            inspected = 0
            public_bases = []
            public_url = os.getenv("S3_PUBLIC_URL", "").strip().rstrip("/")
            if public_url:
                public_bases.append(("S3_PUBLIC_URL", public_url))
            public_bases.extend(
                (f"S3_LEGACY_PUBLIC_URLS[{index}]", value.strip().rstrip("/"))
                for index, value in enumerate(
                    os.getenv("S3_LEGACY_PUBLIC_URLS", "").split(",")
                )
                if value.strip()
            )
            all_keys = _candidate_storage_keys(rows)
            keys = all_keys
            if limit is not None:
                keys = keys[:limit]

            for key in keys:
                acl = _inspect_object_acl(key, config)
                anonymous = probe_s3_object_access(key, storage_config=config)
                public_access = tuple(
                    (name, probe_public_base(base, key))
                    for name, base in public_bases
                )
                authenticated = _verify_authenticated_access(key, config)
                counts[(acl, anonymous, public_access, bool(authenticated))] += 1
                inspected += 1

            conn.rollback()
            return {
                "mode": "read-only",
                "registeredS3Rows": len(rows),
                "validRegistryRows": len(normalized),
                "uniqueObjects": len(all_keys),
                "objectsInspected": inspected,
                "objectsRemaining": max(0, len(all_keys) - inspected),
                "inspectionLimited": inspected < len(all_keys),
                "configuredPublicBasesChecked": len(public_bases),
                "invalidRegistryReasons": dict(sorted(invalid_reasons.items())),
                "accessCombinations": [
                    {
                        "objectAcl": acl,
                        "anonymousAccess": anonymous,
                        "configuredPublicBaseAccess": dict(public_access),
                        "authenticatedAppAccess": authenticated,
                        "objects": count,
                    }
                    for (acl, anonymous, public_access, authenticated), count
                    in sorted(counts.items())
                ],
                "writesAttempted": 0,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=positive_limit,
        help="inspect at most this many unique objects (deterministic order)",
    )
    args = parser.parse_args()
    print(json.dumps(run_audit(limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
