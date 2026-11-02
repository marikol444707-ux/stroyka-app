"""String fixtures only. No Caddy, HTTP, endpoints or containers are invoked."""
import unittest
from scripts.qa_routing import adapt_dual_gateway, CANDIDATE, MAIN

GATEWAY = '''http://qa.example {
    header {
        X-Private "synthetic-private-value"
        X-Request "{http.request.id}"
    }
    # Preserve the canary, including its URI transform.
    handle /api/users/qa-readonly-context/identity {
        uri strip_prefix /api
        reverse_proxy stroyka-qa-backend-candidate:8001
    }
    handle_path /api/* {
        reverse_proxy stroyka-qa-backend:8001 # general API only
    }
    handle {
        reverse_proxy stroyka-qa-static:3000
    }
}
'''
STATIC = ':3000 {\n    root * /srv/app/build\n    file_server\n}\n'


class RoutingTests(unittest.TestCase):
    def test_only_general_upstream_changes(self):
        actual = adapt_dual_gateway(GATEWAY,'8001')
        self.assertEqual(actual,GATEWAY.replace(MAIN,CANDIDATE))
        old=GATEWAY.splitlines(keepends=True); new=actual.splitlines(keepends=True)
        changed=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
        self.assertEqual(len(changed),1)
        self.assertIn('# general API only',new[changed[0]])
        canary=GATEWAY[GATEWAY.index('    handle /api/users'):GATEWAY.index('    handle_path')]
        self.assertIn(canary,actual)
        self.assertIn('X-Private "synthetic-private-value"',actual)
        self.assertIn('X-Request "{http.request.id}"',actual)
    def test_crlf_and_comments_preserved(self):
        text=GATEWAY.replace('\n','\r\n')
        self.assertEqual(adapt_dual_gateway(text,'8001'),text.replace(MAIN,CANDIDATE))
    def test_ambiguous_or_changed_semantics_rejected(self):
        variants=[
            GATEWAY.replace('handle_path /api/*','handle /api/*'),
            GATEWAY.replace('uri strip_prefix /api','uri replace /api /other'),
            GATEWAY.replace('/api/users/qa-readonly-context/identity','/api/other'),
            GATEWAY.replace(MAIN,MAIN+' '+CANDIDATE),
            GATEWAY.replace(MAIN,'{$UPSTREAM}'),
            GATEWAY.replace('handle_path /api/*','handle @api'),
            GATEWAY.replace('    handle_path', '    import other.conf\n    handle_path'),
            GATEWAY.replace('    handle_path', '    reverse_proxy '+MAIN+'\n    handle_path'),
            GATEWAY.replace('    handle_path', '    route {\n        reverse_proxy '+MAIN+'\n    }\n    handle_path'),
            GATEWAY.replace('    handle_path /api/* {','    handle_path /api/* {\n        rewrite * /other'),
            GATEWAY.replace('    handle {','    handle_path /api/* {\n        reverse_proxy '+MAIN+'\n    }\n    handle {'),
            GATEWAY.replace('reverse_proxy stroyka-qa-static:3000','reverse_proxy other:3000'),
            ':80 {\n reverse_proxy '+MAIN+'\n}\n',
        ]
        for text in variants:
            with self.subTest(variant=variants.index(text)), self.assertRaises(ValueError):
                adapt_dual_gateway(text,'8001')
    def test_port_drift_rejected(self):
        with self.assertRaises(ValueError): adapt_dual_gateway(GATEWAY,'8000')
    def test_no_error_discloses_config(self):
        with self.assertRaises(ValueError) as error:
            adapt_dual_gateway(GATEWAY.replace(MAIN,'synthetic-secret.example:443'),'8001')
        self.assertNotIn('synthetic-secret',str(error.exception))

    def test_static_import_or_second_root_rejected(self):
        from scripts.qa_routing import validate_static
        for text in (STATIC.replace('    file_server','    import other\n    file_server'),
                     STATIC.replace('    file_server','    root * /srv/app\n    file_server')):
            with self.assertRaises(ValueError): validate_static(text)
