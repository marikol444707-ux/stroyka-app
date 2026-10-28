"""Offline v2 validation only. Does not search, queue, send, or import into CRM."""
import argparse
import json
import sys

from .contract import InvalidRequest, MAX_REQUEST_BYTES, parse_v2_request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('validate-v2',))
    parser.parse_args(argv)
    try:
        request = parse_v2_request(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
    except InvalidRequest as error:
        print(json.dumps(error.as_dict(), ensure_ascii=False))
        return 2
    print(json.dumps({'ok': True, 'normalized_request': request.canonical_payload(),
                      'search_executed': False, 'legacy_v1_compatibility': 'not_verified',
                      'source_coverage': 'not_tested'}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
