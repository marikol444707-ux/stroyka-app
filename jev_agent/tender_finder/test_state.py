from contextlib import contextmanager
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import stat
import tempfile
import unittest

from .state import RequestBusy, RequestConflict, RequestLedger, Scope, StorageError, publish_result_once

SCOPE = Scope(17, 'synthetic-owner')
ID = 'search-synthetic-001'
HASH = hashlib.sha256(b'synthetic normalized request').hexdigest()
RESULT = {'ok':True,'request_id':ID,'company_id':17,'tenders':[]}


def crash_after_claim(path):
    with RequestLedger(path,SCOPE) as ledger:
        with ledger.claim(ID,HASH):
            os._exit(7)


def simultaneous_claim(path, pipe):
    try:
        with RequestLedger(path,SCOPE) as ledger:
            with ledger.claim(ID,HASH) as claim:
                pipe.send(claim.action)
    except RequestBusy:
        pipe.send('busy')
    finally:
        pipe.close()


@contextmanager
def folders():
    with tempfile.TemporaryDirectory(prefix='jev-ledger-fixture-') as directory:
        root=Path(directory)
        private=root/'private';private.mkdir(mode=0o700)
        public=root/'results';public.mkdir(mode=0o750);public.chmod(0o750)
        yield private,public


class DurableReceiptTests(unittest.TestCase):
    def test_completed_result_is_replayed_after_restart_without_second_execution(self):
        executions=[]
        with folders() as (private,_):
            for _ in range(2):
                with RequestLedger(private,SCOPE) as ledger:
                    with ledger.claim(ID,HASH) as claim:
                        if claim.action=='execute':
                            executions.append(1);claim.complete(RESULT)
                        self.assertEqual(claim.result,RESULT)
            self.assertEqual(executions,[1])

    def test_same_id_different_payload_does_not_overwrite_previous_receipt(self):
        with folders() as (private,_):
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:claim.complete(RESULT)
            before={path.name:path.read_bytes() for path in private.glob('*.json')}
            with RequestLedger(private,SCOPE) as ledger,self.assertRaises(RequestConflict):
                with ledger.claim(ID,'f'*64):self.fail('Must not execute')
            self.assertEqual(before,{path.name:path.read_bytes() for path in private.glob('*.json')})

    def test_another_company_or_principal_cannot_replay_this_receipt(self):
        with folders() as (private,_):
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:claim.complete(RESULT)
            for scope in (Scope(18,'synthetic-owner'),Scope(17,'another-owner')):
                with RequestLedger(private,scope) as ledger:
                    with ledger.claim(ID,HASH) as claim:
                        self.assertEqual(claim.action,'execute')
                        self.assertIsNone(claim.result)
                        claim.complete({'status':'failed','request_id':ID,'company_id':scope.company_id})

    def test_real_process_crash_is_explicit_and_never_automatically_reexecutes(self):
        with folders() as (private,_):
            process=multiprocessing.get_context('fork').Process(target=crash_after_claim,args=(str(private),))
            process.start();process.join(10)
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode,7)
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:
                    self.assertEqual(claim.action,'interrupted')
                    self.assertEqual(claim.result['reason'],'execution_interrupted')
                    self.assertEqual(claim.result['status'],'failed')
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:
                    self.assertEqual(claim.action,'cached')
                    self.assertEqual(claim.result['reason'],'execution_interrupted')

    def test_concurrent_process_cannot_claim_a_running_request(self):
        with folders() as (private,_),RequestLedger(private,SCOPE) as ledger:
            with ledger.claim(ID,HASH) as claim:
                context=multiprocessing.get_context('fork');receive,send=context.Pipe(duplex=False)
                process=context.Process(target=simultaneous_claim,args=(str(private),send))
                process.start();send.close()
                self.assertTrue(receive.poll(10));self.assertEqual(receive.recv(),'busy')
                process.join(10);self.assertEqual(process.exitcode,0)
                receive.close();claim.complete(RESULT)

    def test_callback_error_is_cached_without_its_secret_message(self):
        with folders() as (private,_):
            with self.assertRaisesRegex(RuntimeError,'PRIVATE'):
                with RequestLedger(private,SCOPE) as ledger:
                    with ledger.claim(ID,HASH):raise RuntimeError('PRIVATE_TOKEN')
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:
                    self.assertEqual(claim.action,'cached')
                    self.assertEqual(claim.result['reason'],'execution_failed')
                    self.assertNotIn('PRIVATE',json.dumps(claim.result))

    def test_wrong_company_result_is_never_cached_as_success(self):
        with folders() as (private,_):
            with self.assertRaises(StorageError):
                with RequestLedger(private,SCOPE) as ledger:
                    with ledger.claim(ID,HASH) as claim:claim.complete({**RESULT,'company_id':99})
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:self.assertEqual(claim.result['status'],'failed')

    def test_corrupt_receipt_is_not_repaired_or_replaced(self):
        with folders() as (private,_):
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:claim.complete(RESULT)
            record=next(private.glob('*.json'));record.write_bytes(b'{"corrupt":true}')
            with RequestLedger(private,SCOPE) as ledger,self.assertRaises(StorageError):
                with ledger.claim(ID,HASH):self.fail('Corrupt state must stop')
            self.assertEqual(record.read_bytes(),b'{"corrupt":true}')

    def test_paths_and_scope_must_be_protected_and_never_inferred(self):
        with folders() as (private,_):
            private.chmod(0o750)
            with self.assertRaises(StorageError):RequestLedger(private,SCOPE)
        for scope in (Scope(True,'owner'),Scope(0,'owner'),Scope(1,'')):
            with self.assertRaises(StorageError):scope.key()
        with folders() as (private,_),RequestLedger(private,SCOPE) as ledger:
            for identifier in ('../id','/tmp/job','x;cmd'):
                with self.assertRaises(StorageError):
                    with ledger.claim(identifier,HASH):self.fail('Unsafe ID')

    def test_completed_receipt_survives_crash_before_publication(self):
        with folders() as (private,public):
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:claim.complete(RESULT)
            self.assertFalse((public/(ID+'.json')).exists())
            with RequestLedger(private,SCOPE) as ledger:
                with ledger.claim(ID,HASH) as claim:
                    self.assertEqual(claim.action,'cached')
                    self.assertTrue(publish_result_once(public,ID,claim.result,result_gid=os.getegid()))
            self.assertEqual(json.loads((public/(ID+'.json')).read_bytes()),RESULT)


