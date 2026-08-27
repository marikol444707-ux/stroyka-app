import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend" / "main.py"
ESTIMATE_CHANGES_PATH = (
    PROJECT_ROOT / "backend" / "features" / "estimate_changes" / "routes.py"
)


def _function(tree, name):
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _call_lines(function, name):
    return [
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == name)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == name)
        )
    ]


class AutomaticEstimateSnapshotWiringTests(unittest.TestCase):
    def test_primary_estimate_writers_snapshot_before_commit(self):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))

        for function_name in (
            "create_estimate",
            "update_estimate",
            "update_estimate_status",
        ):
            with self.subTest(function=function_name):
                function = _function(tree, function_name)
                snapshots = _call_lines(function, "ensure_active_estimate_snapshot")
                commits = _call_lines(function, "commit")
                self.assertEqual(len(snapshots), 1)
                self.assertTrue(commits)
                self.assertLess(snapshots[0], min(commits))

    def test_new_active_estimate_from_approved_changes_is_snapshotted_before_commit(self):
        tree = ast.parse(
            ESTIMATE_CHANGES_PATH.read_text(encoding="utf-8"),
            filename=str(ESTIMATE_CHANGES_PATH),
        )
        function = _function(tree, "include_estimate_changes")
        snapshots = _call_lines(function, "ensure_active_estimate_snapshot")
        commits = _call_lines(function, "commit")

        self.assertEqual(len(snapshots), 1)
        self.assertTrue(commits)
        self.assertLess(snapshots[0], max(commits))


if __name__ == "__main__":
    unittest.main()
