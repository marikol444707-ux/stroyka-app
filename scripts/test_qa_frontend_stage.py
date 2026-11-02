"""Filesystem fixtures + fake Docker only; no npm/network/containers."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin
from scripts.qa_frontend_stage import FrontendStage, build_environment


def archive(scripts=None, resolved='https://registry.npmjs.org/example/-/example-1.tgz'):
    output=io.BytesIO()
    files={'package.json':json.dumps({'scripts':scripts or {'build':'react-scripts build'}}),
           'package-lock.json':json.dumps({'packages':{'node_modules/example':{'resolved':resolved}}})}
    with tarfile.open(fileobj=output,mode='w') as tar:
        for name, content in files.items():
            data=content.encode(); item=tarfile.TarInfo(name); item.size=len(data)
            tar.addfile(item,io.BytesIO(data))
    return output.getvalue()


class FrontendStageTests(unittest.TestCase):
    def test_api_uses_confirmed_gateway_prefix_even_on_localhost(self):
        env=build_environment({})
        for page in ('http://localhost:8080/app','https://qa.example/app/projects/'):
            self.assertEqual(urljoin(page,env['REACT_APP_API_URL']+'/projects'),
                             page.split('/app')[0]+'/api/projects')
    def test_production_or_unknown_settings_rejected(self):
        for values in ({'REACT_APP_API_URL':'https://production.example'},
                       {'REACT_APP_TOKEN':'synthetic-secret'}, {'OTHER':'true'}):
            with self.assertRaises(ValueError): build_environment(values)
    def test_boolean_flags_preserved(self):
        self.assertEqual(build_environment({'REACT_APP_FEATURE_ENABLED':'true'})['REACT_APP_FEATURE_ENABLED'],'true')
    def test_builder_must_already_run(self):
        d=MagicMock(); d.inspect.return_value=False
        with self.assertRaises(ValueError): FrontendStage(d).prepare(b'',{})
        d.run.assert_not_called()
    def test_isolated_build_commands_and_digest(self):
        d=MagicMock(); d.inspect.return_value=True
        with tempfile.TemporaryDirectory() as folder:
            def run(args,**kwargs):
                if 'mktemp' in args: return '/tmp/stroyka-qa-prebuild.abcdefghij\n'
                if args[:2]==['docker','cp'] and args[2].endswith('/build'):
                    out=Path(args[3]); out.mkdir()
                    (out/'index.html').write_text('synthetic')
                    (out/'asset-manifest.json').write_text(json.dumps({'files':{'main':'/index.html'}}))
                return ''
            d.run.side_effect=run
            with patch('scripts.qa_frontend_stage.tempfile.mkdtemp',return_value=folder):
                stage=FrontendStage(d); stage.prepare(archive(),{})
            stage.verify()
            calls=[c.args[0] for c in d.run.call_args_list]
            self.assertFalse(any('start' in c or 'stop' in c for c in calls))
            self.assertFalse(any('/var/lib/docker/volumes' in str(c) or '-w /app' in str(c) for c in calls))
            npm=[c for c in calls if 'npm' in c]
            self.assertEqual(len(npm),2)
            for c in npm:
                self.assertIn('-i',c); self.assertIn('REACT_APP_API_URL=/api',c)
            self.assertIn('--ignore-scripts',npm[0])
            (Path(folder)/'build/index.html').write_text('changed')
            with self.assertRaises(ValueError): stage.verify()
    def test_unknown_dependency_origin_before_docker_commands(self):
        d=MagicMock(); d.inspect.return_value=True
        with tempfile.TemporaryDirectory() as folder, patch('scripts.qa_frontend_stage.tempfile.mkdtemp',return_value=folder):
            with self.assertRaises(ValueError): FrontendStage(d).prepare(archive(resolved='https://other.example/x'),{})
        d.run.assert_not_called()
    def test_unreviewed_build_script_rejected(self):
        d=MagicMock(); d.inspect.return_value=True
        with tempfile.TemporaryDirectory() as folder, patch('scripts.qa_frontend_stage.tempfile.mkdtemp',return_value=folder):
            with self.assertRaises(ValueError):
                FrontendStage(d).prepare(archive(scripts={'build':'react-scripts build','postbuild':'anything'}),{})
        d.run.assert_not_called()
    def test_accepted_artifact_not_discarded(self):
        d=MagicMock(); stage=FrontendStage(d); stage.accepted=True
        stage.container_path='/tmp/stroyka-qa-prebuild.abcdefghij'
        stage.discard_unaccepted(); d.run.assert_not_called()

    def test_uncertain_builder_outcome_preserves_staging(self):
        d=MagicMock(); stage=FrontendStage(d)
        stage.cleanup_safe=False
        stage.host=Path('/synthetic-owned-stage')
        stage.container_path='/tmp/stroyka-qa-prebuild.abcdefghij'
        with patch('builtins.print'), patch('scripts.qa_frontend_stage.shutil.rmtree') as remove:
            stage.discard_unaccepted()
        d.run.assert_not_called(); remove.assert_not_called()
