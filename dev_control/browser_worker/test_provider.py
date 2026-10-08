import os
import types
import unittest
from unittest.mock import patch

from dev_control.browser_worker.provider import (
    UPSTREAM_TYPESAFE_URL,
    _sanitize_questions_for_provider,
    _sanitize_state_for_provider,
    install_timeweb_provider,
)
from dev_control.jev_timeweb import JevError


class ProviderPatchTest(unittest.TestCase):


    def test_provider_payload_redacts_element_and_question_values(self):
        state = {
            "page": {"url": "https://qa.example.test/form"},
            "elements": [{"index": "1", "value": "invite-secret", "label": "Invite code"}],
        }
        questions = {
            "target": {
                "type": "choice",
                "current_value": "reset-secret",
                "criteria": {"1": {"current_value": "nested-secret"}},
            }
        }
        safe_state = _sanitize_state_for_provider(state)
        safe_questions = _sanitize_questions_for_provider(questions)
        rendered = repr((safe_state, safe_questions))
        self.assertNotIn("invite-secret", rendered)
        self.assertNotIn("reset-secret", rendered)
        self.assertNotIn("nested-secret", rendered)
        self.assertIn("[POPULATED]", rendered)

    def test_provider_state_redacts_typed_values_and_url_credentials(self):
        state = {
            "page": {"url": "https://qa.example.test/?invite=secret-code"},
            "recent_actions": [
                {
                    "operation": "TYPE_TEXT",
                    "text": "my-password",
                    "value": "another-secret",
                    "url": "https://qa.example.test/reset/path-token?code=query-token",
                }
            ],
        }
        safe = _sanitize_state_for_provider(state)
        rendered = repr(safe)
        self.assertNotIn("secret-code", rendered)
        self.assertNotIn("my-password", rendered)
        self.assertNotIn("another-secret", rendered)
        self.assertNotIn("path-token", rendered)
        self.assertNotIn("query-token", rendered)
        self.assertIn("[REDACTED]", rendered)
        self.assertEqual(state["recent_actions"][0]["text"], "my-password")

    def test_requires_timeweb_key(self):
        fake = types.SimpleNamespace(post_json=lambda *_: {})
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(JevError, "TIMEWEB_AI_API_KEY"):
                install_timeweb_provider(model_module=fake)

    def test_redirects_only_systemone_and_uses_nonsecret_sentinel(self):
        passthrough = []
        fake = types.SimpleNamespace(
            post_json=lambda url, key, body: passthrough.append((url, key, body)) or {"passthrough": True}
        )
        env = {
            "TIMEWEB_AI_API_KEY": "real-secret",
            "JEV_MODEL": "jev-latest",
        }
        with patch("dev_control.browser_worker.provider.JevTimewebClient.ask") as ask:
            ask.return_value = {"answers": {}, "model": "jev-latest"}
            patch_handle = install_timeweb_provider(model_module=fake, environ=env)
            result = fake.post_json(
                UPSTREAM_TYPESAFE_URL,
                env["TYPESAFE_API_KEY"],
                {"state": {"page": {}}, "questions": {"operation": {}}},
            )

        self.assertEqual(result["model"], "jev-latest")
        ask.assert_called_once()
        self.assertEqual(env["TYPESAFE_API_KEY"], "timeweb-adapter-no-secret")
        self.assertNotIn("real-secret", env["TYPESAFE_API_KEY"])
        self.assertEqual(passthrough, [])
        patch_handle.restore()

    def test_other_provider_calls_pass_through(self):
        calls = []
        fake = types.SimpleNamespace(
            post_json=lambda url, key, body: calls.append((url, key, body)) or {"ok": True}
        )
        env = {"TIMEWEB_AI_API_KEY": "secret"}
        patch_handle = install_timeweb_provider(model_module=fake, environ=env)
        result = fake.post_json("https://api.timeweb.ai/v1/chat/completions", "text-key", {"x": 1})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0][0], "https://api.timeweb.ai/v1/chat/completions")
        patch_handle.restore()



    def test_rejects_inherited_text_provider_without_explicit_timeweb_model(self):
        fake = types.SimpleNamespace(post_json=lambda *_: {})
        env = {
            "TIMEWEB_AI_API_KEY": "secret",
            "TEXT_MODEL_API_KEY": "stale-secret",
            "TEXT_MODEL_BASE_URL": "https://external.example/v1",
            "TEXT_MODEL": "stale-model",
        }
        with self.assertRaisesRegex(JevError, "inherited TEXT_MODEL"):
            install_timeweb_provider(model_module=fake, environ=env)

    def test_rejects_partial_or_foreign_text_model_configuration(self):
        fake = types.SimpleNamespace(post_json=lambda *_: {})
        partial = {
            "TIMEWEB_AI_API_KEY": "secret",
            "TIMEWEB_TEXT_MODEL": "timeweb-text",
            "TEXT_MODEL_BASE_URL": "https://external.example/v1",
        }
        with self.assertRaisesRegex(JevError, "partial TEXT_MODEL"):
            install_timeweb_provider(model_module=fake, environ=partial)

        foreign = {
            "TIMEWEB_AI_API_KEY": "secret",
            "TIMEWEB_TEXT_MODEL": "timeweb-text",
            "TEXT_MODEL_API_KEY": "other-secret",
            "TEXT_MODEL_BASE_URL": "https://external.example/v1",
            "TEXT_MODEL": "other-model",
        }
        with self.assertRaisesRegex(JevError, "cannot be mixed"):
            install_timeweb_provider(model_module=fake, environ=foreign)

    def test_text_helper_is_configured_only_when_explicit_model_is_set(self):
        fake = types.SimpleNamespace(post_json=lambda *_: {})
        env = {
            "TIMEWEB_AI_API_KEY": "secret",
            "TIMEWEB_TEXT_MODEL": "some-explicit-model",
        }
        patch_handle = install_timeweb_provider(model_module=fake, environ=env)
        self.assertEqual(env["TEXT_MODEL_API_KEY"], "secret")
        self.assertEqual(env["TEXT_MODEL_BASE_URL"], "https://api.timeweb.ai/v1")
        self.assertEqual(env["TEXT_MODEL"], "some-explicit-model")
        patch_handle.restore()


    def test_visible_nonsecret_select_keeps_current_value(self):
        state = {"elements": [
            {"index": "1", "role": "combobox", "label": "Куда", "value": "JEV QA Объект A"},
            {"index": "2", "role": "textbox", "label": "Примечание", "value": "private note"},
            {"index": "3", "role": "combobox", "label": "Session token", "value": "secret-token"},
        ]}
        questions = {"select_target": {
            "criteria": {
                "1:1": {"role": "combobox", "label": "Куда", "current_value": "JEV QA Объект A"},
                "2:1": {"role": "combobox", "label": "Session token", "current_value": "secret-token"},
            }
        }}
        safe_state = _sanitize_state_for_provider(state)
        safe_questions = _sanitize_questions_for_provider(questions)
        self.assertEqual(safe_state["elements"][0]["value"], "JEV QA Объект A")
        self.assertEqual(safe_state["elements"][1]["value"], "[POPULATED]")
        self.assertEqual(safe_state["elements"][2]["value"], "[POPULATED]")
        self.assertEqual(safe_questions["select_target"]["criteria"]["1:1"]["current_value"], "JEV QA Объект A")
        self.assertEqual(safe_questions["select_target"]["criteria"]["2:1"]["current_value"], "[POPULATED]")
        self.assertEqual(state["elements"][1]["value"], "private note")

    def test_form_policy_reaches_timeweb_without_overriding_choice_schema(self):
        fake = types.SimpleNamespace(post_json=lambda *_: {})
        env = {"TIMEWEB_AI_API_KEY": "secret"}
        questions = {
            "operation": {
                "type": "choice",
                "criteria": {"CLICK": "Click", "BLOCKED": "Blocked"},
                "instructions": {"goal": "Choose item", "rules": "Existing rule"},
            },
            "click_target": {
                "type": "choice",
                "criteria": {"1": {"role": "checkbox", "label": "Test item"}},
                "instructions": {"rules": ["Existing target rule"]},
            },
        }
        with patch("dev_control.browser_worker.provider.JevTimewebClient.ask") as ask:
            ask.return_value = {"answers": {}, "model": "jev-latest"}
            handle = install_timeweb_provider(model_module=fake, environ=env)
            fake.post_json(UPSTREAM_TYPESAFE_URL, env["TYPESAFE_API_KEY"], {
                "state": {"page": {"url": "https://qa.example.test/app"}},
                "questions": questions,
            })
            handle.restore()
        sent = ask.call_args.kwargs["questions"]
        self.assertEqual(sent["operation"]["criteria"], questions["operation"]["criteria"])
        self.assertIn("optional notes", sent["operation"]["instructions"]["rules"])
        self.assertIn("Existing target rule", sent["click_target"]["instructions"]["rules"])
        self.assertTrue(any("checkbox" in rule for rule in sent["click_target"]["instructions"]["rules"]))
        self.assertEqual(questions["operation"]["instructions"]["rules"], "Existing rule")



    def test_confirmed_fill_marker_without_leaking_typed_text(self):
        state = {
            "elements": [
                {"index": "1", "role": "spinbutton", "label": "Кол-во", "value": "15"},
                {"index": "2", "role": "textbox", "label": "Примечание", "value": "private note"},
                {"index": "3", "role": "textbox", "label": "Token", "value": "secret-token"},
            ],
            "recent_actions": [
                {"kind": "fill", "action": "Кол-во", "text": "15"},
                {"kind": "fill", "action": "Token", "text": "secret-token"},
            ],
        }
        safe = _sanitize_state_for_provider(state)
        self.assertEqual(safe["elements"][0]["value"], "[LAST_ENTRY_CONFIRMED]")
        self.assertEqual(safe["elements"][1]["value"], "[POPULATED]")
        self.assertEqual(safe["elements"][2]["value"], "[LAST_ENTRY_CONFIRMED]")
        self.assertEqual(safe["recent_actions"][0]["text"], "[REDACTED]")
        self.assertNotIn("secret-token", repr(safe))
        self.assertNotIn("private note", repr(safe))
        self.assertEqual(state["elements"][0]["value"], "15")

    def test_changed_input_is_not_marked_confirmed(self):
        state = {
            "elements": [{"index": "1", "role": "spinbutton", "label": "Quantity", "value": "10"}],
            "recent_actions": [{"kind": "fill", "action": "Quantity", "text": "15"}],
        }
        safe = _sanitize_state_for_provider(state)
        self.assertEqual(safe["elements"][0]["value"], "[POPULATED]")



if __name__ == "__main__":
    unittest.main()
