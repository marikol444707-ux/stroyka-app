"""Install ONLY as reviewed read-only tools/jev_tender_tool.py; not deployed."""
import os
from pathlib import Path
import sys

# Never load an implementation from the model-writable /opt/data directory.
_root=Path('/opt/stroyka-jev/app')
if _root.resolve(strict=True)!=_root:
    raise RuntimeError('protected_jev_implementation_required')
for _directory in (_root,*_root.parents):
    _info=_directory.stat()
    if _info.st_uid!=0 or _info.st_mode & 0o022:
        raise RuntimeError('protected_jev_implementation_required')
# Reject writable leaves/subdirectories and stale bytecode before importing the
# package. A protected parent alone does not protect a user-owned file in it.
for _index,_entry in enumerate(_root.rglob('*')):
    if _index>=2048 or _entry.is_symlink() or _entry.name in ('__pycache__','.git') or _entry.suffix=='.pyc':
        raise RuntimeError('source_only_jev_package_required')
    _info=_entry.lstat()
    if _info.st_uid!=0 or _info.st_mode & 0o022:
        raise RuntimeError('protected_jev_implementation_required')
sys.path.insert(0,str(_root))
_existing=sys.modules.get('jev_agent')
if _existing is not None and getattr(_existing,'__file__',None)!=str(_root/'jev_agent/__init__.py'):
    raise RuntimeError('foreign_jev_package_preserved_and_refused')

from tools.registry import registry as _actual_registry
from jev_agent.tender_finder.startup_tool import StartupRegistration

registry=StartupRegistration(_actual_registry)
registry.register()
