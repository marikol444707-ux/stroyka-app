"""Reproducible source package and checked LOCAL unpack, never a deployment.

Only tracked allowlisted sources are included. A trusted external SHA256 and
commit are mandatory for verification/unpack: an archive cannot authenticate its
own manifest. No network, environment/config/key files or service operations.
"""
import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

from .cli_result import _pairs,_nonfinite

MAX_ARCHIVE=4*1024*1024
MAX_EXPANDED=8*1024*1024
MAX_FILES=128
MANIFEST='SOURCE_MANIFEST.json'
EXTRA={'jev_agent/__init__.py','jev_agent/server_runtime/scripts/jev_commercial_search.py'}
REQUIRED=EXTRA|{'jev_agent/tender_finder/__init__.py','jev_agent/tender_finder/host_service.py',
    'jev_agent/tender_finder/systemd_bootstrap.py','jev_agent/tender_finder/prepare_install.py',
    'jev_agent/tender_finder/source_package.py',
    'jev_agent/tender_finder/integration/host_entry.py','jev_agent/tender_finder/integration/hermes_jev_tool.py'}
REQUIRED|={'jev_agent/tender_finder/'+name+'.py' for name in (
    '__main__ admission_broker admission_files audit_bridge bootstrap_key broker_service container_transfer '
    'card_page catalog cli_plan cli_result compat contract discovery docker_delivery evidence '
    'hermes_binding host_worker image_pin ingress invoker jobs notification pipeline presentation '
    'publication queue reporting runtime settings standalone_release startup_tool state').split()}


def _source(path):
    return ('__pycache__' not in path.split('/') and (path in EXTRA or bool(re.fullmatch(
        r'jev_agent/tender_finder/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.py',path))))


def _git(repository,*args):
    return subprocess.check_output(['git','-C',str(repository),*args],stderr=subprocess.DEVNULL)


def _local_target(path):
    path=Path(path).absolute()
    if (path.parent.resolve(strict=True)!=path.parent
            or '..' in path.parts or not any(path!=root and path.is_relative_to(root)
                    for root in (Path('/tmp'),Path('/workspace')))):
        raise ValueError('new_local_staging_target_required')
    return path


def build(repository,output):
    if _git(repository,'status','--porcelain'):raise ValueError('clean_source_snapshot_required')
    commit=_git(repository,'rev-parse','HEAD').decode().strip()
    tree=_git(repository,'rev-parse',commit+'^{tree}').decode().strip()
    timestamp=int(_git(repository,'show','-s','--format=%ct',commit))
    files={}
    for row in _git(repository,'ls-tree','-r','-z',commit).split(b'\0'):
        if not row:continue
        metadata,name=row.split(b'\t',1)
        path=name.decode('utf-8')
        if not _source(path):continue
        mode,kind,digest=metadata.decode().split()
        if mode!='100644' or kind!='blob':raise ValueError('regular_tracked_sources_required')
        files[path]=_git(repository,'cat-file','blob',digest)
    if not REQUIRED<=files.keys() or len(files)>MAX_FILES:raise ValueError('complete_bounded_source_package_required')
    manifest={'format':1,'kind':'SOURCE_CANDIDATE_NOT_INSTALLER','commit':commit,'tree':tree,
        'installation_ready':False,'files':[{'path':'app/'+name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
                                          for name,raw in sorted(files.items())]}
    contents={MANIFEST:json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2).encode(),
              **{'app/'+name:raw for name,raw in sorted(files.items())}}
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',filename='',mtime=timestamp) as zipped,tarfile.open(fileobj=zipped,mode='w') as archive:
        for name,raw in contents.items():
            entry=tarfile.TarInfo(name);entry.size=len(raw);entry.mtime=timestamp
            entry.mode=0o644;entry.uid=entry.gid=0
            archive.addfile(entry,io.BytesIO(raw))
    raw=buffer.getvalue();digest=hashlib.sha256(raw).hexdigest()
    verify_bytes(raw,digest,commit)
    output=_local_target(output)
    with output.open('xb') as stream:stream.write(raw)
    return {'commit':commit,'sha256':digest,'source_files':len(files),'installation_ready':False}


