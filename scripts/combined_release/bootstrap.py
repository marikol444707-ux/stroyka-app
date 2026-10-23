"""Self-contained Python zipapp entry: stage private code; default only preflight."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import socket
import stat
import sys
import tempfile
import zipfile

APPLICATION_CI_RUN = '39918989943'
MAX_BYTES = 128*1024*1024

class PackageError(RuntimeError):pass

def unpack(archive, parent):
    """Validate ALL members before creating a directory; never extract links."""
    with zipfile.ZipFile(archive) as source:
        members=source.infolist();names=[x.filename for x in members]
        if len(names)!=len(set(names)) or len(names)>1024:raise PackageError('INVALID_ARCHIVE_INVENTORY')
        if sum(x.file_size for x in members)>MAX_BYTES:raise PackageError('ARCHIVE_TOO_LARGE')
        for item in members:
            parts=PurePosixPath(item.filename).parts
            if (not parts or item.filename.startswith('/') or '\\' in item.filename
                    or any(x in ('.','..','') for x in item.filename.split('/'))
                    or stat.S_ISLNK(item.external_attr>>16)
                    or item.is_dir()):raise PackageError('UNSAFE_ARCHIVE_MEMBER')
            if item.filename!='__main__.py' and not item.filename.startswith('package/'):
                raise PackageError('UNEXPECTED_ARCHIVE_MEMBER')
        manifest=json.loads(source.read('package/manifest.json'))
        expected=manifest['package_files']
        wanted={'__main__.py','package/manifest.json','package/SHA256SUMS'}|{'package/'+n for n in expected}
        if set(names)!=wanted:raise PackageError('PACKAGE_MEMBERSHIP_MISMATCH')
        for name,digest in expected.items():
            if hashlib.sha256(source.read('package/'+name)).hexdigest()!=digest:
                raise PackageError('PACKAGE_CONTENT_MISMATCH')
        if source.read('__main__.py')!=source.read('package/bootstrap.py'):
            raise PackageError('BOOTSTRAP_BINDING_MISMATCH')
        # Retain staged code: recovery must use this exact manifest after an error.
        destination=Path(tempfile.mkdtemp(prefix='stroyka-combined-package-',dir=parent))
        os.chmod(destination,0o700)
        for item in members:
            if item.filename=='__main__.py':continue
            relative=item.filename[len('package/'):]
            target=destination/relative
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as out:out.write(source.read(item.filename))
        return destination

def main():
    if os.geteuid()!=0 or socket.gethostname().split('.')[0]!='msk-1-vm-zh4n':
        print('STOP: WRONG_HOST_OR_USER');return 1
    try:
        os.umask(0o077)
        destination=unpack(Path(sys.argv[0]).resolve(),Path('/root'))
        print('STAGED_PACKAGE='+str(destination),flush=True)
        args=sys.argv[1:] or ['--preflight']
        if '--apply' in args and '--ci-run-id' not in args:args+=['--ci-run-id',APPLICATION_CI_RUN]
        os.execv(sys.executable,[sys.executable,'-E','-B',str(destination/'install.py'),*args])
    except Exception as error:
        print('STOP: '+(str(error) if isinstance(error,PackageError) else type(error).__name__))
        return 1

if __name__=='__main__':raise SystemExit(main())
