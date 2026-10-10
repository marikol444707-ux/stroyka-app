import unittest

from dev_control.browser_worker.verifier import verify_final_state


class VerifierTest(unittest.TestCase):

    def test_done_without_observable_assertion_fails(self):
        result = verify_final_state(
            {"status": "done", "page": {"url": "https://qa.test", "text": "Anything"}},
        )
        self.assertFalse(result.ok)
        self.assertIn("no_deterministic_assertions", result.failures)

    def test_done_is_not_enough_when_expected_evidence_is_missing(self):
        result = verify_final_state(
            {"status": "done", "page": {"url": "https://qa.test/x", "text": "Other"}},
            expect_text=["Success"],
        )
        self.assertFalse(result.ok)
        self.assertIn("expect_text[0]:missing", result.failures)

    def test_passes_observable_assertions(self):
        result = verify_final_state(
            {
                "status": "done",
                "page": {
                    "url": "https://qa.test/warehouse",
                    "text": "Перемещение отклонено",
                    "full_text": "Перемещение отклонено",
                },
            },
            expect_text=["Перемещение отклонено"],
            forbid_text=["М-11 открыт"],
            expect_url_contains=["warehouse"],
        )
        self.assertTrue(result.ok)
        self.assertFalse(result.failures)



    def test_read_only_observation_does_not_require_agent_done(self):
        result = verify_final_state(
            {"status": "observed", "page": {"url": "https://qa.test/warehouse", "text": "Склад", "full_text": "Склад"}},
            expect_text=["Склад"],
            expect_url_contains=["qa.test"],
            require_agent_done=False,
        )
        self.assertTrue(result.ok)
        self.assertIn("read_only_observation", result.checks)
        self.assertNotIn("agent_status=observed", result.failures)

    def test_blank_assertion_fails(self):
        result = verify_final_state(
            {"status": "done", "page": {"url": "https://qa.test", "text": "Anything", "full_text": "Anything"}},
            expect_text=["   "],
        )
        self.assertFalse(result.ok)
        self.assertIn("blank_deterministic_assertion", result.failures)

    def test_negative_assertion_requires_complete_document_text(self):
        result = verify_final_state(
            {"status": "done", "page": {"url": "https://qa.test", "text": "Visible only"}},
            forbid_text=["Forbidden"],
        )
        self.assertFalse(result.ok)
        self.assertIn("forbid_text[0]:full_text_unavailable", result.failures)

    def test_assertion_values_are_never_echoed_into_result(self):
        value = "private-assertion-value"
        result = verify_final_state(
            {"status": "done", "page": {"url": "https://qa.test/", "text": "", "full_text": ""}},
            expect_url_contains=[value],
        )
        self.assertFalse(result.ok)
        self.assertNotIn(value, repr(result))
        self.assertIn("expect_url_contains[0]:missing", result.failures)
    def test_blocked_agent_fails_even_if_text_matches(self):
        result = verify_final_state(
            {"status": "blocked", "page": {"url": "https://qa.test", "text": "Success"}},
            expect_text=["Success"],
        )
        self.assertFalse(result.ok)
        self.assertIn("agent_status=blocked", result.failures)


if __name__ == "__main__":
    unittest.main()
