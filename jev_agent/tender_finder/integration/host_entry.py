"""Protected launcher: python3 -I -B <this file> broker|worker <explicit args>.

No files, keys, services or schedules are provisioned here. -I and root-owned
code are mandatory; bytecode writes stay disabled so host startup cannot pollute
the source-only package checked by the unprivileged Hermes builtin loader.
"""
import os
import sys

sys.dont_write_bytecode=True
if os.geteuid()!=0 or not sys.flags.isolated:
    raise SystemExit('isolated_root_host_launcher_required')
if len(sys.argv)<2 or sys.argv[1] not in ('broker','worker'):
    raise SystemExit('explicit_host_operation_required')

from pathlib import Path

_root=Path(__file__).resolve().parents[3]
for _directory in (_root,*_root.parents):
    _info=_directory.stat()
    if _info.st_uid!=0 or _info.st_mode & 0o022:
        raise SystemExit('protected_host_implementation_required')
sys.path.insert(0,str(_root))
_existing=sys.modules.get('jev_agent')
if _existing is not None and getattr(_existing,'__file__',None)!=str(_root/'jev_agent/__init__.py'):
    raise SystemExit('foreign_host_package_refused')

if sys.argv[1]=='broker':
    from jev_agent.tender_finder.broker_service import main
    raise SystemExit(main(sys.argv[2:]))
from jev_agent.tender_finder.__main__ import main
raise SystemExit(main(['host-pass',*sys.argv[2:]]))
