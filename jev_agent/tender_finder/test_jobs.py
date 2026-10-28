from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from .contract import InvalidRequest
from .discovery import RuntimeMismatch
from .jobs import process_request
from .state import RequestBusy, RequestConflict, Scope, StorageError

SCOPE=Scope(37,'fixture-owner')


def request(version=2, **changes):
    return {'version':version,'request_id':'search-fixture-001','region':'Ставропольский край',
            'sources':['commercial'],'topics':['кровля'], **changes}


def response():
    return json.dumps({'ok':True,'sources':[{'provider':'B2B-Center','ok':True}],
                       'confirmed':[],'review':[]}).encode(),0


def crash_search(directory):
    def invoke(call,timeout):os._exit(9)
    process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=lambda:None)


def hold_search(directory, started, finish):
    def invoke(call,timeout):
        started.set()
        if not finish.wait(10):raise RuntimeError('fixture timeout')
        return response()
    process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=lambda:None)


class JobIntegrationTests(unittest.TestCase):
    def test_v2_replay_after_restart_does_not_repeat_cli_or_runtime_check(self):
        with tempfile.TemporaryDirectory() as directory:
            invoke=Mock(return_value=response());gate=Mock()
            first=process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=gate)
            replay=process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=gate)
            self.assertEqual(first.disposition,'execute')
            self.assertEqual(replay.disposition,'cached')
            self.assertEqual(first.result,replay.result)
            self.assertFalse(replay.delivery_verified)
            invoke.assert_called_once();gate.assert_called_once()

    def test_changed_request_conflicts_without_search_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            invoke=Mock(return_value=response())
            process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=Mock())
            before={p.name:p.read_bytes() for p in Path(directory).glob('*.json')}
            with self.assertRaises(RequestConflict):
                process_request(request(price_min_rub=1000000),SCOPE,directory,invoke=invoke,verify_runtime=Mock())
            self.assertEqual(before,{p.name:p.read_bytes() for p in Path(directory).glob('*.json')})
            invoke.assert_called_once()

    def test_v1_calls_bound_validator_and_executor_without_rewriting_response(self):
        raw=request(version=1)
        expected={'request_id':raw['request_id'],'ok':True,'outputs':[],'topics':['кровля']}
        validator=Mock(side_effect=deepcopy);executor=Mock(return_value=deepcopy(expected))
        with tempfile.TemporaryDirectory() as directory:
            for _ in range(2):
                result=process_request(raw,SCOPE,directory,legacy_validator=validator,legacy_executor=executor)
                self.assertEqual(result.result,expected)
            self.assertEqual(validator.call_count,2)
            executor.assert_called_once_with(raw)
        # Callback fixtures do not constitute acceptance against the installed worker.

    def test_validation_and_missing_binding_leave_no_durable_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(InvalidRequest):
                process_request(request(companyId=9),SCOPE,directory,invoke=Mock())
            with self.assertRaises(ValueError):
                process_request(request(version=1),SCOPE,directory,legacy_validator=Mock(side_effect=deepcopy))
            self.assertEqual(list(Path(directory).iterdir()),[])
        with self.assertRaises(StorageError):process_request(request(),None,'/does-not-exist')

    def test_executor_errors_and_cross_company_results_become_safe_cached_failures(self):
        for value in (RuntimeError('PRIVATE_TOKEN'),{'request_id':'wrong','ok':True},
                      {'request_id':request()['request_id'],'company_id':99,'ok':True}):
            with self.subTest(value=type(value).__name__),tempfile.TemporaryDirectory() as directory:
                executor=Mock(side_effect=value) if isinstance(value,Exception) else Mock(return_value=value)
                for _ in range(2):
                    result=process_request(request(version=1),SCOPE,directory,
                                           legacy_validator=Mock(side_effect=deepcopy),legacy_executor=executor)
                    self.assertEqual(result.result['reason'],'execution_failed')
                    self.assertNotIn('PRIVATE_TOKEN',json.dumps(result.result))
                executor.assert_called_once()

    def test_runtime_mismatch_is_not_retried_as_a_second_search(self):
        with tempfile.TemporaryDirectory() as directory:
            invoke=Mock();gate=Mock(side_effect=RuntimeMismatch('PRIVATE_PATH'))
            first=process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=gate)
            replay=process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=gate)
            self.assertEqual(first.result['reason'],'runtime_changed')
            self.assertEqual(first.result,replay.result)
            invoke.assert_not_called();gate.assert_called_once()

    def test_real_killed_search_returns_interrupted_without_relaunch(self):
        with tempfile.TemporaryDirectory() as directory:
            child=multiprocessing.get_context('fork').Process(target=crash_search,args=(directory,))
            child.start();child.join(10)
            self.assertEqual(child.exitcode,9)
            invoke=Mock()
            result=process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=Mock())
            self.assertEqual(result.disposition,'interrupted')
            self.assertEqual(result.result['reason'],'execution_interrupted')
            invoke.assert_not_called()

    def test_concurrent_job_is_busy_and_does_not_execute_again(self):
        with tempfile.TemporaryDirectory() as directory:
            context=multiprocessing.get_context('fork')
            started=context.Event();finish=context.Event()
            child=context.Process(target=hold_search,args=(directory,started,finish))
            child.start()
            try:
                self.assertTrue(started.wait(10))
                invoke=Mock()
                with self.assertRaises(RequestBusy):
                    process_request(request(),SCOPE,directory,invoke=invoke,verify_runtime=Mock())
                invoke.assert_not_called()
            finally:
                finish.set();child.join(10)
                if child.is_alive():child.terminate();child.join(5)
            self.assertEqual(child.exitcode,0)


if __name__=='__main__':unittest.main()
