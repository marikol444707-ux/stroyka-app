"""Isolated preparation inside /tmp of an EXISTING running frontend container.
No live-volume publication, container start/stop or database work here.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

CONTAINER = 'stroyka-qa-frontend'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def build_environment(values):
    require(values.get('REACT_APP_API_URL', '') in ('', '/api'), 'Frontend API must use the confirmed same-origin /api QA route')
    result = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'CI': 'true',
              'REACT_APP_API_URL': '/api', 'PUBLIC_URL': '',
              'NPM_CONFIG_USERCONFIG': '/dev/null', 'NPM_CONFIG_GLOBALCONFIG': '/dev/null',
              'NPM_CONFIG_REGISTRY': 'https://registry.npmjs.org/'}
    for key, value in values.items():
        if key == 'REACT_APP_API_URL':
            continue
        require(re.fullmatch(r'REACT_APP_[A-Z0-9_]+', key) and value in ('', '0', '1', 'true', 'false'),
                'Unreviewed frontend environment value; not inherited')
        result[key] = value
    return result


def digest(build):
    from scripts.unified_release import manifest_files
    manifest_files(build)
    require((build / 'index.html').is_file(), 'Missing frontend index')
    records = {}
    for path in sorted(build.rglob('*')):
        require(not path.is_symlink(), 'Frontend artifact contains symlink')
        if path.is_file():
            records[str(path.relative_to(build))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return records


class FrontendStage:
    def __init__(self, driver):
        self.driver = driver
        self.host = None
        self.container_path = None
        self.hashes = None
        self.accepted = False
        self.host_identity = None
        self.cleanup_safe = True

    def prepare(self, archive_bytes, environment):
        d = self.driver
        require(d.inspect(CONTAINER, '{{json .State.Running}}') is True,
                'Existing frontend builder must already be running; no automatic start')
        self.host = Path(tempfile.mkdtemp(prefix='stroyka-qa-prebuild-', dir='/opt'))
        if getattr(d, 'diagnostics', None):
            d.diagnostics.resource('host_staging', self.host)
        info = self.host.stat()
        self.host_identity = (info.st_dev, info.st_ino)
        source = self.host / 'source'
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
            for member in archive.getmembers():
                require(member.isfile() or member.isdir(), 'Source links not allowed')
                require((source / member.name).resolve().is_relative_to(source.resolve()), 'Archive escape')
                require(not any(x.startswith('.env') for x in Path(member.name).parts), 'Unexpected build configuration')
            archive.extractall(source, filter='data')
        package = json.loads((source / 'package.json').read_text())
        scripts = package.get('scripts', {})
        require(scripts.get('build') == 'react-scripts build' and not scripts.get('prebuild') and not scripts.get('postbuild'),
                'Unreviewed build lifecycle')
        lock = json.loads((source / 'package-lock.json').read_text())
        for entry in lock.get('packages', {}).values():
            resolved = entry.get('resolved', '')
            require(not resolved or resolved.startswith('https://registry.npmjs.org/'), 'Unreviewed package origin')
        path = d.run(['docker', 'exec', CONTAINER, 'mktemp', '-d', '/tmp/stroyka-qa-prebuild.XXXXXXXXXX']).strip()
        require(re.fullmatch(r'/tmp/stroyka-qa-prebuild\.[A-Za-z0-9]{10}', path), 'Unexpected staging path')
        self.container_path = path
        if getattr(d, 'diagnostics', None):
            d.diagnostics.resource('container_staging', path)
        self.cleanup_safe = False
        d.run(['docker', 'cp', str(source) + '/.', CONTAINER + ':' + path])
        env = build_environment(environment)
        env.update(HOME=path, NPM_CONFIG_CACHE=path + '/npm-cache')
        prefix = ['docker', 'exec', '-w', path, CONTAINER, 'env', '-i'] + [k+'='+v for k,v in sorted(env.items())]
        d.run(prefix + ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'])
        d.run(prefix + ['npm', 'run', 'build'])
        d.run(['docker', 'cp', CONTAINER + ':' + path + '/build', str(self.host / 'build')])
        self.cleanup_safe = True
        self.hashes = digest(self.host / 'build')
        return dict(self.hashes)

    def verify(self):
        require(self.host is not None and digest(self.host / 'build') == self.hashes,
                'Prepared frontend changed')

    def discard_unaccepted(self):
        # Exact resources allocated by this instance only; never unknown paths.
        if self.accepted:
            return
        if not self.cleanup_safe or (getattr(self.driver, 'diagnostics', None) and self.driver.diagnostics.uncertain):
            print('Uncertain builder outcome; retain owned staging for review: ' + str(self.host))
            return
        if self.container_path:
            self.driver.run(['docker', 'exec', CONTAINER, 'rm', '-rf', '--', self.container_path])
            self.container_path = None
        if self.host:
            require(self.host.parent == Path('/opt') and self.host.name.startswith('stroyka-qa-prebuild-')
                    and not self.host.is_symlink()
                    and (self.host.stat().st_dev, self.host.stat().st_ino) == self.host_identity,
                    'Unsafe staging cleanup path')
            shutil.rmtree(self.host)
            self.host = None
