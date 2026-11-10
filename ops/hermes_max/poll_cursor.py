"""Persist MAX's acknowledged polling marker across a graceful gateway move."""

import json
import os
from pathlib import Path
import tempfile


class PollCursor:
    def __init__(self, path, bot_id):
        self.path = Path(path)
        self.bot_id = str(bot_id)
        if not self.bot_id:
            raise ValueError("MAX bot identity is required")

    @staticmethod
    def validate(marker):
        if type(marker) is not int or marker < 0:
            raise ValueError("Invalid MAX polling marker")
        return marker

    def load(self):
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return 0
        if data.get("version") != 1 or data.get("bot_id") != self.bot_id:
            raise ValueError("MAX polling cursor belongs to another bot or version")
        return self.validate(data.get("marker"))

    def save(self, marker):
        self.validate(marker)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(prefix=".max-cursor-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"version": 1, "bot_id": self.bot_id, "marker": marker}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
