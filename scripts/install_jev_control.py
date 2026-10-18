"""Install the owner-authorized standalone Jev controller on the QA host.

Builds a tiny layer on the already verified worker image. Secrets remain on-host;
the source experiments stay untouched until acceptance is completed separately.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

BASE_IMAGE = 'sha256:b7f889ef13bbb1cae05569d078e2deb9c91b3dc1f0e15cc562b15d2e62cffc04'
CONTAINER = 'stroyka-jev-control'


def docker_json(*args):
    return json.loads(subprocess.check_output(['docker', *args]))


def control_environment(source: dict, text_source: dict) -> dict:
    env = {'TIMEWEB_AI_API_KEY': source['TIMEWEB_AI_API_KEY'],
           'DEV_CONTROL_API_TOKEN': secrets.token_hex(32),
           'QA_BASE_URL': 'http://127.0.0.1:8080', 'QA_ENVIRONMENT': 'test'}
    for key in ('JEV_SYSTEMONE_URL', 'JEV_MODEL'):
        if source.get(key):
            env[key] = source[key]
    if text_source.get('TIMEWEB_TEXT_MODEL'):
        if text_source.get('TIMEWEB_AI_API_KEY') != source['TIMEWEB_AI_API_KEY']:
            raise ValueError('Text model belongs to a different credential')
        env['TIMEWEB_TEXT_MODEL'] = text_source['TIMEWEB_TEXT_MODEL']
    # Preserve the existing host-specific Chrome setting; do not broaden it.
    if source.get('CHROME_NO_SANDBOX') == '1':
        env['CHROME_NO_SANDBOX'] = '1'
    if any('\n' in value or '\r' in value for value in env.values()):
        raise ValueError('Invalid multiline runtime configuration')
    return env


def main():
    if os.geteuid() != 0:
        raise PermissionError('Run as root on the QA host')
    repo = Path(__file__).resolve().parent.parent
    sources = {name: docker_json('inspect', name)[0] for name in
               ('stroyka-jev-qa-ca-test', 'stroyka-jev-dialog-test')}
    source = sources['stroyka-jev-qa-ca-test']
    if source['Image'] != BASE_IMAGE:
        raise ValueError('Source worker image changed; review before installing')
    def values(container):
        return dict(item.split('=', 1) for item in container['Config']['Env'] if '=' in item)
    environment = control_environment(values(source), values(sources['stroyka-jev-dialog-test']))
    existing = subprocess.run(['docker', 'inspect', CONTAINER], capture_output=True)
    if existing.returncode == 0:
        raise ValueError('Controller already exists; refusing to replace it')
    task = (repo / 'dev_control/browser_worker/control_task.py').read_bytes()
    digest = hashlib.sha256(task).hexdigest()[:16]
    image = 'stroyka-jev-worker:control-' + digest
    base_tag = 'stroyka-jev-worker:control-reviewed-base'
    subprocess.run(['docker', 'tag', BASE_IMAGE, base_tag], check=True)
    with tempfile.TemporaryDirectory(prefix='jev-control-build-') as directory:
        context = Path(directory)
        (context / 'control_task.py').write_bytes(task)
        (context / 'Dockerfile').write_text('FROM ' + base_tag + '\n'
            'COPY --chown=root:root control_task.py /app/dev_control/browser_worker/control_task.py\n'
            'RUN chmod 644 /app/dev_control/browser_worker/control_task.py\n')
        subprocess.run(['docker', 'build', '--pull=false', '-t', image, str(context)], check=True)
        credentials = context / 'runtime.env'
        credentials.write_text(''.join(key + '=' + value + '\n' for key, value in environment.items()))
        credentials.chmod(0o600)
        subprocess.run(['docker', 'run', '-d', '--name', CONTAINER, '--init',
            '--restart', 'unless-stopped', '--memory', '1g', '--pids-limit', '384',
            '-p', '127.0.0.1:18090:8080', '--env-file', str(credentials), image], check=True)
    destination = Path('/usr/local/libexec/stroyka-jev-control')
    destination.mkdir(mode=0o755, parents=True, exist_ok=True)
    (destination / 'jev_control.py').write_bytes((repo / 'scripts/jev_control.py').read_bytes())
    (destination / 'jev_control.py').chmod(0o644)
    state = Path('/var/lib/stroyka-jev-control')
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    (state / 'installation.json').write_text(json.dumps({'image': image, 'base_image': BASE_IMAGE,
        'task_sha256': hashlib.sha256(task).hexdigest(), 'port': 18090}))
    print('CONTROL_INSTALLED: watchdog remains disabled until browser acceptance')


if __name__ == '__main__':
    main()
