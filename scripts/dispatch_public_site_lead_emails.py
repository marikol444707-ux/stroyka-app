#!/usr/bin/env python3
"""Dispatch due public-site lead email notifications from the database outbox."""

import json

from backend.main import public_site_lead_email_notifier


def main() -> None:
    result = public_site_lead_email_notifier.dispatch_pending(limit=20)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
