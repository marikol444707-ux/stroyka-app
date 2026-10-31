"""Protected launcher: python3 -I -B <this file> broker|worker|service <explicit args>.

No files, keys, services or schedules are provisioned here. -I and root-owned
code are mandatory; bytecode writes stay disabled so host startup cannot pollute
the source-only package checked by the unprivileged Hermes builtin loader.
"""
import os
import sys

sys.dont_write_bytecode=True
if os.geteuid()!=0 or not sys.flags.isolated:
    raise SystemExit('isolated_root_host_launcher_required')
if len(sys.argv)<2 or sys.argv[1] not in ('broker','worker','service','systemd-service','commercial-service'):
    raise SystemExit('explicit_host_operation_required')

from pathlib import Path
import stat


def _verify_package(root,*,_uid=0,_trusted_root=Path('/')):
    if root.resolve(strict=True)!=root:
        raise RuntimeError('protected_host_implementation_required')
    for directory in (root,*root.parents):
        info=directory.stat()
        if info.st_uid!=_uid or info.st_mode & 0o022:
            raise RuntimeError('protected_host_implementation_required')
        if directory==_trusted_root:break
    for index,entry in enumerate(root.rglob('*')):
        info=entry.lstat()
        if (index>=2048 or entry.name in ('__pycache__','.git') or entry.suffix=='.pyc'
                or info.st_uid!=_uid or info.st_mode & 0o022
                or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
                or stat.S_ISREG(info.st_mode) and info.st_nlink!=1):
            raise RuntimeError('protected_source_only_host_package_required')

_root=Path(__file__).resolve().parents[3]
_verify_package(_root)
sys.path.insert(0,str(_root))
_existing=sys.modules.get('jev_agent')
if _existing is not None and getattr(_existing,'__file__',None)!=str(_root/'jev_agent/__init__.py'):
    raise SystemExit('foreign_host_package_refused')

if sys.argv[1]=='broker':
    from jev_agent.tender_finder.broker_service import main
    raise SystemExit(main(sys.argv[2:]))
if sys.argv[1]=='service':
    from jev_agent.tender_finder.host_service import main
    raise SystemExit(main(sys.argv[2:]))
if sys.argv[1]=='systemd-service':
    from jev_agent.tender_finder.systemd_bootstrap import main
    raise SystemExit(main(sys.argv[2:]))
if sys.argv[1]=='commercial-service':
    from jev_agent.tender_finder.commercial.service import main
    raise SystemExit(main(sys.argv[2:]))
from jev_agent.tender_finder.__main__ import main
raise SystemExit(main(['host-pass',*sys.argv[2:]]))
