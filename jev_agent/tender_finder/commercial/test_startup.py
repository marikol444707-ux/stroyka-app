"""Opt-in gateway startup and key-free policy, no installed Hermes required."""
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import startup_tool
from .runtime_config import parse_runtime
from .test_runtime_config import policies
from ..settings import parse_settings
from .. import startup_tool as legacy_startup
from ..state import StorageError


class GatewayStartupTests(unittest.TestCase):
    def registry(self):
        return SimpleNamespace(_lock=threading.RLock(),get_entry=Mock(return_value=None),register=Mock())

    def test_no_optional_policy_preserves_only_legacy_tool(self):
        registry=self.registry();missing=Mock();missing.lstat.side_effect=FileNotFoundError()
        with patch.object(startup_tool,'POLICY',missing),patch.object(startup_tool,'load_gateway_policy') as load:
            legacy_startup.StartupRegistration(registry).register()
        load.assert_not_called();registry.register.assert_called_once()
        self.assertEqual(registry.register.call_args.kwargs['name'],legacy_startup.NAME)

    def test_invalid_optional_policy_cannot_replace_or_disable_registered_v2(self):
        registry=self.registry();present=Mock()
        with patch.object(startup_tool,'POLICY',present),patch.object(startup_tool,'load_gateway_policy',side_effect=ValueError('PRIVATE')):
            legacy_startup.StartupRegistration(registry).register()
        registry.register.assert_called_once();self.assertEqual(registry.register.call_args.kwargs['name'],legacy_startup.NAME)

    def test_valid_policy_registers_separate_v3_schema_without_live_runner_search(self):
        old,value=policies();policy=parse_runtime(value,legacy=parse_settings(old));registry=self.registry()
        with patch.object(startup_tool,'POLICY',Mock()),patch.object(startup_tool,'load_gateway_policy',return_value=policy.bridge),patch.object(
                startup_tool,'bind_live_gateway') as bind:
            legacy_startup.StartupRegistration(registry).register()
        self.assertEqual([call.kwargs['name'] for call in registry.register.call_args_list],
                         [legacy_startup.NAME,startup_tool.NAME])
        self.assertIs(registry.register.call_args.kwargs['handler'],startup_tool.handle)
        self.assertFalse(registry.register.call_args.kwargs['override']);bind.assert_not_called()

    def test_existing_commercial_registration_is_never_overwritten(self):
        registry=self.registry();registry.get_entry.return_value=object()
        with patch.object(startup_tool,'POLICY',Mock()),patch.object(startup_tool,'load_gateway_policy',return_value=object()):
            self.assertFalse(startup_tool.register_if_configured(registry))
        registry.register.assert_not_called()

    def test_wrong_gateway_identity_fails_before_resolving_runner_or_connecting(self):
        old,value=policies();policy=parse_runtime(value,legacy=parse_settings(old))
        with patch.object(startup_tool,'load_gateway_policy',return_value=policy.bridge),patch('os.geteuid',return_value=9999),patch.object(
                startup_tool,'bind_live_gateway') as bind:
            result=startup_tool.handle({'request_json':'{}'})
        self.assertFalse(result['queued']);bind.assert_not_called()

    def test_real_gateway_policy_file_has_no_profile_key_or_recipient_override(self):
        old,value=policies();gateway={key:value[key] for key in ('format','protocol','bridge')}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/'bridge.json';legacy.write_text(json.dumps(old));legacy.chmod(0o600)
            path=root/'commercial.json';path.write_text(json.dumps(gateway));path.chmod(0o600)
            args={'legacy_policy':legacy,'trusted_root':root,'expected_uid':os.geteuid()}
            self.assertEqual(startup_tool.load_gateway_policy(path,**args).queue.pipeline.protocol,3)
            for key in ('key','profile','reply_chat_id','command'):
                path.write_text(json.dumps({**gateway,key:'fake'}));path.chmod(0o600)
                with self.assertRaises(ValueError):startup_tool.load_gateway_policy(path,**args)
            path.write_text(json.dumps(gateway));path.chmod(0o666)
            with self.assertRaises(StorageError):startup_tool.load_gateway_policy(path,**args)

