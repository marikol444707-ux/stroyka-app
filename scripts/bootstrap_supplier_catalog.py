#!/usr/bin/env python3
"""Plan read-only; apply only the exact externally reviewed company ownership map."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg2.extras
from backend.db import get_db
from backend.features.supplier_access.catalog_bootstrap import apply_plan, digest, make_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('--company-id', type=int, required=True)
    plan.add_argument('--supplier-ids', required=True, help='Explicit comma-separated IDs, never inferred from history')
    plan.add_argument('--output', type=Path, required=True)
    apply = commands.add_parser('apply')
    apply.add_argument('--plan', type=Path, required=True)
    apply.add_argument('--sha256', required=True)
    args = parser.parse_args()
    conn = get_db()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if args.command == 'plan':
                cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SET LOCAL lock_timeout='5s'")
            if args.command == 'plan':
                result = make_plan(cur, args.company_id, [int(value) for value in args.supplier_ids.split(',')])
                # The artifact lists names/hashes, not private commercial values.
                with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
                    json.dump(result, output, ensure_ascii=False, indent=2)
                conn.rollback()
                print(json.dumps({'plan': str(args.output), 'sha256': digest(result), 'count': len(result['suppliers'])}))
            else:
                result = apply_plan(cur, json.loads(args.plan.read_text()), args.sha256)
                conn.commit()
                print(json.dumps(result))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
