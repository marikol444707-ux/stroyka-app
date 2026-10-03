import os
import types
import unittest
from unittest.mock import patch

from dev_control.browser_worker.provider import (
    UPSTREAM_TYPESAFE_URL,
    install_timeweb_provider,
)
from dev_control.jev_timeweb import JevError


class ProviderPatchTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
