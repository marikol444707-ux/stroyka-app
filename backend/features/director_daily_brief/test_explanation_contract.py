import json
import unittest

from backend.features.director_daily_brief.explanation_contract import (
    DirectorDailyBriefExplanationError,
    build_explanation_model_input,
    parse_explanation_model_output,
    public_daily_brief_explanation,
)
from backend.features.director_daily_brief.test_query_service import valid_result


class DirectorDailyBriefExplanationContractTests(unittest.TestCase):
    def test_builds_canonical_input_only_from_the_public_brief(self):
        brief = valid_result()
        brief["private"] = {"apiKey": "must-not-pass"}

        first = build_explanation_model_input(brief)
        second = build_explanation_model_input(brief)
        payload = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(set(payload), {"schemaVersion", "briefDate", "summary", "sections"})
        self.assertNotIn("private", first)
        self.assertNotIn("apiKey", first)
        self.assertLessEqual(len(first.encode("utf-8")), 32 * 1024)

    def test_accepts_bounded_text_linked_to_existing_source_codes(self):
        result = parse_explanation_model_output(
            json.dumps({
                "headline": "Есть вопросы, требующие внимания",
                "overview": "Сначала проверьте сроки объекта и остаток кабеля.",
                "points": [
                    {
                        "sourceCode": "project.deadline_overdue",
                        "text": "Срок объекта уже требует внимания.",
                    },
                    {
                        "sourceCode": "warehouse.below_minimum",
                        "text": "Остаток материала ниже установленного уровня.",
                    },
                ],
            }, ensure_ascii=False),
            source_job_id=17,
            brief=valid_result(),
        )

        self.assertEqual(result["schemaVersion"], 1)
        self.assertEqual(result["sourceJobId"], 17)
        self.assertEqual(len(result["points"]), 2)

    def test_rejects_untrusted_or_unverifiable_model_output(self):
        cases = (
            {"headline": "Итог 99", "overview": "Без изменений", "points": []},
            {"headline": "<b>Важно</b>", "overview": "Без изменений", "points": []},
            {"headline": "Важно", "overview": "Без изменений", "points": [
                {"sourceCode": "unknown.code", "text": "Неизвестный факт."}
            ]},
            {"headline": "Важно", "overview": "Без изменений", "points": [], "action": "pay"},
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(DirectorDailyBriefExplanationError):
                    parse_explanation_model_output(
                        json.dumps(value, ensure_ascii=False),
                        source_job_id=17,
                        brief=valid_result(),
                    )

    def test_rejects_invalid_source_job_or_malformed_brief_before_output(self):
        output = '{"headline":"Важно","overview":"Проверьте сводку.","points":[]}'
        with self.assertRaises(DirectorDailyBriefExplanationError):
            parse_explanation_model_output(output, source_job_id=0, brief=valid_result())

        brief = valid_result()
        brief["sections"] = []
        with self.assertRaises(DirectorDailyBriefExplanationError):
            build_explanation_model_input(brief)

    def test_validates_a_stored_explanation_for_the_exact_source(self):
        stored = {
            "schemaVersion": 1,
            "sourceJobId": 17,
            "headline": "Есть вопросы, требующие внимания",
            "overview": "Проверьте сроки объекта.",
            "points": [{
                "sourceCode": "project.deadline_overdue",
                "text": "Срок объекта требует проверки.",
            }],
        }
        self.assertEqual(
            public_daily_brief_explanation(
                stored, source_job_id=17, brief=valid_result()
            ),
            stored,
        )
        with self.assertRaises(DirectorDailyBriefExplanationError):
            public_daily_brief_explanation(
                stored, source_job_id=18, brief=valid_result()
            )


if __name__ == "__main__":
    unittest.main()
