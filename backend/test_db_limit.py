import unittest

from backend.db import limit_offset_sql


class LimitOffsetSqlTests(unittest.TestCase):
    def test_default_none_uses_bounded_page_size(self):
        sql, params = limit_offset_sql(None, 0)
        self.assertTrue(sql.strip().upper().startswith("LIMIT"))
        self.assertEqual([200, 0], params)


if __name__ == "__main__":
    unittest.main()
