"""Private document worker, fixed executables, private temp directory, bounded output."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

class Invalid(Exception):pass
class Limit(Exception):pass
class Missing(Exception):pass
class Encrypted(Exception):pass

def run(name,args):
    executable=shutil.which(name)
    if not executable:raise Missing()
    return subprocess.run([executable,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=True,timeout=90).stdout

def ocr(path):
    text=run('tesseract',[path,'stdout','-l','rus+eng']).decode('utf-8').replace('\x0c','\n').strip()
    if not text:raise Invalid()
    return text

def pdf(data,folder):
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data),strict=False)
    if reader.is_encrypted:raise Encrypted()
    if not 0<len(reader.pages)<=30:raise Limit()
    source=folder/'input.pdf';source.write_bytes(data);texts=[]
    for index,page in enumerate(reader.pages,1):
        text=(page.extract_text() or '').strip()
        # Image-bearing pages are rendered too: a text header does not prove
        # that requisites in the scanned body have been read.
        has_image=bool(page.images)
        if not text or has_image:
            prefix=folder/'render'
            run('pdftoppm',['-f',index,'-l',index,'-singlefile','-scale-to',2200,'-png',source,prefix])
            text=ocr(folder/'render.png');(folder/'render.png').unlink()
        texts.append(text)
        if sum(map(len,texts))+2*len(texts)>64000:raise Limit()
    return '\n\n'.join(texts)

def office(data,suffix,folder):
    if suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist())>2000 or sum(i.file_size for i in z.infolist())>32*1024*1024:raise Limit()
            raw=z.read('word/document.xml')
            if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:raise Invalid()
            tree=ET.fromstring(raw);ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            # Text-only main document can be read without a converter. Images,
            # headers/footers and objects require rendering the complete document.
            complex_doc=any(e.tag.rsplit('}',1)[-1] in ('drawing','object','pict','altChunk') for e in tree.iter()) or any(n.startswith(('word/header','word/footer')) for n in z.namelist())
            if not complex_doc:
                return '\n'.join(''.join(p.itertext()) for p in tree.iter(ns+'p')).strip()
    source=folder/('source'+suffix);source.write_bytes(data)
    run('libreoffice',['-env:UserInstallation='+ (folder/'profile').as_uri(),'--headless','--convert-to','pdf','--outdir',folder,source])
    return pdf((folder/'source.pdf').read_bytes(),folder)

def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(90,90));resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024*1024,)*2)
        if sys.platform=='linux':resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
        data=sys.stdin.buffer.read(10*1024*1024+1)
        if len(data)>10*1024*1024:raise Limit()
        suffix=sys.argv[1]
        magic={'.pdf':b'%PDF-','.doc':b'\xd0\xcf\x11\xe0','.docx':b'PK','.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8','.jpeg':b'\xff\xd8'}
        if suffix not in magic or not data.startswith(magic[suffix]):raise Invalid()
        folder=Path(sys.argv[2])
        if suffix=='.pdf':text=pdf(data,folder)
        elif suffix in ('.doc','.docx'):text=office(data,suffix,folder)
        else:
            path=folder/('image'+suffix);path.write_bytes(data);text=ocr(path)
        if len(text)>64000:raise Limit()
        if not text.strip():raise Invalid()
        sys.stdout.buffer.write(text.encode('utf-8'))
        return 0
    except Encrypted:return 6
    except (Limit,MemoryError):return 4
    except (Missing,ImportError):return 3
    except Exception:return 2
if __name__=='__main__':sys.exit(main())
