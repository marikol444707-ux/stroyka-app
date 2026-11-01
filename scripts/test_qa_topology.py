import unittest
from scripts.qa_topology import TOPOLOGY, QUIESCE, FRONTEND_VOLUME, backup_manifest, validate_topology
from scripts.test_qa_server_adapter import make


def observed():
    return {n: {'image': i, 'workdir': w,
                'mounts': [dict(Type=k, Source=s, Destination=d, RW=rw) for k,s,d,rw in m]}
            for n,(i,w,m) in TOPOLOGY.items()}


class TopologyTests(unittest.TestCase):
    def test_observed_topology_and_single_shared_frontend_backup(self):
        self.assertTrue(validate_topology(observed()))
        manifest = backup_manifest()
        volume = [x for x in manifest['sources'] if x['source'] == FRONTEND_VOLUME]
        self.assertEqual(len(volume), 1)
        self.assertEqual(len(volume[0]['consumers']), 2)
        self.assertFalse(manifest['database']['external_persistence_proven'])
        self.assertTrue(manifest['database']['preserve_container'])

    def test_image_rw_extra_mount_changes_block(self):
        for change in ('image', 'rw', 'extra'):
            data = observed()
            if change == 'image':
                data['stroyka-qa-db']['image'] = 'different'
            elif change == 'rw':
                data['stroyka-qa-backend']['mounts'][0]['RW'] = True
            else:
                data['stroyka-qa-db']['mounts'].append(dict(Type='volume', Source='/unknown', Destination='/data', RW=True))
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_topology(data)

    def test_no_db_recreation_stop_or_exec_writes(self):
        a = make()
        for argv in [('docker','rm','stroyka-qa-db'), ('docker','run','image'),
                     ('docker','stop','stroyka-qa-db'), ('docker','exec','stroyka-qa-backend','touch','/app/x'),
                     ('docker','volume','prune')]:
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                a._run(argv)
        a.transport.run.assert_not_called()

    def test_protected_contents_and_uploads_not_assumed(self):
        m = backup_manifest()
        self.assertTrue(all(x['confidential'] and not x['export_contents'] for x in m['sources']))
        self.assertEqual(m['uploads']['status'], 'unresolved')
        self.assertFalse(m['uploads']['local_bind_writable'])
        self.assertIn('stroyka-qa-frontend', QUIESCE)
        self.assertIn('stroyka-qa-gateway', QUIESCE)
        self.assertNotIn('stroyka-qa-db', QUIESCE)