class ResultPublicationTests(unittest.TestCase):
    def test_atomic_publication_is_idempotent_and_has_explicit_group_permissions(self):
        with folders() as (_,public):
            self.assertTrue(publish_result_once(public,ID,RESULT,result_gid=os.getegid()))
            self.assertFalse(publish_result_once(public,ID,RESULT,result_gid=os.getegid()))
            info=(public/(ID+'.json')).stat()
            self.assertEqual(stat.S_IMODE(info.st_mode),0o640)
            self.assertEqual(info.st_gid,os.getegid())
            self.assertEqual([path.name for path in public.iterdir()],[ID+'.json'])

    def test_conflicting_result_never_overwrites_completed_response(self):
        with folders() as (_,public):
            publish_result_once(public,ID,RESULT,result_gid=os.getegid())
            original=(public/(ID+'.json')).read_bytes()
            with self.assertRaises(RequestConflict):
                publish_result_once(public,ID,{**RESULT,'status':'rejected'},result_gid=os.getegid())
            self.assertEqual((public/(ID+'.json')).read_bytes(),original)

    def test_symlink_does_not_read_or_modify_its_target(self):
        with folders() as (private,public):
            target=private/'secret';target.write_text('PRIVATE')
            (public/(ID+'.json')).symlink_to(target)
            with self.assertRaises((StorageError,OSError)):
                publish_result_once(public,ID,RESULT,result_gid=os.getegid())
            self.assertEqual(target.read_text(),'PRIVATE')

    def test_already_existing_unreadable_result_is_not_silently_called_published(self):
        with folders() as (_,public):
            publish_result_once(public,ID,RESULT,result_gid=os.getegid())
            (public/(ID+'.json')).chmod(0o600)
            with self.assertRaises(StorageError):
                publish_result_once(public,ID,RESULT,result_gid=os.getegid())
            self.assertEqual(stat.S_IMODE((public/(ID+'.json')).stat().st_mode),0o600)

    def test_oversized_result_is_not_published(self):
        with folders() as (_,public):
            with self.assertRaisesRegex(StorageError, 'result_size_limit'):
                publish_result_once(public,ID,{'request_id':ID,'data':'x'*(1024*1024)},result_gid=os.getegid())
            self.assertEqual(list(public.iterdir()), [])

    def test_restrictive_umask_cannot_make_results_unreadable_to_configured_group(self):
        with folders() as (private,public):
            previous=os.umask(0o777)
            try:
                with RequestLedger(private,SCOPE) as ledger:
                    with ledger.claim(ID,HASH) as claim:claim.complete(RESULT)
                publish_result_once(public,ID,RESULT,result_gid=os.getegid())
            finally:os.umask(previous)
            self.assertEqual(stat.S_IMODE((public/(ID+'.json')).stat().st_mode),0o640)
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode)==0o600 for path in private.iterdir()))


if __name__=='__main__':
    unittest.main()