def verify_bytes(raw,expected_sha256,expected_commit):
    if (type(raw) is not bytes or len(raw)>MAX_ARCHIVE
            or type(expected_sha256) is not str or not re.fullmatch('[a-f0-9]{64}',expected_sha256)
            or type(expected_commit) is not str or not re.fullmatch('[a-f0-9]{40}',expected_commit)
            or hashlib.sha256(raw).hexdigest()!=expected_sha256):
        raise ValueError('pinned_package_hash_and_commit_required')
    files={};expanded=0
    # Bound decompression BEFORE tarfile parses PAX/long-name headers, which
    # could otherwise allocate/scan data before a member is yielded to us.
    maximum=MAX_EXPANDED+(MAX_FILES+1)*1024+32768
    with gzip.GzipFile(fileobj=io.BytesIO(raw),mode='rb') as zipped:plain=zipped.read(maximum+1)
    if len(plain)>maximum:raise ValueError('expanded_source_package_limit')
    with tarfile.open(fileobj=io.BytesIO(plain),mode='r:') as archive:
        for entry in archive:
            if (len(files)>=MAX_FILES+1 or not entry.isfile() or entry.name in files
                    or entry.uid!=0 or entry.gid!=0 or entry.mode!=0o644
                    or entry.size<0 or entry.pax_headers
                    or entry.name!=MANIFEST and not (entry.name.startswith('app/') and _source(entry.name[4:]))):
                raise ValueError('source_only_regular_members_required')
            expanded+=entry.size
            if expanded>MAX_EXPANDED:raise ValueError('expanded_source_package_limit')
            stream=archive.extractfile(entry)
            if stream is None:raise ValueError('source_member_required')
            data=stream.read(entry.size+1)
            if len(data)!=entry.size:raise ValueError('source_size_conflict')
            files[entry.name]=data
    if MANIFEST not in files:raise ValueError('source_manifest_required')
    value=json.loads(files[MANIFEST].decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_nonfinite)
    if (type(value) is not dict or set(value)!={'format','kind','commit','tree','installation_ready','files'}
            or type(value['format']) is not int or value['format']!=1
            or value['kind']!='SOURCE_CANDIDATE_NOT_INSTALLER' or value['commit']!=expected_commit
            or value['installation_ready'] is not False or type(value['tree']) is not str
            or not re.fullmatch('[a-f0-9]{40}',value['tree']) or type(value['files']) is not list):
        raise ValueError('pinned_source_manifest_required')
    declared=set()
    for row in value['files']:
        if (type(row) is not dict or set(row)!={'path','sha256','bytes'} or type(row['path']) is not str
                or row['path']==MANIFEST or row['path'] in declared or row['path'] not in files):
            raise ValueError('exact_source_manifest_required')
        data=files[row['path']]
        if (type(row['bytes']) is not int or row['bytes']!=len(data)
                or row['sha256']!=hashlib.sha256(data).hexdigest()):
            raise ValueError('source_manifest_hash_conflict')
        ast.parse(data.decode('utf-8'),filename=row['path'])  # Parse only, never execute archive code.
        declared.add(row['path'])
    if declared!=files.keys()-{MANIFEST} or not {'app/'+name for name in REQUIRED}<=declared:
        raise ValueError('complete_exact_source_manifest_required')
    return files


def verify(archive,expected_sha256,expected_commit,output=None):
    with Path(archive).open('rb') as stream:raw=stream.read(MAX_ARCHIVE+1)
    files=verify_bytes(raw,expected_sha256,expected_commit)
    if output is not None:
        target=_local_target(output);target.mkdir(mode=0o700)
        for name,data in files.items():
            path=target/name;path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(data)
            path.chmod(0o644)
    return {'verified':True,'source_files':len(files)-1,'unpacked':output is not None,'installation_ready':False}


class Parser(argparse.ArgumentParser):
    def error(self,message):self.exit(2,'invalid package arguments\n')


def main(argv=None):
    parser=Parser(description=__doc__);commands=parser.add_subparsers(dest='operation',required=True)
    builder=commands.add_parser('build');builder.add_argument('--repository',required=True);builder.add_argument('--output',required=True)
    for operation in ('verify','unpack'):
        command=commands.add_parser(operation);command.add_argument('--archive',required=True)
        command.add_argument('--sha256',required=True);command.add_argument('--commit',required=True)
        if operation=='unpack':command.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:
        result=(build(args.repository,args.output) if args.operation=='build' else
                verify(args.archive,args.sha256,args.commit,getattr(args,'output',None)))
    except Exception as error:
        print(json.dumps({'ok':False,'code':type(error).__name__,'installation_ready':False}));return 1
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
