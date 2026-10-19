"""Fixed server-side entry points; no arbitrary URLs or shell commands."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['status', 'demo', 'avito', 'eis', 'eis-search'])
    parser.add_argument('--query', default='электромонтаж')
    args=parser.parse_args()
    if os.geteuid() != 0:
        raise PermissionError('Run through sudo on the dedicated Jev server')
    if args.operation in {'eis', 'eis-search'}:
        from jev_eis_probe import probe
        # Serialise these resource-heavy browser probes separately from Jev's worker.
        import fcntl
        with open('/run/lock/stroyka-eis-probe.lock','a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return {'ok':False,'status':'busy'}
            return probe(args.query if args.operation == 'eis-search' else None)
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
