import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fastapi import HTTPException
from .suggestions import parse_suggestion, request_suggestion_text


class SuggestionContractTests(unittest.TestCase):
    def test_suggestions_use_existing_gateway_with_bounded_deadline(self):
        for capability in ('material_inspection_suggestion','cable_journal_suggestion'):
            with self.subTest(capability=capability), patch(
                    'backend.features.quality_journals.suggestions.build_yandex_model_adapter') as factory:
                factory.return_value.generate.return_value=SimpleNamespace(output_text='{}')
                self.assertEqual(request_suggestion_text('Synthetic material',api_key='synthetic',
                    folder_id='synthetic-folder',capability=capability),'{}')
                request=factory.return_value.generate.call_args.args[0]
                self.assertEqual(request.capability,capability)
                self.assertEqual(request.deadline_seconds,20)
                self.assertEqual(request.max_output_tokens,1500)

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
