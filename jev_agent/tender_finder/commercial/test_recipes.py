from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest

from .recipes import parse_recipes,load_recipes
from .model import Profile
from .portal_reader import source_bundle
from .test_commercial import NOW


def recipe(key='tenderpro'):
    # Synthetic operator configuration; not the real Tender.Pro URL.
    return {'source_id':key,'hosts':['owner.example'],'listings':['https://owner.example/procurement'],
            'reviewer_subject':'fixture-reviewer','review_evidence_url':'https://owner.example/about',
            'notice_path':'/notice.html','notice_query_key':'notice_id'}


class RecipesTests(unittest.TestCase):
    def parse(self,rows=None):return parse_recipes({'format':1,'portals':[recipe()] if rows is None else rows})

    def test_tenderpro_and_all_named_owners_join_one_packet_without_code_changes(self):
        keys=('tenderpro','ozon','agrokompleks','progress','ecoculture','rusagro','yugrusi','pokrovsky','resurs','damate')
        compiled=self.parse([recipe(key) for key in keys])
        sources,adapters=source_bundle(open_browser=lambda _:None,clock=lambda:NOW,
            reviewed_recipes=compiled.factories,extra_sources=compiled.extra_sources)
        self.assertEqual(len(adapters),19)
        self.assertTrue(set(keys)<=set(adapters))
        self.assertEqual(sources['step'].hosts,('ahstep.ru','www.ahstep.ru'))

    def test_data_recipe_cannot_run_python_shell_or_override_native(self):
        for row in ({**recipe(),'command':'fake'},{**recipe(),'source_id':'b2b'},
                    {**recipe(),'notice_path':'/notice','notice_query_key':'__import__(os)'}):
            with self.assertRaises(ValueError):self.parse([row])

    def test_exact_query_notice_identity_and_public_domain_only(self):
        spec=self.parse().factories['tenderpro'](Profile(),NOW)
        self.assertEqual(spec.approve('https://owner.example/notice.html?notice_id=fixture123'),'card')
        for url in ('https://owner.example/notice.html?notice_id=1&delete=1',
                    'https://attacker.example/notice.html?notice_id=1'):
            with self.assertRaises(ValueError):spec.approve(url)

    def test_unknown_owner_can_be_added_but_requires_explicit_metadata(self):
        row={**recipe('new-owner'),'name':'Синтетический санаторий','category':'owner'}
        compiled=self.parse([row]);self.assertEqual(compiled.extra_sources[0].id,'new-owner')
        with self.assertRaises(ValueError):self.parse([recipe('new-owner')])

    def test_literal_path_is_escaped_not_executed_as_user_regex(self):
        row={**recipe(),'notice_path':'/notice(unsafe)','notice_query_key':None}
        spec=self.parse([row]).factories['tenderpro'](Profile(),NOW)
        self.assertEqual(spec.approve('https://owner.example/notice(unsafe)/123'),'card')
        with self.assertRaises(ValueError):spec.approve('https://owner.example/noticeunsafe/123')

    def test_search_parameter_is_encoded_and_preserves_both_regions(self):
        row={**recipe(),'search_query_parameter':'search'}
        spec=self.parse([row]).factories['tenderpro'](Profile(queries=('кровля',)),NOW)
        self.assertEqual(len(spec.listings),3)
        self.assertTrue(all('search=' in url for url in spec.listings))

    def test_private_configuration_file_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'portals.json'
            path.write_text(json.dumps({'format':1,'portals':[recipe()]}));path.chmod(0o600)
            bindings={'trusted_root':root,'expected_uid':os.geteuid(),'system_uid':Path('/').stat().st_uid}
            self.assertIn('tenderpro',load_recipes(path,**bindings).factories)
            path.chmod(0o644)
            with self.assertRaises(ValueError):load_recipes(path,**bindings)


if __name__=='__main__':unittest.main()
