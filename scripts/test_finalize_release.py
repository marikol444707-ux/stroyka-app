import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('finalizer',Path(__file__).with_name('finalize_release.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class VerificationGateTests(unittest.TestCase):
    def test_only_complete_checks_for_exact_release_allow_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            self.assertFalse(module.verification_passed(path,'abc'))
            evidence={'head':'abc','checks':dict.fromkeys(('backend','database','frontend','browser'),True)}
            (path/'verified.json').write_text(json.dumps(evidence))
            self.assertTrue(module.verification_passed(path,'abc'))
            self.assertFalse(module.verification_passed(path,'different-release'))
            for key in evidence['checks']:
                failed={**evidence,'checks':{**evidence['checks'],key:False}}
                (path/'verified.json').write_text(json.dumps(failed))
                self.assertFalse(module.verification_passed(path,'abc'))
            (path/'verified.json').write_text('{broken')
            self.assertFalse(module.verification_passed(path,'abc'))

if __name__=='__main__':unittest.main()
