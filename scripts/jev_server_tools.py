"""Fixed server-side entry points; no arbitrary URLs or shell commands."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['status', 'demo', 'avito', 'eis', 'eis-search', 'eis-review'])
    parser.add_argument('--query', default='электромонтаж')
    parser.add_argument('--stavropol-open', action='store_true', help='44-ФЗ: Ставропольский край, только подача заявок')
    parser.add_argument('--notice', help='Наблюдавшаяся ссылка на карточку закупки 44-ФЗ')
    args=parser.parse_args()
    if args.operation=='eis-review' and not args.notice:parser.error('--notice is required for eis-review')
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
    if args.operation in {'eis', 'eis-search'}:
        from jev_eis_probe import probe
        # Serialise these resource-heavy browser probes separately from Jev's worker.
        import fcntl
        with open('/run/lock/stroyka-eis-probe.lock','a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return {'ok':False,'status':'busy'}
            return probe(args.query if args.operation == 'eis-search' else None, args.stavropol_open)
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
