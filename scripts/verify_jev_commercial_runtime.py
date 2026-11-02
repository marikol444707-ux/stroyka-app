"""Required CI-only real copied venv/wheel/bwrap check; no production paths.

Failure of venv, pinned wheel, PDF parsing or native isolation fails CI. No skip,
host extraction fallback, package hook, database, Hermes or Telegram access.
"""
import json
import os
from pathlib import Path
import tempfile
import urllib.request

from .activate_jev_commercial import WHEEL_URL,WHEEL_SHA,command,sha,install_wheel,validate_venv_tree


def main():
    with urllib.request.urlopen(WHEEL_URL,timeout=30) as response:
        if response.url!=WHEEL_URL:raise ValueError('pinned_wheel_origin_changed')
        raw=response.read(1024*1024)
    if sha(raw)!=WHEEL_SHA:raise ValueError('pinned_wheel_hash_mismatch')
    repository=Path(__file__).resolve().parents[1]
    # /tmp is intentionally hidden by bwrap. Put this unique venv under the CI
    # workspace so its one explicit readonly bind survives that /tmp overlay.
    with tempfile.TemporaryDirectory(prefix='jev-native-venv-',dir=repository) as directory:
        venv=Path(directory)/'venv'
        command('/usr/bin/python3','-I','-B','-m','venv','--without-pip','--copies',str(venv))
        purelib=Path(command(str(venv/'bin/python3'),'-I','-B','-c',
            'import sysconfig;print(sysconfig.get_path("purelib"))').decode().strip())
        if not purelib.is_relative_to(venv) or purelib.resolve(strict=True)!=purelib:raise ValueError('private_venv_site_required')
        install_wheel(purelib,raw,uid=os.geteuid())
        validate_venv_tree(venv,uid=os.geteuid())
        probe='''import sys,io,importlib.metadata
sys.path.insert(0,__REPOSITORY__)
assert importlib.metadata.version('pypdf')=='6.18.1'
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from jev_agent.tender_finder.commercial.documents import extract_isolated
assert extract_isolated(b'JEV fixture text','.txt')['complete'] is True
writer=PdfWriter();page=writer.add_blank_page(width=100,height=100)
font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
content=DecodedStreamObject();content.set_data(b'BT /F1 10 Tf 5 50 Td (JEV fixture text) Tj ET')
page[NameObject('/Contents')]=writer._add_object(content)
buffer=io.BytesIO();writer.write(buffer)
result=extract_isolated(buffer.getvalue(),'.pdf')
assert result['complete'] is True and 'JEV fixture text' in str(result)
'''.replace('__REPOSITORY__',repr(str(repository)))
        command(str(venv/'bin/python3'),'-I','-B','-c',probe)
    print(json.dumps({'native_commercial_runtime':'PASS','copied_venv_without_pip':True,
        'pinned_wheel':WHEEL_SHA,'real_isolated_txt_and_pdf':True,'production_changed':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
