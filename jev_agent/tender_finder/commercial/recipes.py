"""Data-only protected recipes for Tender.Pro and official owner portals.

No guessed default portals. The operator records reviewed official endpoints;
model requests cannot supply config paths, hosts, selectors or approval fields.
Names/categories are discovery metadata, never direct-contract evidence.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,urlencode

from .model import public_url
from .platforms import PortalSpec
from .sources import Source,source_registry
from ..state import _directory,_read


@dataclass(frozen=True)
class Recipes:
    extra_sources: tuple
    factories: dict


def parse_recipes(value):
    if (type(value) is not dict or set(value)!={'format','portals'} or type(value['format']) is not int
            or value['format']!=1 or type(value['portals']) is not list or len(value['portals'])>24):
        raise ValueError('bounded_operator_portal_recipes_required')
    known=source_registry();extras=[];factories={}
    native={'b2b','fabrikant','tektorg','gpb','roseltorg','sber','federation','rtender','step'}
    for row in value['portals']:
        required={'source_id','hosts','listings','reviewer_subject','review_evidence_url','notice_path'}
        optional={'name','category','notice_query_key','search_query_parameter'}
        if type(row) is not dict or not required<=set(row) or set(row)-required-optional:
            raise ValueError('explicit_reviewed_portal_fields_required')
        key=row['source_id']
        if (type(key) is not str or not re.fullmatch('[a-z][a-z0-9_-]{1,63}',key)
                or key in native or key in factories):raise ValueError('unique_non_native_portal_required')
        hosts=row['hosts'];listings=row['listings']
        if (type(hosts) is not list or not 1<=len(hosts)<=10 or len(set(hosts))!=len(hosts)
                or any(type(host) is not str or not re.fullmatch(r'[a-z0-9][a-z0-9.-]*[a-z0-9]',host)
                       or not public_url('https://'+host+'/') for host in hosts)
                or type(listings) is not list or not 1<=len(listings)<=4
                or any(not public_url(url) or urlsplit(url).hostname not in hosts for url in listings)):
            raise ValueError('reviewed_exact_public_hosts_and_listings_required')
        if (not public_url(row['review_evidence_url']) or urlsplit(row['review_evidence_url']).hostname not in hosts
                or type(row['reviewer_subject']) is not str
                or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_:.@-]{0,127}',row['reviewer_subject'])):
            raise ValueError('protected_official_portal_review_required')
        path=row['notice_path'];query=row.get('notice_query_key');search=row.get('search_query_parameter')
        if (type(path) is not str or not path.startswith('/') or len(path)>200 or '?' in path or '#' in path
                or '..' in path or any(ord(char)<33 for char in path)
                or any(item is not None and (type(item) is not str or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',item))
                       for item in (query,search))):
            raise ValueError('literal_portal_path_and_parameter_names_required')
        pattern=re.escape(path) if query else re.escape(path.rstrip('/')+'/')+r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}/?'
        if key in known:
            old=known[key];source=Source(key,old.name,old.category,tuple(hosts))
        else:
            name=row.get('name');category=row.get('category')
            if (type(name) is not str or not 2<=len(name)<=120 or category not in ('owner','agriculture','research')):
                raise ValueError('explicit_new_owner_source_metadata_required')
            source=Source(key,name,category,tuple(hosts));extras.append(source)
        def factory(profile,now,source=source,seeds=tuple(listings),pattern=pattern,query=query,search=search):
            profile.validate()
            if search:
                terms=tuple(dict.fromkeys((*profile.queries,*profile.regions)))
                urls=tuple(seed+('&' if urlsplit(seed).query else '?')+urlencode({search:term})
                           for seed in seeds for term in terms)
            else:urls=seeds
            if len(urls)>20:raise ValueError('portal_search_plan_limit')
            return PortalSpec(source,urls,(None,)*len(urls),notice_pattern=pattern,planned_at=now,notice_query_key=query)
        factories[key]=factory
    return Recipes(tuple(extras),factories)


def load_recipes(path,*,trusted_root,expected_uid=0,system_uid=0):
    """Only an explicitly provisioned private 0700/0600 operator namespace.

    Production UIDs are root; managed test fixtures can explicitly bind mapped
    filesystem-root ownership. Existing v2/key directories
    are not read or adopted. This reads config only and never creates folders.
    """
    import os,stat
    if any(type(uid) is not int or uid<0 for uid in (expected_uid,system_uid)):
        raise ValueError('protected_config_uids_required')
    path=Path(path).absolute();root=Path(trusted_root).absolute()
    if path.parent!=root or path.resolve(strict=True)!=path:raise ValueError('protected_portal_config_path_required')
    for parent in (root,*root.parents):
        info=parent.stat()
        if info.st_uid not in (0,system_uid,expected_uid) or info.st_mode&0o022:
            # Sticky root-owned /tmp cannot let another UID rename our private
            # owned 0700 directory. The explicit trusted root itself still has
            # strict ownership/mode checks below; arbitrary shared dirs fail.
            if parent==Path('/tmp') and info.st_uid in (0,system_uid) and info.st_mode&0o1000:continue
            raise ValueError('protected_portal_config_ancestor_required')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if info.st_uid!=expected_uid or stat.S_IMODE(info.st_mode)!=0o700:
            raise ValueError('private_portal_config_directory_required')
        # _read checks effective UID, mode, hardlinks and a bounded size. The
        # root host process is mandatory in production; no UID fallback.
        if os.geteuid()!=expected_uid:raise ValueError('portal_config_process_uid_mismatch')
        raw=_read(fd,path.name,private=True)
        if raw is None:raise ValueError('portal_recipes_missing')
        from ..cli_result import _pairs,_nonfinite
        return parse_recipes(json.loads(raw,object_pairs_hook=_pairs,parse_constant=_nonfinite))
    finally:os.close(fd)
