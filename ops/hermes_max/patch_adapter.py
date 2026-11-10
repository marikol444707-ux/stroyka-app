"""Patch only the reviewed, installed custom MAX adapter; reject other versions."""

import ast
import hashlib
from pathlib import Path
import sys

SOURCE_SHA256 = "acf84ae7a83a3b0cad2ca06437f9c0b486c0ed7bd31ba53d7316c0de2306d534"


def patched(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unreviewed MAX adapter version; refusing to patch")
    text = source.decode()
    text = text.replace(
        "        marker: int = 0\n",
        "        from .poll_cursor import PollCursor\n"
        "        cursor = PollCursor(\n"
        "            Path(os.environ.get('HERMES_HOME', '/opt/data')) / 'gateway' / 'max-poll-cursor.json',\n"
        "            self._bot_user_id,\n"
        "        )\n"
        "        marker = cursor.load()\n",
        1,
    )
    text = text.replace(
        "                    if new_marker is not None:\n                        marker = new_marker\n\n",
        "                    if new_marker is not None:\n                        cursor.validate(new_marker)\n\n",
        1,
    )
    text = text.replace(
        "                        await self._handle_update(u)\n\n",
        "                        await self._handle_update(u)\n\n"
        "                    if new_marker is not None:\n"
        "                        cursor.save(new_marker)\n"
        "                        marker = new_marker\n\n",
        1,
    )
    ast.parse(text)
    return text.encode()


if __name__ == "__main__":
    source, destination = map(Path, sys.argv[1:])
    destination.write_bytes(patched(source.read_bytes()))
