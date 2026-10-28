import json
import os
from pathlib import Path
import tempfile
import unittest

from .settings import load_settings, parse_settings
from .bootstrap_key import read_bootstrap_key
from .state import StorageError


def settings():
    return {'schema_version':1,'company_id':37,'principal_subject':'fixture-owner',
        'telegram_user_id':'123456789','reply_chat_id':'123456789','hermes_profile':None,
        'writer_uid':10000,'result_gid':10000,
        'worker':{'inbox':'/fixture/host/requests','private':'/fixture/private',
                  'results':'/fixture/host/results','admissions':'/fixture/host/admissions'},
        'gateway':{'inbox':'/fixture/container/requests','admissions':'/fixture/container/admissions'}}


class SettingsTests(unittest.TestCase):
    def test_v2_broker_queue_is_root_owned_with_separate_gateway_uid(self):
        value={**settings(),'schema_version':2,'writer_uid':0,'gateway_uid':10000}
        parsed=parse_settings(value)
        self.assertEqual(parsed.queue.writer_uid,0);self.assertEqual(parsed.gateway_uid,10000)
        for field,wrong in (('gateway_uid',0),('writer_uid',10000),('schema_version',3)):
            with self.subTest(field=field),self.assertRaises(ValueError):parse_settings({**value,field:wrong})
        with self.assertRaises(ValueError):parse_settings({**settings(),'writer_uid':0})

    def test_explicit_settings_preserve_separate_host_and_container_views(self):
        config=parse_settings(settings())
        self.assertEqual(config.owner.scope.company_id,37)
        self.assertEqual(config.queue.writer_uid,10000)
        self.assertNotEqual(config.queue.inbox,config.gateway_inbox)
        self.assertNotIn('123456789',repr(config))

    def test_missing_company_and_unknown_secret_fields_have_no_fallback(self):
        for change in ('missing_company','secret','zero_company','boolean_company'):
            value=settings()
            if change=='missing_company':del value['company_id']
            elif change=='secret':value['signing_key']='MUST_NOT_BE_CONFIG'
            else:value['company_id']=0 if change=='zero_company' else True
            with self.subTest(change=change),self.assertRaises(ValueError):parse_settings(value)

    def test_privileged_gateway_and_different_recipient_are_rejected(self):
        for key,value in (('writer_uid',0),('result_gid',0),('reply_chat_id','987654321')):
            config=settings();config[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):parse_settings(config)

    def test_nested_or_traversal_namespaces_are_rejected(self):
        for private in ('relative','/fixture/host/requests/private','/fixture/../other'):
            value=settings();value['worker']['private']=private
            with self.subTest(path=private),self.assertRaises(ValueError):parse_settings(value)

    def test_protected_file_is_loaded_but_world_writable_file_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'bridge.json';path.write_text(json.dumps(settings()));path.chmod(0o600)
            loaded=load_settings(path,trusted_root=root,expected_uid=os.geteuid())
            self.assertEqual(loaded.owner.scope.company_id,37)
            path.chmod(0o666)
            with self.assertRaises(StorageError):load_settings(path,trusted_root=root,expected_uid=os.geteuid())

    def test_symlink_writable_parent_and_wrong_owner_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sub=root/'config';sub.mkdir(mode=0o700)
            path=sub/'bridge.json';path.write_text(json.dumps(settings()));path.chmod(0o600)
            link=sub/'link.json';link.symlink_to(path)
            with self.assertRaises(StorageError):load_settings(link,trusted_root=root,expected_uid=os.geteuid())
            with self.assertRaises(StorageError):load_settings(path,trusted_root=root,expected_uid=os.geteuid()+1)
            sub.chmod(0o777)
            with self.assertRaises(StorageError):load_settings(path,trusted_root=root,expected_uid=os.geteuid())

    def test_duplicate_configuration_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'bridge.json'
            path.write_text('{"schema_version":1,"schema_version":1}');path.chmod(0o600)
            with self.assertRaises(StorageError):load_settings(path,trusted_root=root,expected_uid=os.geteuid())


class KeyDescriptorTests(unittest.TestCase):
    def test_unclosed_writer_cannot_block_bootstrap_indefinitely(self):
        reader,writer=os.pipe()
        try:
            with self.assertRaisesRegex(ValueError,'bootstrap_key_timeout'):
                read_bootstrap_key(reader,expected_uid=os.geteuid(),timeout_seconds=1)
            with self.assertRaises(OSError):os.fstat(reader)
        finally:os.close(writer)

    def test_pipe_key_is_redacted_and_descriptor_is_closed(self):
        reader,writer=os.pipe()
        os.write(writer,b'x'*32);os.close(writer)
        secret=read_bootstrap_key(reader,expected_uid=os.geteuid())
        self.assertEqual(secret.material,b'x'*32)
        self.assertNotIn('xxxxxxxx',repr(secret))
        with self.assertRaises(OSError):os.fstat(reader)

    def test_weak_or_oversized_key_closes_descriptor_without_echoing_bytes(self):
        for raw in (b'weak',b'x'*65):
            reader,writer=os.pipe();os.write(writer,raw);os.close(writer)
            with self.assertRaises(ValueError) as caught:read_bootstrap_key(reader,expected_uid=os.geteuid())
            self.assertNotIn(raw.decode(),str(caught.exception))
            with self.assertRaises(OSError):os.fstat(reader)

    def test_regular_key_file_is_not_anonymous_bootstrap_input(self):
        with tempfile.TemporaryFile() as file:
            file.write(b'x'*32);file.seek(0);fd=os.dup(file.fileno())
            with self.assertRaises(ValueError):read_bootstrap_key(fd,expected_uid=os.geteuid())
            with self.assertRaises(OSError):os.fstat(fd)

    def test_wrong_owner_pipe_is_rejected_and_closed(self):
        reader,writer=os.pipe();os.write(writer,b'x'*32);os.close(writer)
        with self.assertRaises(ValueError):read_bootstrap_key(reader,expected_uid=os.geteuid()+1)
        with self.assertRaises(OSError):os.fstat(reader)


if __name__=='__main__':unittest.main()
