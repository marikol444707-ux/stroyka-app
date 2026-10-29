"""Host-only pin for an approved stopped-container snapshot; no image creation.

Missing pin keeps the original strict image gate. Existing malformed/untrusted
pins fail closed. A derived image must match a root-owned private record AND its
fresh Docker parent must be the reviewed base. No model/env/force overrides.
"""
import json
import os
from pathlib import Path
import re
import stat

from .cli_result import _pairs,_nonfinite

BASE_IMAGE='sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d'
PIN_PATH=Path('/etc/stroyka-jev/container-image.json')


def snapshot_pin(stopped,image,*,_base=BASE_IMAGE):
    if (type(stopped) is not dict or stopped.get('Image')!=_base
            or type(stopped.get('State')) is not dict or stopped['State'].get('Running') is not False
            or type(stopped.get('Id')) is not str or not re.fullmatch('[a-f0-9]{64}',stopped['Id'])
            or type(image) is not dict or image.get('Parent')!=_base
            or type(image.get('Id')) is not str or not re.fullmatch('sha256:[a-f0-9]{64}',image['Id'])
            or image['Id']==_base):
        raise ValueError('stopped_snapshot_of_reviewed_base_required')
    return {'format':1,'base_image':_base,'snapshot_image':image['Id'],
            'source_container':stopped['Id'],'source_stopped':True}


def load_pin(*,_path=PIN_PATH,_uid=0,_trusted_root=Path('/etc/stroyka-jev')):
    path=Path(_path).absolute();root=Path(_trusted_root).absolute()
    try:info=path.lstat()
    except FileNotFoundError:return None
    if (path==root or not path.is_relative_to(root) or path.resolve(strict=True)!=path
            or root.resolve(strict=True)!=root or not stat.S_ISREG(info.st_mode)):
        raise ValueError('protected_image_pin_required')
    for directory in (path.parent,*path.parent.parents):
        current=directory.stat()
        if current.st_uid!=_uid or current.st_mode & 0o022:
            raise ValueError('protected_image_pin_parent_required')
        if directory==root:break
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=_uid or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>4096):
            raise ValueError('private_image_pin_required')
        raw=os.read(fd,4097)
    finally:os.close(fd)
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_nonfinite)
    if (type(value) is not dict or set(value)!={'format','base_image','snapshot_image','source_container','source_stopped'}
            or type(value['format']) is not int or value['format']!=1 or value['base_image']!=BASE_IMAGE
            or value['source_stopped'] is not True or type(value['snapshot_image']) is not str
            or not re.fullmatch('sha256:[a-f0-9]{64}',value['snapshot_image'])
            or value['snapshot_image']==BASE_IMAGE or type(value['source_container']) is not str
            or not re.fullmatch('[a-f0-9]{64}',value['source_container'])):
        raise ValueError('reviewed_snapshot_pin_required')
    return value
