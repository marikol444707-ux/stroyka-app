"""Exercise the real patched polling loop offline, without importing bot secrets."""

import ast
import asyncio
import logging
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from ops.hermes_max.patch_adapter import patched
from ops.hermes_max.poll_cursor import PollCursor


def verify(source):
    tree = ast.parse(patched(source))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)
                  and node.name == "_poll_loop")
    namespace = {"__package__": "ops.hermes_max", "Path": Path, "os": os,
                 "asyncio": asyncio, "logger": logging.getLogger("offline-max-test"),
                 "aiohttp": SimpleNamespace(ClientTimeout=lambda **kw: kw),
                 "_json_preview": lambda value: "redacted"}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "adapter-loop", "exec"), namespace)

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def json(self):
            return {"marker": 43, "updates": [{"update_type": "test"}]}

    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, HERMES_HOME=directory):
        cursor = PollCursor(Path(directory) / "gateway/max-poll-cursor.json", "test-bot")
        cursor.save(42)
        for cancel, expected in [(True, 42), (False, 43), (False, 43)]:
            calls = []
            instance = SimpleNamespace(_running=True, _bot_user_id="test-bot", _api_base_url="offline")

            def get(url, **kwargs):
                calls.append(kwargs["params"])
                return Response()

            async def handle(update):
                # A fetched marker must not acknowledge a batch before dispatch.
                assert cursor.load() == calls[0]["marker"]
                instance._running = False
                if cancel:
                    raise asyncio.CancelledError()

            instance._session = SimpleNamespace(get=get)
            instance._handle_update = handle
            before = cursor.load()
            asyncio.run(namespace["_poll_loop"](instance))
            assert calls == [{"limit": 100, "timeout": 30, "marker": before}]
            assert cursor.load() == expected
        cursor.path.write_text("corrupt")
        instance._running = True
        calls.clear()
        try:
            asyncio.run(namespace["_poll_loop"](instance))
        except ValueError:
            pass
        else:
            raise AssertionError("Corrupt cursor must prevent unpositioned polling")
        assert not calls
    print("Real MAX polling loop: restart, dispatch ordering, cancellation, corruption OK")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).read_bytes())
