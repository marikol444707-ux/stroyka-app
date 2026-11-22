import json
import subprocess
import sys
import unittest

from backend.features.route_access.inventory import (
    GATED_REGISTRATIONS,
    MAIN_PATH,
    ROOT,
    load_inventory,
)


def collect_live_routes():
    """Import the app in a child process so this suite does not load backend.main."""
    script = (
        "import json,sys\n"
        "from backend.features.route_access.inventory import collect_routes, load_app\n"
        "json.dump(collect_routes(load_app()), sys.stdout, ensure_ascii=False)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr[-4000:] or completed.stdout[-4000:])
    return json.loads(completed.stdout)


def _label(route):
    roles = []
    for dependency in route["dependencies"]:
        if dependency["roles"]:
            roles.append(dependency["callable"] + ":" + ",".join(dependency["roles"] if isinstance(dependency["roles"][0], str) else []))
        else:
            roles.append(dependency["callable"])
    return f"{','.join(route['methods']) or '-'} {route['path']} [{'; '.join(roles)}]"


class RouteAccessInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = collect_live_routes()

    def test_registered_routes_match_inventory(self):
        expected = load_inventory()["routes"]
        if self.live == expected:
            return
        live_labels = [_label(route) for route in self.live]
        expected_labels = [_label(route) for route in expected]
        missing = [label for label in expected_labels if label not in live_labels]
        added = [label for label in live_labels if label not in expected_labels]
        # Same path and method can still differ in dependency roles.
        live_by_key = {(tuple(route["methods"]), route["path"]): route for route in self.live}
        role_changes = []
        for route in expected:
            key = (tuple(route["methods"]), route["path"])
            current = live_by_key.get(key)
            if current is not None and current["dependencies"] != route["dependencies"]:
                role_changes.append(
                    key[1] + " expected " + _label(route) + " live " + _label(current)
                )
        preview = "\n".join(
            ["missing:"] + missing[:20] + ["added:"] + added[:20] + ["roles:"] + role_changes[:20]
        )
        self.fail(
            f"registered routes changed (live {len(self.live)}, inventory {len(expected)})\n{preview}"
        )

    def test_flag_gated_registrations_remain_in_main(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        for flag, call in GATED_REGISTRATIONS:
            with self.subTest(flag=flag):
                self.assertIn(flag, source)
                self.assertIn(call, source)


if __name__ == "__main__":
    unittest.main()
