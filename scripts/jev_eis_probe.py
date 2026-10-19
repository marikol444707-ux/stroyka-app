"""Read-only EIS browser access probe; not an autonomous procurement search.

The CA is trusted only inside this short-lived, credential-free browser container.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urljoin, urlparse
from uuid import uuid4

URL = 'https://zakupki.gov.ru/epz/order/extendedsearch/results.html'
IMAGE = 'sha256:8c231608d909734fee19e3ce851ca1725fd6e4e84f20fb5f8a4288a06823ef0d'
CA_SHA256 = 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31'

class Registry(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ''
        self.search = False
        self.notices = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'input' and attrs.get('name') == 'searchString': self.search = True
        if tag == 'a':
            link = urljoin(URL, attrs.get('href', ''))
            parsed = urlparse(link)
            if (parsed.scheme == 'https' and parsed.netloc == 'zakupki.gov.ru'
                    and parsed.path.endswith('/common-info.html') and 'regNumber=' in parsed.query):
                self.notices.add(link)

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False

    def handle_data(self, data):
        if self.in_title: self.title += data


def classify(html):
    page = Registry()
    page.feed(html)
    ready = page.title.strip() == 'Закупки' and page.search and bool(page.notices)
    status = 'search_registry_accessible' if ready else 'registry_not_verified'
    if 'ERR_CERT_' in html: status, ready = 'tls_failed', False
    return {'ok': ready, 'status': status, 'title': page.title.strip()[:150],
            'url': URL, 'notice_links_observed': len(page.notices),
            'search_execution_verified': False, 'model_calls': 0}


def verify_ca(path):
    import ssl
    der = ssl.PEM_cert_to_DER_cert(path.read_text())
    if hashlib.sha256(der).hexdigest() != CA_SHA256:
        raise ValueError('Unexpected EIS CA fingerprint')


def worker():
    ca = Path('/cert/root.pem')
    verify_ca(ca)
    with tempfile.TemporaryDirectory(prefix='eis-browser-') as tmp:
        env = {'HOME': tmp, 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
        db = Path(tmp) / '.pki/nssdb'
        db.mkdir(parents=True)
        for args in (['certutil', '-N', '-d', 'sql:'+str(db), '--empty-password'],
                     ['certutil', '-A', '-d', 'sql:'+str(db), '-n', 'EIS Russian Trusted Root',
                      '-t', 'C,,', '-i', str(ca)]):
            subprocess.run(args, env=env, check=True, capture_output=True, timeout=5)
        result = subprocess.run(['/usr/bin/google-chrome', '--headless=new', '--no-sandbox',
            '--disable-dev-shm-usage', '--user-data-dir='+tmp+'/chrome', '--dump-dom', URL],
            env=env, timeout=40, capture_output=True, text=True)
        if result.returncode: return {'ok': False, 'status': 'browser_failed'}
        return classify(result.stdout)


def probe():
    repo = Path(__file__).resolve().parent.parent
    ca = repo / 'dev_control/certificates/russian-trusted-root.pem'
    verify_ca(ca)
    name = 'stroyka-eis-probe-' + uuid4().hex
    args = ['docker', 'run', '--rm', '--name', name, '--network', 'bridge',
            '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '1g', '--pids-limit', '256', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=384m',
            '--mount', 'type=bind,src='+str(ca)+',dst=/cert/root.pem,readonly',
            '--mount', 'type=bind,src='+str(Path(__file__).resolve())+',dst=/probe.py,readonly',
            '--entrypoint', 'python3', IMAGE, '/probe.py', '--worker']
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        if result.returncode: return {'ok': False, 'status': 'runner_failed'}
        return json.loads(result.stdout)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)


if __name__ == '__main__':
    import sys
    try:
        result = worker() if sys.argv[1:] == ['--worker'] else probe()
    except subprocess.TimeoutExpired:
        result = {'ok': False, 'status': 'browser_timeout'}
    except Exception as exc:
        result = {'ok': False, 'status': 'probe_failed', 'error_type': type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get('ok') else 1)
