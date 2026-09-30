import json
import unittest
from types import SimpleNamespace

from backend.features.director_daily_brief.explanation_model import (
    generate_daily_brief_explanation,
)
from backend.features.director_daily_brief.test_query_service import valid_result
from backend.features.model_gateway.contract import MODEL_GATEWAY_PROVIDER_FAILED, ModelGatewayError


class DirectorDailyBriefExplanationModelTests(unittest.TestCase):
    def test_uses_director_gateway_capability_and_validates_result(self):
        captured = {}

        class Gateway:
            def generate(self, request):
                captured["request"] = request
                return SimpleNamespace(output_text=json.dumps({
                    "headline": "Есть вопросы, требующие внимания",
                    "overview": "Проверьте сроки объекта и остатки материалов.",
                    "points": [{
                        "sourceCode": "project.deadline_overdue",
                        "text": "Срок объекта требует проверки руководителем.",
                    }],
                }, ensure_ascii=False))

        result = generate_daily_brief_explanation(
            brief=valid_result(),
            source_job_id=17,
            api_key="private",
            folder_id="folder-1",
            adapter_factory=lambda **kwargs: Gateway(),
        )

        request = captured["request"]
        self.assertEqual(request.capability, "director_agent")
        self.assertEqual(request.temperature, 0.0)
        self.assertEqual(request.max_output_tokens, 700)
        self.assertNotIn("private", request.input_text)
        self.assertEqual(result["sourceJobId"], 17)

    def test_normalizes_unexpected_transport_failure(self):
        def broken_factory(**kwargs):
            raise RuntimeError("secret provider detail")

        with self.assertRaises(ModelGatewayError) as caught:
            generate_daily_brief_explanation(
                brief=valid_result(),
                source_job_id=17,
                api_key="private",
                folder_id="folder-1",
                adapter_factory=broken_factory,
            )

        self.assertEqual(caught.exception.code, MODEL_GATEWAY_PROVIDER_FAILED)
        self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
