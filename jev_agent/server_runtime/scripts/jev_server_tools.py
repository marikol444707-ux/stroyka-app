"""Fixed server-side entry points; no arbitrary URLs or shell commands."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['status', 'demo', 'avito', 'eis', 'eis-search', 'eis-review', 'commercial-search'])
    parser.add_argument('--query')
    parser.add_argument('--profile-stdin', action='store_true',
                        help='Read a company search profile JSON object from stdin')
    parser.add_argument('--stavropol-open', action='store_true', help='44-ФЗ: Ставропольский край, только подача заявок')
    parser.add_argument('--notice', help='Наблюдавшаяся ссылка на карточку закупки 44-ФЗ')
    args=parser.parse_args()
    if args.operation=='eis-review' and not args.notice:parser.error('--notice is required for eis-review')
    if args.operation == 'commercial-search' and args.query is not None:
        parser.error('--query is not configurable for commercial-search')
    if args.profile_stdin and args.operation != 'commercial-search':
        parser.error('--profile-stdin requires commercial-search')
    profile = None
    if args.profile_stdin:
        raw_profile = sys.stdin.buffer.read(32769)
        if len(raw_profile) > 32768:
            parser.error('company profile exceeds size limit')
        profile = json.loads(raw_profile.decode('utf-8'))
    if args.notice and args.operation!='eis-review':parser.error('--notice requires eis-review')
    if args.stavropol_open and args.operation != 'eis-search':
        parser.error('--stavropol-open requires eis-search')
    if os.geteuid() != 0:
        raise PermissionError('Run through sudo on the dedicated Jev server')
    if args.operation=='eis-review':
        import fcntl
        from jev_eis_review_runner import run
        with open('/run/lock/stroyka-eis-probe.lock','a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:return {'ok':False,'status':'busy'}
            return run(args.notice)
    if args.operation == 'commercial-search':
        from jev_commercial_search import probe
        import fcntl
        # Share the browser lock with public EIS runs; both use a disposable
        # Chrome container and the same bounded host resources.
        with open('/run/lock/stroyka-eis-probe.lock', 'a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return {'ok': False, 'status': 'busy'}
            return probe(profile)
    if args.operation in {'eis', 'eis-search'}:
        from jev_eis_probe import probe
        # Serialise these resource-heavy browser probes separately from Jev's worker.
        import fcntl
        with open('/run/lock/stroyka-eis-probe.lock','a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return {'ok':False,'status':'busy'}
            query = args.query or 'электромонтаж'
            return probe(query if args.operation == 'eis-search' else None, args.stavropol_open)
    operation='health' if args.operation=='status' else args.operation
    request={'operation':operation}
    if operation=='avito': request['query']='кирпич б/у'
    result=subprocess.run(['python3','/usr/local/libexec/stroyka-jev-control/jev_control.py','--server'],
                          input=json.dumps(request),capture_output=True,text=True,timeout=125)
    if result.returncode: return {'ok':False,'status':'controller_failed'}
    return json.loads(result.stdout)

if __name__=='__main__':
    try: result=main()
    except Exception as exc: result={'ok':False,'status':'tools_failed','error_type':type(exc).__name__}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result.get('ok') else 1)
