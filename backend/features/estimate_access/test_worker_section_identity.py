"""Exercise the actual legacy sanitizer without starting the application/database."""
import ast
from pathlib import Path
import unittest


class WorkerSectionIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[2] / 'main.py'
        names = {'_estimate_item_key_candidates', '_worker_estimate_item_kind_for_sanitize',
                 '_sanitize_worker_estimate_sections'}
        tree = ast.parse(source.read_text(encoding='utf-8'))
        module = ast.Module(body=[node for node in tree.body
                                 if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
        namespace = {}
        exec(compile(module, str(source), 'exec'), namespace)
        cls.sanitize = staticmethod(namespace['_sanitize_worker_estimate_sections'])

    def test_filtered_sections_keep_original_contract_identity_and_hide_money(self):
        sections = [
            {'name': 'Материалы', 'items': [{'name': 'Кабель', 'type': 'material'}]},
            {'name': 'Монтаж', 'items': [
                {'name': 'Не назначено', 'type': 'work'},
                {'name': 'Розетка', 'type': 'work', 'priceWork': 900, 'quantity': 10},
            ]},
        ]
        rows = self.sanitize(sections, [{'estimate_item_key': '72:1:1'}], estimate_id=72)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['items'], [{'name': 'Розетка', 'type': 'work', 'priceWork': 0,
                                           'quantity': 10, 'estimateItemKey': '72:1:1'}])
        self.assertNotIn('estimateItemKey', sections[1]['items'][1])

    def test_contract_key_wins_over_an_unrelated_item_id(self):
        sections = [{'name': 'Монтаж', 'items': [{'id': 123, 'workKey': 'socket-377', 'name': 'Розетка'}]}]
        result = self.sanitize(sections, [{'estimate_item_key': 'socket-377'}], estimate_id=72)
        self.assertEqual(result[0]['items'][0]['estimateItemKey'], 'socket-377')

    def test_existing_stable_key_survives_without_contract_filter(self):
        sections = [{'name': 'Монтаж', 'items': [{'estimateItemKey': 'stable', 'name': 'Розетка'}]}]
        self.assertEqual(self.sanitize(sections, estimate_id=72)[0]['items'][0]['estimateItemKey'], 'stable')


if __name__ == '__main__':
    unittest.main()
