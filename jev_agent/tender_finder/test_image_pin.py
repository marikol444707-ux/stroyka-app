import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from .image_pin import BASE_IMAGE,load_pin,snapshot_pin
from .docker_delivery import check_hermes_container
from . import test_docker_delivery as fixtures

SNAPSHOT='sha256:'+'b'*64
STOPPED={'Id':'a'*64,'Image':BASE_IMAGE,'State':{'Running':False}}


class ImagePinTests(unittest.TestCase):
    def test_stopped_snapshot_requires_exact_base_parent_and_source_identity(self):
        pin=snapshot_pin(STOPPED,{'Id':SNAPSHOT,'Parent':BASE_IMAGE})
        self.assertEqual(pin['snapshot_image'],SNAPSHOT)
        for source,image in (({**STOPPED,'State':{'Running':True}},{'Id':SNAPSHOT,'Parent':BASE_IMAGE}),
            (STOPPED,{'Id':SNAPSHOT,'Parent':'sha256:'+'c'*64}),(STOPPED,{'Id':BASE_IMAGE,'Parent':BASE_IMAGE})):
            with self.assertRaises(ValueError):snapshot_pin(source,image)

    def test_private_pin_loader_checks_modes_links_owner_and_schema_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'pin.json'
            read=lambda:load_pin(_path=path,_uid=os.geteuid(),_trusted_root=root)
            self.assertIsNone(read())
            pin=snapshot_pin(STOPPED,{'Id':SNAPSHOT,'Parent':BASE_IMAGE})
            path.write_text(json.dumps(pin));path.chmod(0o600)
            self.assertEqual(read(),pin)
            path.chmod(0o640)
            with self.assertRaises(ValueError):read()
            path.chmod(0o600);alias=root/'alias';os.link(path,alias)
            with self.assertRaises(ValueError):read()
            alias.unlink();path.write_text(json.dumps({**pin,'source_stopped':False}))
            with self.assertRaises(ValueError):read()
            path.unlink();path.symlink_to(root/'missing')
            with self.assertRaises((ValueError,FileNotFoundError)):read()

    def test_snapshot_container_requires_private_pin_and_fresh_exact_parent_attestation(self):
        pin=snapshot_pin(STOPPED,{'Id':SNAPSHOT,'Parent':BASE_IMAGE})
        run=Mock(side_effect=[(json.dumps({'id':SNAPSHOT,'parent':BASE_IMAGE}).encode(),0),
                              (fixtures.metadata(image=SNAPSHOT),0)])
        with patch('jev_agent.tender_finder.docker_delivery.load_pin',return_value=pin):
            self.assertEqual(check_hermes_container(_run=run),'a'*64)
        self.assertIn(SNAPSHOT,run.call_args_list[0].args[0])
        bad=Mock(return_value=(json.dumps({'id':SNAPSHOT,'parent':'wrong'}).encode(),0))
        with patch('jev_agent.tender_finder.docker_delivery.load_pin',return_value=pin):
            with self.assertRaises(ValueError):check_hermes_container(_run=bad)
        bad.assert_called_once()

    def test_untrusted_pin_is_not_silently_ignored_even_for_original_image(self):
        run=Mock(return_value=(fixtures.metadata(),0))
        with patch('jev_agent.tender_finder.docker_delivery.load_pin',side_effect=ValueError('unsafe')):
            with self.assertRaises(ValueError):check_hermes_container(_run=run)
        run.assert_not_called()


if __name__=='__main__':unittest.main()
