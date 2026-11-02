"""Read-only upgrade review of an ALREADY installed v2 broker.

Creates only a new private local review directory. Never applies files, stops
services, reads signing keys, installs dependencies, or calls procurement sites.
An unknown/manual source change blocks the review, rather than being overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .prepare_install import prepare
from ..settings import load_settings
from ..source_package import _git,_source,MAX_FILES,MAX_EXPANDED
from ..standalone_release import source_files,verify_ci,_private
from ..systemd_bootstrap import discover_gateway_peer

BASELINE='ba6cf4fe3357fd5549c11799452cdff4820b15ea'
PLUGIN='jev_agent/tender_finder/integration/hermes_jev_tool.py'


def baseline_manifest(repository,commit=BASELINE):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('pinned_baseline_required')
    files={};size=0
    for row in _git(repository,'ls-tree','-r','-z',commit).split(b'\0'):
        if not row:continue
        metadata,name=row.split(b'\t',1);name=name.decode()
        if not _source(name):continue
        mode,kind,blob=metadata.decode().split()
        if mode!='100644' or kind!='blob':raise ValueError('regular_baseline_sources_required')
        raw=_git(repository,'cat-file','blob',blob);size+=len(raw)
        if len(files)>=MAX_FILES or size>MAX_EXPANDED:raise ValueError('bounded_baseline_required')
        files[name]=hashlib.sha256(raw).hexdigest()
    if PLUGIN not in files:raise ValueError('complete_baseline_required')
    return files


def installed_manifest(root,expected,*,uid=0,trusted_root=Path('/')):
    """Read only regular, protected .py files named by the pinned baseline."""
    root=Path(root);trusted_root=Path(trusted_root)
    if (root.resolve(strict=True)!=root or trusted_root.resolve(strict=True)!=trusted_root
            or not root.is_relative_to(trusted_root)):
        raise ValueError('protected_installed_root_required')
    for parent in (root,*root.parents):
        info=parent.stat()
        if info.st_uid!=uid or info.st_mode&0o022:raise ValueError('protected_installed_parent_required')
        if parent==trusted_root:break
    files={};size=0
    for index,path in enumerate(root.rglob('*')):
        if index>=2048:raise ValueError('bounded_installed_tree_required')
        info=path.lstat();name=path.relative_to(root).as_posix()
        if (info.st_uid!=uid or info.st_mode&0o022
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
            raise ValueError('protected_source_only_tree_required')
        if stat.S_ISDIR(info.st_mode):continue
        if (name not in expected or not _source(name) or info.st_nlink!=1 or info.st_size>1024*1024):
            raise ValueError('unreviewed_installed_file_preserved')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            opened=os.fstat(fd)
            if (opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns)!=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns):
                raise ValueError('installed_source_changed_during_review')
            raw=os.read(fd,1024*1024+1)
            if len(raw)!=info.st_size:raise ValueError('installed_source_changed_during_review')
        finally:os.close(fd)
        size+=len(raw)
        if size>MAX_EXPANDED:raise ValueError('bounded_installed_source_required')
        files[name]=hashlib.sha256(raw).hexdigest()
    if files!=expected:raise ValueError('installed_source_differs_from_pinned_baseline')
    return files


def change_plan(previous,candidate):
    # The Hermes builtin also has its own file bind mount. Do not replace that
    # inode or silently assume a directory swap updates the mounted plugin.
    if previous.get(PLUGIN)!=candidate.get(PLUGIN):raise ValueError('plugin_mount_upgrade_requires_review')
    return {'added':sorted(candidate.keys()-previous.keys()),
            'changed':sorted(name for name in candidate.keys()&previous.keys() if candidate[name]!=previous[name]),
            'removed':sorted(previous.keys()-candidate.keys()),
            'unchanged':len([name for name in candidate.keys()&previous.keys() if candidate[name]==previous[name]]),
            'mounted_plugin_unchanged':True}


def review(stage,commit,*,_uid=0,_installed=Path('/opt/stroyka-jev/app'),_trusted_root=Path('/'),
           _legacy=Path('/etc/stroyka-jev/bridge.json'),_legacy_root=Path('/etc/stroyka-jev'),
           _ci=verify_ci,_peer=discover_gateway_peer):
    stage=Path(stage).absolute();_private(stage,_uid)
    output=stage/'commercial-upgrade-review'
    if output.exists() or output.is_symlink():raise ValueError('existing_review_preserved')
    previous=installed_manifest(_installed,baseline_manifest(stage/'repository'),uid=_uid,trusted_root=_trusted_root)
    candidate=source_files(stage/'repository',stage/'source',commit,_uid)
    changes=change_plan(previous,candidate)
    legacy=load_settings(_legacy,trusted_root=_legacy_root,expected_uid=_uid)
    peer=_peer()
    if peer.uid!=legacy.gateway_uid or peer.gid!=10000:raise ValueError('observed_gateway_identity_required')
    ci_url=_ci(commit)
    # Recheck after external CI/process observations; the review is a snapshot,
    # never authorization to overwrite a source that changes afterwards.
    installed_manifest(_installed,previous,uid=_uid,trusted_root=_trusted_root)
    result=prepare(output,legacy)
    manifest={'kind':'COMMERCIAL_UPGRADE_REVIEW_ONLY','baseline_commit':BASELINE,'candidate_commit':commit,
        'ci_url':ci_url,'installed_source_verified':True,'previous_files':previous,'candidate_files':candidate,
        'changes':changes,'installation_ready':False,'services_changed':False,'key_read':False,
        'required_transaction':[
            'Recheck exact source, private owner policy, container identity and active units under an operator lock.',
            'Gracefully stop/drain both the old broker and Hermes before modifying any shared Python source.',
            'Keep the unchanged bound plugin inode and original container; never recreate it from partial inspect data.',
            'Retain protected original source bytes and file metadata for rollback; preserve all existing keys and request receipts.',
            'Provision a separate protected venv, sandbox dependencies, host-only key and commercial state.',
            'Verify both old broker and new broker after restart; test native search and real Telegram delivery.',
            'On failure restore only owned code/config/service changes; never restore or erase operational data.'
        ]}
    path=output/'UPGRADE_REVIEW.json'
    with path.open('x') as stream:json.dump(manifest,stream,ensure_ascii=False,indent=2)
    path.chmod(0o600)
    return {**result,'installed_source_verified':True,'mounted_plugin_unchanged':True,
        'added_files':len(changes['added']),'changed_files':len(changes['changed']),
        'removed_files':len(changes['removed']),'ci_url':ci_url,
        'review_directory':str(output),'installation_started':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',required=True);parser.add_argument('--commit',required=True)
    args=parser.parse_args(argv)
    try:
        if os.geteuid()!=0:raise ValueError('root_operator_review_required')
        result=review(args.stage,args.commit)
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) and re.fullmatch('[a-z_]{1,100}',str(error)) else type(error).__name__
        print(json.dumps({'prepared':False,'code':code,'installation_ready':False,'services_changed':False}));return 1
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
