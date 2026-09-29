"""Bounded document extraction in a separate process; no URLs or credentials."""
import os
import signal
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from fastapi import HTTPException

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def python_runtime_bind_args(prefix):
    """Expose a non-system Python runtime read-only inside the empty sandbox."""
    runtime = Path(prefix).resolve()
    system_roots = (Path('/usr'), Path('/lib'), Path('/lib64'))
    if any(runtime == root or root in runtime.parents for root in system_roots):
        return []
    return ['--ro-bind', str(runtime), str(runtime)]


def existing_readonly_bind_args(*paths):
    """Bind optional host configuration only when it is installed."""
    result = []
    for path in map(Path, paths):
        if path.exists():
            result += ['--ro-bind', str(path), str(path)]
    return result

def extract_document_text(content, extension):
    if extension not in ('.pdf','.doc','.docx','.jpg','.jpeg','.png'):
        raise HTTPException(415,'Этот тип файла договора не поддерживается')
    if len(content)>MAX_DOCUMENT_BYTES:
        raise HTTPException(413,'Договор превышает 10 МБ')
    with tempfile.TemporaryDirectory(prefix='stroyka-contract-') as temp:
        worker=Path(__file__).with_name('contract_document_worker.py')
        command=[sys.executable,'-I',str(worker),extension,temp]
        if sys.platform=='linux':
            sandbox=shutil.which('bwrap')
            if not sandbox:raise HTTPException(503,'Изолированный обработчик документов недоступен')
            command=[sandbox,'--unshare-all','--die-with-parent','--cap-drop','ALL',
                     '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--symlink','usr/bin','/bin']
            if Path('/lib64').exists():command+=['--ro-bind','/lib64','/lib64']
            command += python_runtime_bind_args(sys.prefix)
            command+=['--dir','/etc']
            command += existing_readonly_bind_args('/etc/fonts', '/etc/libreoffice')
            command+=['--ro-bind','/etc/passwd','/etc/passwd','--ro-bind','/etc/group','/etc/group',
                      '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
                      '--bind',temp,'/work','--ro-bind',str(worker),'/worker.py',
                      '--chdir','/work','--setenv','HOME','/work',
                      sys.executable,'-I','/worker.py',extension,'/work']
        try:
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                env={'PATH':'/usr/bin:/bin:/usr/local/bin','OMP_THREAD_LIMIT':'1'},start_new_session=True)
        except OSError:raise HTTPException(503,'Обработчик документов недоступен') from None
        try:
            output,_=process.communicate(bytes(content),timeout=120)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.communicate()
            raise HTTPException(504,'Обработка договора заняла слишком много времени. Оригинал сохранён') from None
    errors={3:(503,'Обработчик этого документа временно недоступен'),4:(413,'Договор превышает лимит обработки: 30 страниц или 64000 символов'),
            6:(422,'Для распознавания загрузите договор без пароля')}
    if process.returncode:
        status,message=errors.get(process.returncode,(422,'Не удалось прочитать договор. Проверьте качество и целостность файла; оригинал сохранён'))
        raise HTTPException(status,message)
    try:text=output.decode('utf-8')
    except UnicodeDecodeError:raise HTTPException(422,'Некорректный результат распознавания') from None
    if not text.strip() or len(text)>64000 or any(ord(c)<32 and c not in '\r\n\t' for c in text):
        raise HTTPException(422,'В договоре не найден читаемый текст')
    return text
