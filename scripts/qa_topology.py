"""User-observed QA metadata only. No credentials, filesystem reads or actions."""
BACKEND_IMAGE = 'sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5'
CADDY_IMAGE = 'sha256:d44355d3c2149dc580ce2cac735955d1c08d3d00882c30489c241aa51a5c10d9'
FRONTEND_VOLUME = '/var/lib/docker/volumes/stroyka-qa-frontend-work/_data'
TOPOLOGY = {
    'stroyka-qa-backend': (BACKEND_IMAGE, '/app', (('bind', '/opt/stroyka-jev-d1d1e2e', '/app', False),)),
    'stroyka-qa-backend-candidate': (BACKEND_IMAGE, '/app', (('bind', '/opt/stroyka-jev-qa-7e89d73', '/app', False),)),
    'stroyka-qa-db': ('sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54', '', ()),
    'stroyka-qa-frontend': ('sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0', '/app',
                           (('volume', FRONTEND_VOLUME, '/app', True),)),
    'stroyka-qa-static': (CADDY_IMAGE, '/srv', (('volume', FRONTEND_VOLUME, '/srv/app', False),
                        ('bind', '/tmp/stroyka-qa-static.Caddyfile', '/etc/caddy/Caddyfile', False))),
    'stroyka-qa-gateway': (CADDY_IMAGE, '/srv', (
        ('volume', '/var/lib/docker/volumes/stroyka-qa-caddy-data/_data', '/data', True),
        ('volume', '/var/lib/docker/volumes/stroyka-qa-caddy-config/_data', '/config', True),
        ('bind', '/opt/stroyka-qa-gateway/Caddyfile', '/etc/caddy/Caddyfile', False))),
}
QUIESCE = ('stroyka-qa-backend', 'stroyka-qa-backend-candidate',
           'stroyka-qa-frontend', 'stroyka-qa-gateway')


def validate_topology(observed):
    if set(observed) != set(TOPOLOGY):
        raise ValueError('QA inventory incomplete')
    for name, expected in TOPOLOGY.items():
        record = observed[name]
        mounts = []
        for m in record['mounts']:
            if type(m.get('RW')) is not bool:
                raise ValueError('QA mount write mode unknown')
            mounts.append((m['Type'], m['Source'], m['Destination'], m['RW']))
        if (record['image'], record['workdir'], tuple(sorted(mounts))) != (
                expected[0], expected[1], tuple(sorted(expected[2]))):
            raise ValueError('QA topology changed: ' + name)
    return True


def backup_manifest():
    """Unique physical sources. Sensitive contents must never enter chat/Library."""
    sources = {}
    for name, (_, _, mounts) in TOPOLOGY.items():
        for kind, source, destination, writable in mounts:
            item = sources.setdefault(source, {'source': source, 'type': kind,
                'consumers': [], 'confidential': True, 'export_contents': False})
            item['consumers'].append({'container': name, 'destination': destination, 'writable': writable})
    return {'sources': list(sources.values()),
            'database': {'container': 'stroyka-qa-db', 'database': 'stroyka_qa',
                         'mounts_observed': [], 'external_persistence_proven': False,
                         'preserve_container': True, 'backup_method': 'verified_logical_dump'},
            'quiesce': list(QUIESCE),
            'uploads': {'status': 'unresolved', 'code_relative_path': 'uploads',
                        'possible_container_path': '/app/uploads',
                        'local_bind_writable': False, 's3_possible': True},
            'execution_allowed': False}
