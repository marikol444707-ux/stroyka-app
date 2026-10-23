import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from durable_files import Stop, Transaction, digest


class DurableFilesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root, self.evidence = self.base / 'app', self.base / 'evidence'
        self.root.mkdir()
        self.evidence.mkdir(mode=0o700)
        (self.root / 'old.py').write_bytes(b'old')
        (self.root / 'old.py').chmod(0o640)
        self.payload = {'old.py': b'new', 'static/new.js': b'frontend'}
        self.manifest = {name: {'before_sha256': digest(b'old') if name == 'old.py' else None,
                                'after_sha256': digest(body)} for name, body in self.payload.items()}
        self.tx = Transaction(self.root, self.evidence, self.manifest)

    def reload(self):
        return Transaction.load(self.root, self.evidence)

    def assert_before(self):
        self.assertEqual((self.root / 'old.py').read_bytes(), b'old')
        self.assertEqual(stat.S_IMODE((self.root / 'old.py').stat().st_mode), 0o640)
        self.assertFalse((self.root / 'static/new.js').exists())

    def crash_after_replace(self, target='old.py'):
        original = self.tx._replace_file
        def crash(name, action):
            original(name, action)
            if name == target:
                raise OSError('injected after atomic rename')
        return patch.object(self.tx, '_replace_file', side_effect=crash)

    def foreign_replace(self, target):
        foreign = self.root / 'foreign'
        foreign.write_bytes(target.read_bytes())
        foreign.chmod(stat.S_IMODE(target.stat().st_mode))
        os.replace(foreign, target)

    def test_success_reload_verify_repeated_rollback(self):
        self.tx.prepare().apply(self.payload)
        self.assertTrue(self.reload().verify_after())
        self.reload().rollback()
        self.assert_before()
        self.reload().rollback()
        self.assert_before()
        self.assertTrue((self.root / 'static').is_dir())

    def test_modes_owner_and_private_evidence(self):
        original = (self.root / 'old.py').stat()
        self.tx.prepare().apply(self.payload)
        info = (self.root / 'old.py').stat()
        self.assertEqual((stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid), (0o640, original.st_uid, original.st_gid))
        for path in self.tx.directory.rglob('*'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)
        self.reload().rollback()
        info = (self.root / 'old.py').stat()
        self.assertEqual((info.st_uid, info.st_gid), (original.st_uid, original.st_gid))

    def test_apply_intent_durable_before_rename_and_cleanup_own_temp(self):
        self.tx.prepare()
        def observe(name, action):
            disk = json.loads(self.tx.journal.read_text())['entries'][name]['apply']
            self.assertFalse(disk['done'])
            self.assertEqual(disk['file'], self.tx._read(disk['temp'])[0])
            raise OSError('crash before rename')
        with patch.object(self.tx, '_replace_file', side_effect=observe), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        self.assert_before()
        self.reload().rollback()
        self.assertFalse(list(self.root.rglob('.release-*')))

    def test_apply_after_rename_crash_recovery_by_own_inode(self):
        self.tx.prepare()
        with self.crash_after_replace(), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        self.assertEqual((self.root / 'old.py').read_bytes(), b'new')
        self.assertFalse(json.loads(self.tx.journal.read_text())['entries']['old.py']['apply']['done'])
        self.reload().rollback()
        self.assert_before()

    def test_resume_apply_after_rename(self):
        self.tx.prepare()
        with self.crash_after_replace(), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        self.reload().apply(self.payload).verify_after()
        self.reload().rollback()
        self.assert_before()

    def test_resume_apply_before_rename(self):
        self.tx.prepare()
        with patch.object(self.tx, '_replace_file', side_effect=OSError('before')), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        self.reload().apply(self.payload).verify_after()

    def test_parent_fsync_failure_after_target_rename(self):
        self.tx.prepare()
        original_replace, original_fsync = os.replace, os.fsync
        armed = [False]
        def replace(source, target, *args, **kwargs):
            result = original_replace(source, target, *args, **kwargs)
            if target == 'old.py': armed[0] = True
            return result
        def fsync(fd):
            if armed[0]:
                armed[0] = False
                raise OSError('fsync after rename')
            return original_fsync(fd)
        with patch('durable_files.os.replace', side_effect=replace), patch('durable_files.os.fsync', side_effect=fsync), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        self.reload().rollback()
        self.assert_before()

    def test_journal_save_failure_does_not_create_unrecorded_mutation(self):
        self.tx.prepare()
        original, calls = self.tx._save, [0]
        def fail_intent():
            calls[0] += 1
            original()
            if calls[0] == 2: raise OSError('intent save fault')
        with patch.object(self.tx, '_save', side_effect=fail_intent), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        self.assert_before()
        self.reload().rollback()
        self.assert_before()

    def test_rollback_restore_crash_after_rename(self):
        self.tx.prepare().apply(self.payload)
        with self.crash_after_replace(), self.assertRaises(OSError):
            self.tx.rollback()
        self.assert_before()
        self.reload().rollback()
        self.assert_before()

    def test_rollback_remove_crash_after_unlink(self):
        self.tx.prepare().apply(self.payload)
        original = os.unlink
        def unlink(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == 'new.js': raise OSError('after removal')
            return result
        with patch('durable_files.os.unlink', side_effect=unlink), self.assertRaises(OSError):
            self.tx.rollback()
        self.assertFalse((self.root / 'static/new.js').exists())
        self.reload().rollback()
        self.assert_before()

    def test_rollback_crash_before_restore_rename(self):
        self.tx.prepare().apply(self.payload)
        with patch.object(self.tx, '_replace_file', side_effect=OSError('before restore')), self.assertRaises(OSError):
            self.tx.rollback()
        self.reload().rollback()
        self.assert_before()

    def test_rollback_all_path_preflight_chmod_refusal(self):
        self.tx.prepare().apply(self.payload)
        (self.root / 'old.py').chmod(0o600)
        with self.assertRaises(Stop): self.tx.rollback()
        self.assertEqual((self.root / 'static/new.js').read_bytes(), b'frontend')
        self.assertEqual((self.root / 'old.py').read_bytes(), b'new')

    def test_apply_all_path_preflight_chmod_refusal(self):
        self.tx.prepare()
        (self.root / 'old.py').chmod(0o600)
        with self.assertRaises(Stop): self.tx.apply(self.payload)
        self.assertEqual((self.root / 'old.py').read_bytes(), b'old')
        self.assertFalse((self.root / 'static').exists())

    def test_foreign_identical_new_file_not_deleted(self):
        self.tx.prepare().apply(self.payload)
        self.foreign_replace(self.root / 'static/new.js')
        with self.assertRaises(Stop): self.tx.rollback()
        self.assertEqual((self.root / 'static/new.js').read_bytes(), b'frontend')
        self.assertEqual((self.root / 'old.py').read_bytes(), b'new')

    def test_foreign_identical_existing_file_not_overwritten(self):
        self.tx.prepare().apply(self.payload)
        self.foreign_replace(self.root / 'old.py')
        with self.assertRaises(Stop): self.reload()
        self.assertEqual((self.root / 'old.py').read_bytes(), b'new')

    def test_foreign_identical_restored_file_not_overwritten(self):
        self.tx.prepare().apply(self.payload).rollback()
        self.foreign_replace(self.root / 'old.py')
        with self.assertRaises(Stop): self.tx.rollback()
        self.assertEqual((self.root / 'old.py').read_bytes(), b'old')

    def test_before_content_change_refused(self):
        (self.root / 'old.py').write_bytes(b'changed')
        with self.assertRaises(Stop): self.tx.prepare()
        self.assertFalse(self.tx.directory.exists())

    def test_payload_mismatch_before_any_write(self):
        self.tx.prepare()
        with self.assertRaises(Stop): self.tx.apply({**self.payload, 'static/new.js': b'wrong'})
        self.assert_before()

    def test_corrupted_backup_blocks_all_rollback_writes(self):
        self.tx.prepare().apply(self.payload)
        (self.tx.directory / 'backups/00000000').write_bytes(b'corrupted')
        with self.assertRaises(Stop): self.tx.rollback()
        self.assertEqual((self.root / 'static/new.js').read_bytes(), b'frontend')
        self.assertEqual((self.root / 'old.py').read_bytes(), b'new')

    def test_symlink_root_ancestor_refused(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(Stop): Transaction(alias / 'app', self.evidence, self.manifest)

    def test_symlink_target_ancestor_refused(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'new.js').write_bytes(b'outside')
        (self.root / 'static').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(Stop): self.tx.prepare()
        self.assertEqual((outside / 'new.js').read_bytes(), b'outside')

    def test_symlink_leaf_refused(self):
        outside = self.base / 'outside'
        outside.write_bytes(b'old')
        (self.root / 'old.py').unlink()
        (self.root / 'old.py').symlink_to(outside)
        with self.assertRaises(Stop): self.tx.prepare()
        self.assertEqual(outside.read_bytes(), b'old')

    def test_replaced_root_refused_on_load(self):
        self.tx.prepare()
        self.root.rename(self.base / 'original-root')
        self.root.mkdir()
        (self.root / 'old.py').write_bytes(b'old')
        with self.assertRaises(Stop): self.reload()

    def test_public_evidence_refused(self):
        self.evidence.chmod(0o755)
        with self.assertRaises(Stop): Transaction(self.root, self.evidence, self.manifest)

    def test_foreign_identical_temp_not_cleaned(self):
        self.tx.prepare()
        with patch.object(self.tx, '_replace_file', side_effect=OSError('before')), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        target = self.root / self.tx.state['entries']['old.py']['apply']['temp']
        self.foreign_replace(target)
        with self.assertRaises(Stop): self.tx.rollback()
        self.assertTrue(target.exists())
        self.assert_before()

    def test_file_payload_and_custom_order(self):
        source = self.base / 'payload'
        source.write_bytes(b'frontend')
        self.tx.prepare().apply({**self.payload, 'static/new.js': source}, order=['static/new.js', 'old.py'])
        self.assertTrue(self.tx.verify_after())
        self.tx.rollback()
        self.assert_before()

    def test_invalid_names_and_duplicate_order_refused(self):
        for name in ('../outside', '/outside', 'a//b', 'a/./b'):
            with self.subTest(name=name), self.assertRaises(Stop):
                Transaction(self.root, self.evidence, {name: self.manifest['old.py']})
        self.tx.prepare()
        with self.assertRaises(Stop): self.tx.apply(self.payload, ['old.py', 'old.py'])
        self.assert_before()

    def test_no_recursive_cleanup_other_files_or_directories(self):
        self.tx.prepare().apply(self.payload)
        unrelated = self.root / 'static/other.js'
        unrelated.write_bytes(b'unrelated')
        self.tx.rollback()
        self.assertEqual(unrelated.read_bytes(), b'unrelated')
        self.assertTrue(unrelated.parent.is_dir())
        self.assert_before()


    def test_malformed_journal_cannot_name_unrelated_file_as_owned_temp(self):
        self.tx.prepare()
        with patch.object(self.tx, '_replace_file', side_effect=OSError('before')), self.assertRaises(OSError):
            self.tx.apply(self.payload)
        state = json.loads(self.tx.journal.read_text())
        state['entries']['old.py']['apply']['temp'] = 'unrelated.txt'
        self.tx.journal.write_text(json.dumps(state))
        with self.assertRaises(Stop): self.reload()
        self.assert_before()

    def test_malformed_journal_cannot_change_expected_content_hash(self):
        self.tx.prepare().apply(self.payload)
        state = json.loads(self.tx.journal.read_text())
        state['entries']['old.py']['apply']['file']['sha256'] = digest(b'foreign')
        self.tx.journal.write_text(json.dumps(state))
        with self.assertRaises(Stop): self.reload()

    def test_last_moment_foreign_target_replacement_is_refused(self):
        self.tx.prepare()
        original = self.tx._replace_file
        def race(name, action):
            self.foreign_replace(self.root / name)
            return original(name, action)
        with patch.object(self.tx, '_replace_file', side_effect=race), self.assertRaises(Stop):
            self.tx.apply(self.payload)
        self.assert_before()


if __name__ == '__main__':
    unittest.main()
