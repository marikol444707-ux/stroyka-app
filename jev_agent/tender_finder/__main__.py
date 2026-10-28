"""Explicit validation and one-shot worker entry points; no automatic services."""
import argparse
import json
import sys
import os

from .contract import InvalidRequest, MAX_REQUEST_BYTES, parse_v2_request
from .runtime import initialize_worker
from .settings import load_settings
from .bootstrap_key import read_bootstrap_key
from .host_worker import run_host_pass
from .docker_delivery import check_hermes_container


class BridgeParser(argparse.ArgumentParser):
    def error(self,message):
        # Unknown operator arguments might accidentally contain a secret. Never
        # echo their values into service logs or shell transcripts.
        self.exit(2,'invalid bridge arguments\n')


def main(argv=None):
    parser = BridgeParser(description=__doc__)
    parser.add_argument('operation', choices=('validate-v2','check-settings','worker-once','worker-resume','host-pass'))
    parser.add_argument('--config')
    parser.add_argument('--key-fd',type=int)
    parser.add_argument('--request')
    parser.add_argument('--claim')
    parser.add_argument('--gateway-gid',type=int)
    args=parser.parse_args(argv)
    if args.operation!='validate-v2':
        if not args.config:parser.error('configuration required')
        if args.operation=='check-settings':
            if args.key_fd is not None or args.request or args.claim or args.gateway_gid is not None:parser.error('unexpected worker arguments')
        elif args.key_fd is None or args.key_fd<3:
            parser.error('inherited key descriptor required')
        elif args.operation=='host-pass':
            if args.request or args.claim or args.gateway_gid is None or args.gateway_gid<=0:
                parser.error('explicit host activation required')
        elif ((args.operation=='worker-once' and (not args.request or args.claim))
              or (args.operation=='worker-resume' and (not args.claim or args.request))):
            parser.error('one explicit request or recovery handle required')
        elif args.gateway_gid is not None:parser.error('unexpected host argument')
        try:
            if args.operation=='check-settings':
                load_settings(args.config)
                value={'configuration_loaded':True,'installation_ready':False,'search_executed':False,'notification_sent':False}
            elif args.operation=='host-pass':
                if os.geteuid()!=0:
                    try:os.close(args.key_fd)
                    except OSError:pass
                    raise ValueError('privileged_host_worker_required')
                try:check_hermes_container()
                except Exception:
                    try:os.close(args.key_fd)
                    except OSError:pass
                    raise
                secret=read_bootstrap_key(args.key_fd)
                settings=load_settings(args.config)
                if os.geteuid()!=0 or settings.queue.writer_uid!=0 or settings.gateway_uid is None:
                    raise ValueError('privileged_broker_worker_settings_required')
                value=run_host_pass(settings,secret,gateway_gid=args.gateway_gid)
                print(json.dumps(value,ensure_ascii=False))
                return 1 if value['errors'] else 0
            else:
                worker=initialize_worker(args.config,args.key_fd)
                outcome=worker.consume(args.request) if args.operation=='worker-once' else worker.resume(args.claim)
                # Public lifecycle metadata only, not private report/config/keys.
                value={name:outcome[name] for name in ('request_id','status','claim_handle','job_disposition',
                    'publication_disposition','completion_event_id','notification_sent','handled') if name in outcome}
            print(json.dumps(value,ensure_ascii=False));return 0
        except Exception as error:
            print(json.dumps({'ok':False,'code':type(error).__name__,'installation_ready':False,
                              'notification_sent':False}));return 1
    if args.config or args.key_fd is not None or args.request or args.claim or args.gateway_gid is not None:
        parser.error('validation does not accept runtime settings')
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
