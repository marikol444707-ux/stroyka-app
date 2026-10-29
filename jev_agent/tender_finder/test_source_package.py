import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from . import source_package as package


class SourcePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repository=self.root/'repository';self.repository.mkdir()
        def git(*args):
            return subprocess.check_output(['git','-C',str(self.repository),*args],stderr=subprocess.DEVNULL)
        self.git=git;git('init','--quiet')
        for name in package.REQUIRED:
            path=self.repository/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('raise RuntimeError("PACKAGE_SOURCE_MUST_NOT_EXECUTE")\n')
        (self.repository/'.env').write_text('SYNTHETIC_EXCLUDED_SETTING=1\n')
        git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@invalid','commit','--quiet','-m','fixture sources')
        self.archive=self.root/'source.tar.gz';self.info=package.build(self.repository,self.archive)
        self.raw=self.archive.read_bytes()

    def repack(self,mutate):
        with tarfile.open(fileobj=io.BytesIO(self.raw),mode='r:gz') as archive:
            entries=[(entry,archive.extractfile(entry).read()) for entry in archive]
        mutate(entries)
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
            for entry,data in entries:
                entry.size=len(data);archive.addfile(entry,io.BytesIO(data))
        return buffer.getvalue()

    def verified(self,raw):
        return package.verify_bytes(raw,hashlib.sha256(raw).hexdigest(),self.info['commit'])

    def test_reproducible_clean_build_excludes_configuration_and_unpacks_without_execution(self):
        second=self.root/'second.tar.gz';other=package.build(self.repository,second)
        self.assertEqual(self.raw,second.read_bytes());self.assertEqual(self.info,other)
        output=self.root/'unpack'
        result=package.verify(self.archive,self.info['sha256'],self.info['commit'],output)
        self.assertTrue(result['verified']);self.assertFalse(result['installation_ready'])
        self.assertFalse(list(output.rglob('.env')));self.assertFalse(list(output.rglob('*.pyc')))
        self.assertEqual(len(list((output/'app').rglob('*.py'))),len(package.REQUIRED))

    def test_dirty_worktree_and_existing_output_are_refused(self):
        with self.assertRaises(FileExistsError):package.build(self.repository,self.archive)
        leaf=self.repository/next(iter(package.REQUIRED));leaf.write_text('pass\n')
        with self.assertRaises(ValueError):package.build(self.repository,self.root/'dirty.tar.gz')
        self.assertFalse((self.root/'dirty.tar.gz').exists())

    def test_external_hash_and_commit_are_mandatory_before_any_unpack(self):
        output=self.root/'unpack'
        for digest,commit in (('0'*64,self.info['commit']),(self.info['sha256'],'0'*40),('',self.info['commit'])):
            with self.subTest(digest=digest[:4]),self.assertRaises(ValueError):
                package.verify(self.archive,digest,commit,output)
            self.assertFalse(output.exists())

    def test_source_tampering_and_manifest_duplicate_declarations_are_rejected(self):
        def tamper(entries):entries[1]=(entries[1][0],b'pass # changed\n')
        with self.assertRaises(ValueError):self.verified(self.repack(tamper))
        def duplicate(entries):
            value=json.loads(entries[0][1]);value['files'].append(value['files'][0])
            entries[0]=(entries[0][0],json.dumps(value).encode())
        with self.assertRaises(ValueError):self.verified(self.repack(duplicate))

    def test_traversal_links_duplicate_members_and_bytecode_names_are_refused(self):
        def traversal(entries):entries[1][0].name='../../escape.py'
        def link(entries):entries[1][0].type=tarfile.SYMTYPE;entries[1][0].linkname='/etc/passwd'
        def duplicate(entries):entries.append(entries[1])
        def bytecode(entries):entries[1][0].name='app/jev_agent/tender_finder/__pycache__/wrong.py'
        for mutation in (traversal,link,duplicate,bytecode):
            with self.subTest(mutation=mutation.__name__),self.assertRaises(ValueError):self.verified(self.repack(mutation))

    def test_oversized_compressed_stream_is_rejected_before_tar_parsing(self):
        raw=gzip.compress(b'\0'*(package.MAX_EXPANDED+300000))
        with self.assertRaisesRegex(ValueError,'expanded_source_package_limit'):self.verified(raw)

    def test_local_unpack_never_overwrites_or_targets_live_paths(self):
        existing=self.root/'existing';existing.mkdir();(existing/'keep').write_text('keep')
        with self.assertRaises(FileExistsError):package.verify(self.archive,self.info['sha256'],self.info['commit'],existing)
        self.assertEqual((existing/'keep').read_text(),'keep')
        with self.assertRaises(ValueError):package.verify(self.archive,self.info['sha256'],self.info['commit'],'/etc/stroyka-jev-review')

    def test_missing_runtime_module_is_refused_even_with_consistent_manifest(self):
        def remove(entries):
            name='app/jev_agent/tender_finder/contract.py'
            entries[:]=[(entry,data) for entry,data in entries if entry.name!=name]
            value=json.loads(entries[0][1]);value['files']=[row for row in value['files'] if row['path']!=name]
            entries[0]=(entries[0][0],json.dumps(value).encode())
        with self.assertRaises(ValueError):self.verified(self.repack(remove))


if __name__=='__main__':unittest.main()
