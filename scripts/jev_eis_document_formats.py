"""Bounded document text extraction. Never executes document code or macros."""
import ast
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import io
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from defusedxml import ElementTree as ET
import zipfile

MAX_BYTES=32*1024*1024
MAX_EXPANDED=96*1024*1024
MAX_UNITS=25000


def formula_value(formula, cells, seen=frozenset()):
    if not isinstance(formula,str) or not formula.startswith('=') or len(formula)>2000:raise ValueError('Unsupported formula')
    from openpyxl.utils.cell import range_boundaries, get_column_letter
    def expand(match):
        x1,y1,x2,y2=range_boundaries(match[1])
        if (x2-x1+1)*(y2-y1+1)>2000:raise ValueError('Range limit')
        return 'SUM('+','.join(get_column_letter(x)+str(y) for y in range(y1,y2+1) for x in range(x1,x2+1))+')'
    expression=re.sub(r'SUM\(([A-Z]+\d+:[A-Z]+\d+)\)',expand,formula[1:].replace('$',''))
    try: tree=ast.parse(expression,mode='eval')
    except (SyntaxError,RecursionError):raise ValueError('Unsupported formula') from None
    def visit(node,depth=0):
        if depth>30:raise ValueError('Formula depth')
        if isinstance(node,ast.Constant) and isinstance(node.value,(float,int)) and not isinstance(node.value,bool):return Decimal(ast.get_source_segment(expression,node))
        if isinstance(node,ast.Name) and re.fullmatch(r'[A-Z]+[1-9]\d*',node.id):
            if node.id in seen or len(seen)>20:raise ValueError('Formula cycle')
            value=cells.get(node.id)
            if isinstance(value,str) and value.startswith('='):return formula_value(value,cells,seen|{node.id})
            if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):return Decimal(str(value))
            raise ValueError('Non-numeric cell')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand,depth+1);return -value if isinstance(node.op,ast.USub) else value
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            a,b=visit(node.left,depth+1),visit(node.right,depth+1)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if not b:raise ValueError('Zero divisor')
            return a/b
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            values=[visit(x,depth+1) for x in node.args]
            if node.func.id=='SUM':return sum(values,Decimal(0))
            if node.func.id=='ROUND' and len(values)==2 and values[1]==int(values[1]) and -10<=int(values[1])<=10:return values[0].quantize(Decimal(1).scaleb(-int(values[1])),rounding=ROUND_HALF_UP)
        raise ValueError('Unsupported formula')
    try:return visit(tree.body)
    except (InvalidOperation,OverflowError):raise ValueError('Invalid numeric operation') from None


