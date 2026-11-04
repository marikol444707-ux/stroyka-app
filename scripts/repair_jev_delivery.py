"""Explicit one-file repair for the installed, tool-exposure-repaired JEV.

Uses Hermes' native in-memory profile secret scope. No key copying, token
printing, container/config changes, result replay or delivery receipt edits.
Only the host workers restart; retain rollback until real Telegram acceptance.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import stat
import urllib.request

REPOSITORY = 'marikol444707-ux/stroyka-app'
BRANCH = 'jev-tender-finder-audit-contract-20261028'

REPAIR_REV = 'dfc68b84d6ac4481cd85718c6014bf3586fd3a60'
REPAIR_SHA = '73e5019b483d0becbe76615e9b0dfbb1d6762a0ac97cbfdc43f3372efb3f8dd8'
TARGET = 'jev_agent/tender_finder/docker_delivery.py'
OLD_SHA = '9d5ab6593fc20bc68e3c5a13e098b180ae13abbbbdd68bdb4cc472b809f785c8'
NEW_SHA = 'c3edc6b7728a32876b765fa5dfe7e5314e2cf48cbc47b04b8ea1e12166ae147c'

# Exact addition only; its removal reconstructs the reviewed f214 transport.
PROFILE_FUNCTION = '''
def _profile_sender(sender):
    # A standalone docker exec does not inherit gateway startup's credential
    # initialization. Resolve ONLY this supported default Hermes profile using
    # its own SDK, in memory; never copy credentials into JEV or os.environ.
    def send(args):
        from pathlib import Path
        from hermes_constants import get_hermes_home
        from agent.secret_scope import (
            build_profile_secret_scope, set_secret_scope, reset_secret_scope,
        )
        home = Path('/opt/data')
        if (get_hermes_home() != home or os.environ.get('HERMES_PROFILE')
                or os.environ.get('HERMES_HOME') != str(home)):
            raise ValueError('reviewed_default_hermes_profile_required')
        token = set_secret_scope(build_profile_secret_scope(home), profile_home=str(home))
        try:
            return sender(args)
        finally:
            reset_secret_scope(token)
    return send
'''


def patched(raw, sha):
    if sha(raw) != OLD_SHA:
        raise ValueError('exact_original_delivery_required')
    new = raw.replace(b'return module.send_message_tool', b'return _profile_sender(module.send_message_tool)')
    new = new.replace(b'\ndef main():', PROFILE_FUNCTION.encode() + b'\ndef main():')
    if sha(new) != NEW_SHA:
        raise ValueError('exact_profile_delivery_patch_required')
    compile(new, TARGET, 'exec')
    return new


def verify_ci_api(commit):
    """Verify exact source CI via official JSON, independent of GitHub's UI.

    No credentials, skip flag, cached success, or fallback to a different SHA.
    The first matching run must be completed successfully, just as before.
    """
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('full_pinned_revision_required')
    url = ('https://api.github.com/repos/' + REPOSITORY +
           '/actions/workflows/ci.yml/runs?head_sha=' + commit + '&per_page=10')
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.url != url:
            raise ValueError('github_ci_origin_changed')
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('github_ci_response_limit')
    data = json.loads(raw)
    if type(data) is not dict or type(data.get('workflow_runs')) is not list:
        raise ValueError('github_ci_response_required')
    for row in data['workflow_runs']:
        if (type(row) is not dict or row.get('head_sha') != commit
                or row.get('head_branch') != BRANCH or row.get('path') != '.github/workflows/ci.yml'
                or row.get('event') != 'push' or type(row.get('repository')) is not dict
                or row['repository'].get('full_name') != REPOSITORY):
            continue
        if row.get('status') != 'completed' or row.get('conclusion') != 'success':
            raise ValueError('exact_source_ci_not_successful')
        link = row.get('html_url')
        if not re.fullmatch(r'https://github\.com/marikol444707-ux/stroyka-app/actions/runs/[0-9]+', str(link)):
            raise ValueError('exact_source_ci_url_required')
        return link
    raise ValueError('exact_source_ci_unconfirmed')


def activation_source(raw):
    # The pinned operator's stage/source/policy checks remain byte-identical.
    # Bind ONLY its CI verifier to the equivalent strict official API reader;
    # never edit the authenticated old stage or replace its global module.
    old = b'from jev_agent.tender_finder.standalone_release import verify_ci,_save,root_broker_probe'
    new = b'from jev_agent.tender_finder.standalone_release import _save,root_broker_probe'
    if raw.count(old) != 1:
        raise ValueError('exact_activation_ci_import_required')
    return raw.replace(old, new)


def remote_probe(raw):
    tree = ast.parse(raw)
    program = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(t, ast.Name) and t.id == 'REMOTE_PROGRAM' for t in node.targets))
    return ("import contextlib,json,os; ns={'__name__':'delivery_configuration_probe'}; exec(" + repr(program) + ",ns); "
            "\nwith open(os.devnull,'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):\n"
            "    ns['_load_sender']()\n"
            "    def ready(_):\n"
            "        from gateway.config import load_gateway_config, Platform\n"
            "        return bool(getattr(load_gateway_config().platforms.get(Platform.TELEGRAM),'token',None))\n"
            "    ok=ns['_profile_sender'](ready)({})\n"
            "print(json.dumps({'profile_credentials_ready':ok,'notifications_sent':False}))\n")


class DeliveryRepair:
    def __init__(self, helper, *, _probe=None):
        self.h = helper
        self.op = helper.op
        self.base = helper.base
        self.path = helper.path('/opt/stroyka-jev/app/' + TARGET)
        self.journal = helper.stage / 'delivery-profile-repair.json'
        self.backup = helper.stage / 'delivery-profile-backup.py'
        self.before = dict(helper.bundle['candidate'])
        if self.before.get(TARGET) != OLD_SHA:
            raise ValueError('reviewed_previous_delivery_required')
        self.after = {**self.before, TARGET: NEW_SHA}
        self.probe = _probe or self.credentials_probe

    def save(self, state):
        self.h.bundle['save'](self.journal, state)

    def credentials_probe(self, raw):
        identifier = self.h.bundle['container']()
        output = self.base.run('/usr/bin/docker', '--host=unix:///var/run/docker.sock', 'exec',
            '--user', '10000:10000', '--workdir', '/opt/hermes',
            '--env', 'HOME=/opt/data', '--env', 'HERMES_HOME=/opt/data', '--env', 'HERMES_PROFILE=',
            identifier, '/opt/hermes/.venv/bin/python', '-I', '-B', '-c', remote_probe(raw))
        if output != b'{"profile_credentials_ready": true, "notifications_sent": false}\n':
            raise ValueError('native_profile_credentials_not_confirmed')

    def status(self):
        state = json.loads(self.h.read(self.journal, private=True))
        if (state.get('kind') != 'JEV_DELIVERY_PROFILE_REPAIR'
                or state.get('old_sha') != OLD_SHA or state.get('new_sha') != NEW_SHA
                or state.get('phase') not in ('backed_up', 'stopping', 'patched', 'ready_unverified', 'rolled_back')
                or type(state.get('maintenance')) is not bool or type(state.get('source_intent')) is not bool
                or not re.fullmatch('[a-f0-9]{64}', str(state.get('container', '')))):
            raise ValueError('owned_delivery_repair_journal_required')
        return state

    def stop(self):
        self.base.run('/usr/bin/systemctl', 'stop', *self.op.NEW, *self.op.OLD)
        self.base.stopped(self.op.OLD + self.op.NEW)

    def start(self):
        self.base.run('/usr/bin/systemctl', 'start', *self.op.OLD, *self.op.NEW)
        self.base.healthy(self.op.OLD + self.op.NEW)

    def apply(self):
        if self.journal.exists():
            raise ValueError('existing_delivery_repair_requires_review')
        if self.h.state()['phase'] != 'repaired_unverified':
            raise ValueError('successful_tool_exposure_repair_required')
        self.h.snapshot(self.before); self.h.units_ready()
        original = self.h.read(self.path)
        new = patched(original, self.op.sha)
        self.probe(new)  # Resolve credentials only; never invoke send_message.
        identifier = self.h.bundle['container']()
        self.h.bundle['peer']()
        if self.backup.exists():
            raise ValueError('existing_delivery_backup_requires_review')
        self.op.atomic_file(self.backup, original, 0o600, 0, uid=self.h.uid)
        state = {'kind': 'JEV_DELIVERY_PROFILE_REPAIR', 'phase': 'backed_up',
                 'old_sha': OLD_SHA, 'new_sha': NEW_SHA, 'container': identifier,
                 'maintenance': False, 'source_intent': False}
        self.save(state)
        self.h.snapshot(self.before); self.h.units_ready()
        state.update(maintenance=True, phase='stopping'); self.save(state)
        self.stop()
        self.h.snapshot(self.before)
        if self.h.bundle['container']() != identifier:
            raise ValueError('container_identity_changed')
        state['source_intent'] = True; self.save(state)
        self.op.atomic_file(self.path, new, 0o644, 0, uid=self.h.uid)
        state['phase'] = 'patched'; self.save(state)
        self.h.snapshot(self.after)
        self.probe(new)
        self.start()
        if self.h.bundle['container']() != identifier:
            raise ValueError('container_identity_changed')
        state['phase'] = 'ready_unverified'; self.save(state)
        return {'repaired': True, 'source_files_updated': 1, 'profile_credentials_ready': True,
                'container_restarted': False, 'keys_copied': False, 'notifications_sent': False,
                'unknown_delivery_retried': False, 'real_telegram_acceptance': False,
                'installation_ready': False, 'backups_retained': True}

    def rollback(self):
        state = self.status()
        current = self.op.sha(self.h.read(self.path))
        if current not in (OLD_SHA, NEW_SHA):
            raise ValueError('foreign_delivery_change_blocks_rollback')
        self.h.snapshot(self.before if current == OLD_SHA else self.after)
        original = self.h.read(self.backup, private=True)
        if self.op.sha(original) != OLD_SHA:
            raise ValueError('delivery_backup_changed')
        if self.h.bundle['container']() != state['container']:
            raise ValueError('container_identity_changed')
        if state['maintenance']:
            self.stop()
            if state['source_intent']:
                self.op.atomic_file(self.path, original, 0o644, 0, uid=self.h.uid)
            self.h.snapshot(self.before)
            self.start()
        state['phase'] = 'rolled_back'; self.save(state)
        return {'restored': True, 'data_restored': False, 'receipts_unchanged': True, 'backups_retained': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--operation', choices=('apply', 'rollback'), required=True)
    args = parser.parse_args(argv)
    repair = None; lock = None; fresh = False
    try:
        if os.geteuid() != 0 or not __import__('sys').flags.isolated:
            raise ValueError('isolated_root_operator_required')
        if not re.fullmatch('[a-f0-9]{40}', args.revision):
            raise ValueError('full_pinned_revision_required')
        # Use only the already-reviewed operators, authenticated by content.
        import hashlib, urllib.request
        def download(name, rev, digest):
            with urllib.request.urlopen('https://raw.githubusercontent.com/marikol444707-ux/stroyka-app/' + rev + '/' + name, timeout=25) as response:
                raw = response.read(200000)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('pinned_operator_source_required')
            return raw
        ns = {'__name__': 'verified_visibility_operator'}
        exec(compile(download('scripts/repair_jev_tool_exposure.py', REPAIR_REV, REPAIR_SHA), 'verified-visibility', 'exec'), ns)
        previous = type('VerifiedVisibility', (), ns)
        base_ns = {'__name__': 'verified_activation_operator', 'verify_ci': verify_ci_api}
        activation = download('scripts/activate_jev_commercial.py', previous.BASE_REV, previous.BASE_SHA)
        exec(compile(activation_source(activation), 'verified-activation', 'exec'), base_ns)
        operator = type('VerifiedOperator', (), base_ns)
        bundle = operator.bootstrap(args.stage)
        verify_ci_api(args.revision)
        lock = os.open('/run/stroyka-jev/operator-upgrade.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('protected_operator_lock_required')
        operator.fcntl.flock(lock, operator.fcntl.LOCK_EX | operator.fcntl.LOCK_NB)
        patches = {name: download(name, previous.PATCH_REV, digest) for name, digest in previous.PATCHES.items()}
        helper = previous.Repair(operator, bundle, patches)
        repair = DeliveryRepair(helper); fresh = not repair.journal.exists()
        result = repair.apply() if args.operation == 'apply' else repair.rollback()
        print(json.dumps(result)); return 0
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z_]{1,100}', str(error)) else type(error).__name__
        result = {'repaired': False, 'code': code, 'installation_ready': False, 'backups_retained': True}
        if args.operation == 'apply' and fresh and repair is not None and repair.journal.exists():
            try: result['rollback'] = repair.rollback()
            except Exception as rollback_error: result['rollback'] = {'restored': False, 'code': type(rollback_error).__name__}
        print(json.dumps(result)); return 1
    finally:
        if lock is not None: os.close(lock)


if __name__ == '__main__':
    raise SystemExit(main())
