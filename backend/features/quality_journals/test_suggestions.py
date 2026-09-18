import json
import unittest

from fastapi import HTTPException
from .suggestions import parse_suggestion


class SuggestionContractTests(unittest.TestCase):
    def test_exact_json_shape(self):
        self.assertEqual(parse_suggestion('{"normatives":" X ","requiredDocs":" Y "}', 'material_inspection_journal'),
                         {'normatives': 'X', 'requiredDocs': 'Y'})

    def test_invalid_output_is_rejected(self):
        for text in ('', '```json\n{}\n```', '[]', 'null',
                     '{"normatives":"a","normatives":"b","requiredDocs":"c"}',
                     '{"normatives":{},"requiredDocs":"c"}',
                     json.dumps({'normatives': 'x'*2001, 'requiredDocs': ''}),
                     '{"normatives":"x","requiredDocs":"x","extra":"x"}'):
            with self.subTest(text=text[:40]), self.assertRaises(HTTPException) as error:
                parse_suggestion(text, 'material_inspection_journal')
            self.assertEqual(error.exception.status_code, 502)