def checked_zip(data, budget=None):
    z=zipfile.ZipFile(io.BytesIO(data));total=0
    if len(z.infolist())>400:raise ValueError('Archive member limit')
    for member in z.infolist():
        name=PurePosixPath(member.filename)
        if len(member.filename)>500 or name.is_absolute() or '..' in name.parts or '\\' in member.filename or (member.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive path')
        total+=member.file_size
        if member.flag_bits&1 or total>MAX_EXPANDED or member.file_size>MAX_BYTES or member.file_size>max(member.compress_size,1)*200:raise ValueError('Archive size/encryption limit')
    if budget is not None:
        budget['expanded']+=total
        if budget['expanded']>MAX_EXPANDED:raise ValueError('Total archive expansion limit')
    return z


def extract(path, source, depth=0, budget=None):
    if budget is None:budget={'expanded':0,'units':0,'chars':0}
    path=Path(path);data=path.read_bytes()
    if len(data)>MAX_BYTES:raise ValueError('File size limit')
    suffix=path.suffix.lower();units=[];issues=[];audit=[]
    if suffix=='.bin' and data.startswith(b'Rar!\x1a\x07'):suffix='.rar'
    def add(locator,text,ocr=False):
        text=str(text).strip()
        if text:
            budget['units']+=1;budget['chars']+=len(text)
            if budget['chars']>2000000:raise ValueError('Total text limit')
            if budget['units']>MAX_UNITS:raise ValueError('Text unit limit')
            units.append({'id':source+':'+str(len(units)+1),'source':source,'locator':locator,'text':text[:20000],'ocr':ocr})
            if len(text)>20000:issues.append('Фрагмент обрезан: '+locator)
    if suffix=='.docx':
        with checked_zip(data,budget) as z:
            xml=z.read('word/document.xml')
            if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:raise ValueError('XML entities refused')
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            sections=['word/document.xml']+[n for n in z.namelist() if re.fullmatch(r'word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml',n)]
            for section in sections:
                root=ET.fromstring(z.read(section))
                for i,p in enumerate(root.findall('.//w:p',ns),1):
                    locator=('' if section=='word/document.xml' else section+' · ')+'абзац '+str(i)
                    add(locator,''.join(t.text or '' for t in p.findall('.//w:t',ns)))
            media=[n for n in z.namelist() if n.startswith('word/media/')]
            if len(media)>20:issues.append('Встроенных изображений больше лимита OCR');media=media[:20]
            with tempfile.TemporaryDirectory(prefix='eis-docx-images-') as tmp:
                for index,name in enumerate(media):
                    suffix=PurePosixPath(name).suffix.lower()
                    if suffix not in {'.png','.jpg','.jpeg','.tif','.tiff','.bmp'}:
                        issues.append('Не прочитано встроенное изображение: '+name);continue
                    image=Path(tmp)/(str(index)+suffix);image.write_bytes(z.read(name))
                    try:
                        text=subprocess.run(['tesseract',str(image),'stdout','-l','rus+eng'],capture_output=True,timeout=45,check=True).stdout.decode('utf-8',errors='replace')
                        if len(text.strip())>=10:add(name+' · OCR',text,True);issues.append('OCR: '+name+' — цифры требуют сверки с изображением')
                    except Exception:issues.append('Не удалось распознать изображение: '+name)
    elif suffix in {'.xlsx','.xlsm'}:
        from openpyxl import load_workbook
        with checked_zip(data,budget):pass
        book=load_workbook(path,read_only=True,data_only=False,keep_links=False)
        cached=load_workbook(path,read_only=True,data_only=True,keep_links=False)
        try:
            for sheet in book:
                if sheet.max_row>10000 or sheet.max_column>1000 or sheet.max_row*sheet.max_column>1000000:raise ValueError('Worksheet dimensions limit')
                values={};cache={}
                for row in cached[sheet.title]:
                    for cell in row:
                        if cell.value is not None:cache[cell.coordinate]=cell.value
                for row in sheet:
                    for cell in row:
                        if cell.value is None:continue
                        values[cell.coordinate]=cell.value
                        shown=cache.get(cell.coordinate,cell.value)
                        add(sheet.title+'!'+cell.coordinate,shown)
                for address,value in values.items():
                    if not isinstance(value,str) or not value.startswith('='):continue
                    item={'locator':sheet.title+'!'+address,'formula':value,'status':'not_checked'}
                    try:
                        calculated=formula_value(value,values)
                        prior=cache.get(address)
                        if isinstance(prior,(int,float)) and not isinstance(prior,bool):
                            item.update(status='matched' if abs(calculated-Decimal(str(prior)))<=Decimal('.01') else 'mismatch',calculated=str(calculated),cached=str(prior))
                        else:item['status']='cached_value_missing'
                    except ValueError:pass
                    audit.append(item)
        finally:book.close();cached.close()
    elif suffix=='.pdf':
        # Poppler preserves page boundaries; OCR is used only for pages without text.
        with tempfile.TemporaryDirectory(prefix='eis-pdf-') as tmp:
            text=subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True,timeout=45,check=True).stdout.decode('utf-8',errors='replace')
            pages=text.split('\f')
            if len(pages)>101:raise ValueError('PDF page limit')
            for number,page in enumerate(pages,1):
                if number==len(pages) and not page.strip():continue
                ocr=False
                if len(page.strip())<25:
                    prefix=str(Path(tmp)/('page-'+str(number)))
                    subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-scale-to','2200','-singlefile','-png',str(path),prefix],capture_output=True,timeout=30,check=True)
                    page=subprocess.run(['tesseract',prefix+'.png','stdout','-l','rus+eng'],capture_output=True,timeout=45,check=True).stdout.decode('utf-8',errors='replace');ocr=True
                    issues.append('OCR: страница '+str(number)+' — цифры требуют сверки с изображением')
                add('страница '+str(number),page,ocr)
    elif suffix in {'.doc','.rtf'}:
        tool=['antiword',str(path)] if suffix=='.doc' else ['unrtf','--text',str(path)]
        text=subprocess.run(tool,capture_output=True,check=True,timeout=30).stdout
        text=text.decode('utf-8',errors='replace')
        for i,line in enumerate(text.splitlines(),1):add('строка '+str(i),line)
    elif suffix in {'.txt','.csv'}:
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:text=data.decode('cp1251')
        for i,line in enumerate(text.splitlines(),1):add('строка '+str(i),line)
    elif suffix in {'.rar','.7z'}:
        if depth>=2:raise ValueError('Nested archive limit')
        import libarchive
        with libarchive.file_reader(str(path)) as archive, tempfile.TemporaryDirectory(prefix='eis-rar-') as tmp:
            for number,entry in enumerate(archive,1):
                if number>100:raise ValueError('Archive member limit')
                name=PurePosixPath(entry.pathname)
                if len(entry.pathname)>500 or name.is_absolute() or '..' in name.parts or '\\' in entry.pathname or entry.issym or entry.islnk:raise ValueError('Unsafe archive entry')
                if entry.isdir:continue
                if not entry.isfile:raise ValueError('Non-file archive entry')
                parts=[];size=0
                for block in entry.get_blocks():
                    size+=len(block);budget['expanded']+=len(block)
                    if size>MAX_BYTES or budget['expanded']>MAX_EXPANDED:raise ValueError('Archive expansion limit')
                    parts.append(block)
                child=Path(tmp)/(str(number)+name.suffix.lower());child.write_bytes(b''.join(parts))
                try:
                    result=extract(child,source+' / '+str(name),depth+1,budget);units.extend(result['units']);issues.extend(result['issues']);audit.extend(result['formula_audit'])
                except Exception as exc:issues.append(str(name)+': '+type(exc).__name__)
    elif suffix=='.zip':
        if depth>=2:raise ValueError('Nested archive limit')
        with checked_zip(data,budget) as z, tempfile.TemporaryDirectory(prefix='eis-archive-') as tmp:
            for number,member in enumerate(z.infolist(),1):
                if member.is_dir():continue
                child=Path(tmp)/(str(number)+PurePosixPath(member.filename).suffix.lower());child.write_bytes(z.read(member))
                try:
                    result=extract(child,source+' / '+member.filename,depth+1,budget);units.extend(result['units']);issues.extend(result['issues']);audit.extend(result['formula_audit'])
                except Exception as exc:issues.append(member.filename+': '+type(exc).__name__)
                if len(units)>MAX_UNITS:raise ValueError('Archive text unit limit')
    else:issues.append('Формат не поддержан: '+suffix)
    if not units:issues.append('Текст не извлечён')
    return {'units':units,'issues':issues,'formula_audit':audit,'status':'partial' if issues else 'read'}
