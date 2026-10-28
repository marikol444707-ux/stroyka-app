from dataclasses import replace
import errno
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from .cli_plan import build_cli_plan
from .contract import validate_v2_request
from .invoker import _run_bounded, invoke_cli
from .discovery import RuntimeMismatch
from .state import Scope

SCOPE=Scope(37,'fixture-owner')


def call():
    req=validate_v2_request({'version':2,'request_id':'search-fixture-001',
        'region':'Ставропольский край','sources':['commercial'],'topics':['кровля']})
    return build_cli_plan(req,SCOPE).calls[0]


class FixedInvokerTests(unittest.TestCase):
    def test_eis_arguments_cannot_be_replaced_with_another_operation(self):
        req=validate_v2_request({'version':2,'request_id':'search-fixture-001','region':'Ставропольский край',
                                'sources':['eis'],'topics':['кровля'],'legal_regimes':['44-ФЗ']})
        value=build_cli_plan(req,SCOPE).calls[0]
        with patch('jev_agent.tender_finder.invoker.verify_installed_runtime'),patch('jev_agent.tender_finder.invoker._run_bounded',return_value=(b'{}',1)) as run:
            invoke_cli(value,100,scope=SCOPE)
            run.assert_called_once_with(value.argv,None,100)
            run.reset_mock()
            with self.assertRaises(ValueError):
                invoke_cli(replace(value,argv=(value.argv[0],'eis-review','--notice','https://example.org')),100,scope=SCOPE)
            run.assert_not_called()

    def test_changed_runtime_prevents_real_process_launch(self):
        with patch('jev_agent.tender_finder.invoker.verify_installed_runtime',side_effect=RuntimeMismatch('changed')),patch('jev_agent.tender_finder.invoker._run_bounded') as run:
            with self.assertRaises(RuntimeMismatch):invoke_cli(call(),330,scope=SCOPE)
            run.assert_not_called()

    def test_validated_call_is_verified_and_keeps_exact_argv_and_stdin(self):
        value=call()
        with patch('jev_agent.tender_finder.invoker.verify_installed_runtime') as gate,patch('jev_agent.tender_finder.invoker._run_bounded',return_value=(b'{}',1)) as run:
            self.assertEqual(invoke_cli(value,330,scope=SCOPE),(b'{}',1))
            gate.assert_called_once();run.assert_called_once_with(value.argv,value.stdin,330)

    def test_arbitrary_commands_wrong_company_and_extra_profile_fields_never_launch(self):
        value=call();profile=json.loads(value.stdin)
        variants=[replace(value,argv=('/bin/sh','-c','id')),
                  replace(value,stdin=json.dumps({**profile,'companyId':99}).encode()),
                  replace(value,stdin=json.dumps({**profile,'token':'PRIVATE'}).encode()),
                  replace(value,stdin=b'{"companyId":37,"companyId":99}'),
                  replace(value,stdin=json.dumps({**profile,'searchTerms':[]}).encode())]
        with patch('jev_agent.tender_finder.invoker.verify_installed_runtime') as gate,patch('jev_agent.tender_finder.invoker._run_bounded') as run:
            for item in variants:
                with self.subTest(item=item.argv),self.assertRaises(ValueError):invoke_cli(item,330,scope=SCOPE)
            gate.assert_not_called();run.assert_not_called()

    def test_unbounded_timeout_is_not_allowed(self):
        with patch('jev_agent.tender_finder.invoker._run_bounded') as run,self.assertRaises(ValueError):
            invoke_cli(call(),999999,scope=SCOPE)
        run.assert_not_called()


class LocalTransportTests(unittest.TestCase):
    # Execute only synthetic Python children: no CLI, browser, Docker or network.
    def test_real_child_receives_full_stdin_and_nonzero_output_is_retained(self):
        script='import sys; b=sys.stdin.buffer.read(); sys.stdout.buffer.write(b); sys.exit(3)'
        stdout,code=_run_bounded((sys.executable,'-c',script),b'x'*32000,5)
        self.assertEqual(stdout,b'x'*32000);self.assertEqual(code,3)

    def test_unread_stdin_cannot_deadlock_parent(self):
        stdout,code=_run_bounded((sys.executable,'-c','print("ready")'),b'x'*32768,5)
        self.assertEqual(stdout,b'ready\n');self.assertEqual(code,0)

    def test_output_flood_is_stopped_at_the_limit(self):
        with self.assertRaises(OSError) as caught:
            _run_bounded((sys.executable,'-c','import sys; sys.stdout.buffer.write(b"x"*2000000)'),None,5)
        self.assertEqual(caught.exception.errno,errno.EFBIG)

    def test_timeout_is_bounded_and_stderr_not_returned(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            _run_bounded((sys.executable,'-c','import time; time.sleep(30)'),None,.1)
        stdout,code=_run_bounded((sys.executable,'-c','import sys; sys.stderr.write("PRIVATE"); print("ok")'),None,5)
        self.assertEqual(stdout,b'ok\n');self.assertEqual(code,0)


if __name__=='__main__':unittest.main()
