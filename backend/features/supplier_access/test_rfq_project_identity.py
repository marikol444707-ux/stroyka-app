import ast
import unittest
from pathlib import Path


MAIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "main.py"
)

ERROR_TEXT = (
    "Объект заявки КП определяется неоднозначно"
)


class RfqProjectIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MAIN_PATH.read_text(
            encoding="utf-8"
        )
        cls.lines = cls.source.splitlines(
            keepends=True
        )
        cls.tree = ast.parse(
            cls.source,
            filename=str(MAIN_PATH),
        )

    def resolver(self):
        matches = []

        for node in ast.walk(self.tree):
            if not isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue

            segment = "".join(
                self.lines[
                    node.lineno - 1:
                    node.end_lineno
                ]
            )

            if ERROR_TEXT in segment:
                matches.append((node, segment))

        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_legacy_project_name_is_trimmed_in_company_scope(self):
        node, segment = self.resolver()

        string_literals = "\n".join(
            value.value
            for value in ast.walk(node)
            if isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        )

        compact_sql = " ".join(
            string_literals.split()
        )

        self.assertIn(
            "company_id=%s",
            compact_sql,
        )
        self.assertIn(
            "BTRIM(name)=BTRIM(%s)",
            compact_sql,
        )
        self.assertIn(
            "COALESCE(archived,FALSE)=FALSE",
            compact_sql,
        )
        self.assertIn(
            "ORDER BY id",
            compact_sql,
        )

        self.assertNotIn(
            "company_id=%s AND name=%s",
            compact_sql,
        )

        # A normalized-name duplicate must still fail closed.
        self.assertIn(
            "if len(projects) != 1:",
            segment,
        )
        self.assertIn(
            ERROR_TEXT,
            segment,
        )


if __name__ == "__main__":
    unittest.main()
