"""Upgrade source attestation: manual edits and foreign files are preserved."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import upgrade_review as upgrade
from .test_runtime_config import policies
from ..source_package import REQUIRED


class UpgradeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.stage=self.base/'stage';self.stage.mkdir(mode=0o700)
        self.repository=self.stage/'repository';self.repository.mkdir()
        self.installed=self.base/'installed';self.installed.mkdir()
        self.source=self.stage/'source';self.source.mkdir()
        self.git('init','--quiet')
        for name in REQUIRED:
            for root in (self.repository,self.installed):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('pass\n');path.chmod(0o644)
        self.git('add','.');self.git('-c','user.name=Fixture','-c','user.email=fixture@invalid','commit','--quiet','-m','baseline')
        self.previous=self.git('rev-parse','HEAD').decode().strip()
        (self.repository/'jev_agent/tender_finder/host_service.py').write_text('"""changed fixture"""\n')
        path=self.repository/'jev_agent/tender_finder/fixture_new.py';path.write_text('pass\n')
        self.git('add','.');self.git('-c','user.name=Fixture','-c','user.email=fixture@invalid','commit','--quiet','-m','candidate')
        self.commit=self.git('rev-parse','HEAD').decode().strip()
        for path in self.repository.rglob('*.py'):
            target=self.source/path.relative_to(self.repository);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(path.read_bytes());target.chmod(0o644)
        self.legacy=self.base/'bridge.json';old,_=policies();self.legacy.write_text(json.dumps(old));self.legacy.chmod(0o600)
        self.ci=Mock(return_value='https://github.com/example/fixture')
        self.peer=Mock(return_value=SimpleNamespace(uid=10000,gid=10000))

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repository),*args],stderr=subprocess.DEVNULL)

    def inspect(self):
        with patch.object(upgrade,'BASELINE',self.previous):
            # default arguments bind at import; pass the fixture manifest seam.
            manifest=upgrade.baseline_manifest(self.repository,self.previous)
            with patch.object(upgrade,'baseline_manifest',return_value=manifest):
                return upgrade.review(self.stage,self.commit,_uid=os.geteuid(),_installed=self.installed,
                    _trusted_root=self.base,_legacy=self.legacy,_legacy_root=self.base,_ci=self.ci,_peer=self.peer)

    def test_verified_review_keeps_source_and_legacy_policy_unchanged(self):
        before=upgrade.baseline_manifest(self.repository,self.previous);legacy=self.legacy.read_bytes()
        result=self.inspect()
        self.assertTrue(result['installed_source_verified']);self.assertFalse(result['installation_ready'])
        self.assertEqual(result['changed_files'],1);self.assertEqual(result['added_files'],1)
        self.assertEqual(upgrade.installed_manifest(self.installed,before,uid=os.geteuid(),trusted_root=self.base),before)
        self.assertEqual(self.legacy.read_bytes(),legacy)
        manifest=json.loads((Path(result['review_directory'])/'UPGRADE_REVIEW.json').read_text())
        self.assertEqual(manifest['baseline_commit'],self.previous)
        runtime=json.loads((Path(result['review_directory'])/'policy/runtime.json').read_text())
        self.assertEqual(runtime['bridge']['company_id'],37)
        self.assertEqual(runtime['bridge']['telegram_user_id'],'123456789')

    def test_manual_edit_blocks_before_network_or_review_creation(self):
        path=self.installed/'jev_agent/tender_finder/host_service.py';path.write_text('manual fix\n')
        with self.assertRaisesRegex(ValueError,'differs_from_pinned_baseline'):self.inspect()
        self.ci.assert_not_called();self.peer.assert_not_called()
        self.assertEqual(path.read_text(),'manual fix\n')
        self.assertFalse((self.stage/'commercial-upgrade-review').exists())

    def test_foreign_file_is_never_read_or_removed(self):
        path=self.installed/'private.key';path.write_text('PRIVATE_TOKEN')
        original=os.open
        def opened(name,*args,**kwargs):
            self.assertNotEqual(Path(name),path)
            return original(name,*args,**kwargs)
        with patch.object(os,'open',side_effect=opened),self.assertRaisesRegex(ValueError,'unreviewed_installed_file'):
            self.inspect()
        self.assertEqual(path.read_text(),'PRIVATE_TOKEN');self.ci.assert_not_called()

    def test_symlink_and_hardlink_are_rejected_without_following(self):
        path=self.installed/'jev_agent/tender_finder/host_service.py';path.unlink();path.symlink_to(self.legacy)
        with self.assertRaisesRegex(ValueError,'protected_source_only'):self.inspect()
        path.unlink();os.link(self.legacy,path)
        with self.assertRaisesRegex(ValueError,'unreviewed_installed_file'):self.inspect()

    def test_failed_exact_ci_or_changed_plugin_cannot_produce_plan(self):
        self.ci.side_effect=ValueError('exact_source_ci_unconfirmed')
        with self.assertRaisesRegex(ValueError,'exact_source_ci'):self.inspect()
        self.assertFalse((self.stage/'commercial-upgrade-review').exists())
        old={upgrade.PLUGIN:'a'*64};new={upgrade.PLUGIN:'b'*64}
        with self.assertRaisesRegex(ValueError,'plugin_mount_upgrade'):upgrade.change_plan(old,new)

    def test_existing_review_is_preserved(self):
        self.inspect();sentinel=self.stage/'commercial-upgrade-review'/'sentinel';sentinel.write_text('keep')
        with self.assertRaisesRegex(ValueError,'existing_review_preserved'):self.inspect()
        self.assertEqual(sentinel.read_text(),'keep')

    def test_source_change_during_ci_lookup_blocks_review(self):
        path=self.installed/'jev_agent/tender_finder/host_service.py'
        def change(commit):
            path.write_text('concurrent manual fix\n');return 'https://github.com/example/fixture'
        self.ci.side_effect=change
        with self.assertRaisesRegex(ValueError,'differs_from_pinned_baseline'):self.inspect()
        self.assertFalse((self.stage/'commercial-upgrade-review').exists())
        self.assertEqual(path.read_text(),'concurrent manual fix\n')

    def test_different_gateway_never_rebinds_owner(self):
        self.peer.return_value=SimpleNamespace(uid=12345,gid=10000)
        with self.assertRaisesRegex(ValueError,'observed_gateway_identity'):self.inspect()
        self.ci.assert_not_called()
        self.assertFalse((self.stage/'commercial-upgrade-review').exists())
