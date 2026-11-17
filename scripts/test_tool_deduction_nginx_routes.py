import unittest
from scripts.ensure_tool_deduction_nginx_routes import ensure_routes,BLOCK

class ToolDeductionProxyTests(unittest.TestCase):
    config='server {\n    location = /site/pricing { proxy_pass http://127.0.0.1:8001; }\n    location / { try_files $uri /index.html; }\n}\n'
    def test_missing_api_routes_are_inserted_before_frontend_fallback_without_changing_existing_config(self):
        updated=ensure_routes(self.config)
        self.assertEqual(updated.replace(BLOCK,''),self.config)
        self.assertLess(updated.index('location = /tool-deductions'),updated.index('location / {'))
        self.assertIn('location ^~ /tool-deductions/ {',updated)
        self.assertIn('location = /salary-tool-deductions {',updated)
        self.assertEqual(BLOCK.count('proxy_pass http://127.0.0.1:8001;'),3)
        self.assertNotIn('try_files',BLOCK)
    def test_idempotent(self):
        updated=ensure_routes(self.config);self.assertEqual(ensure_routes(updated),updated)
    def test_conflicting_unknown_or_drifted_config_is_not_replaced(self):
        for config in [self.config.replace('/site/pricing','/other'),self.config+'\nlocation /tool-deductions { }',
                       ensure_routes(self.config).replace('proxy_set_header Host $host;',''),
                       ensure_routes(self.config)+BLOCK]:
            with self.subTest(config=config),self.assertRaises(ValueError):ensure_routes(config)
