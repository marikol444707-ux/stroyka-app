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

# Matches observed line numbers; the header value is synthetic, never a server secret.
KNOWN_LINE_GLOBAL_GATEWAY = '''{
    auto_https off
}
:80 {
    header X-Private "synthetic {opaque} value"
    encode gzip

    handle /api/users/qa-readonly-context/identity {
        uri strip_prefix /api
        reverse_proxy stroyka-qa-backend-candidate:8001
    }

    handle_path /api/* {
        reverse_proxy stroyka-qa-backend:8001
    }

    handle {
        reverse_proxy stroyka-qa-static:3000
    }
}
'''


class LeadingGlobalRoutingTests(unittest.TestCase):
    def test_observed_lines_and_single_upstream_change(self):
        lines=KNOWN_LINE_GLOBAL_GATEWAY.splitlines()
        for index,expected in {
            8:'handle /api/users/qa-readonly-context/identity {',
            9:'uri strip_prefix /api', 10:'reverse_proxy '+CANDIDATE,
            13:'handle_path /api/* {', 14:'reverse_proxy '+MAIN,
            17:'handle {',18:'reverse_proxy stroyka-qa-static:3000'
        }.items():
            self.assertEqual(lines[index-1].strip(),expected)
        actual=adapt_dual_gateway(KNOWN_LINE_GLOBAL_GATEWAY,'8001')
        self.assertEqual(actual,KNOWN_LINE_GLOBAL_GATEWAY.replace(MAIN,CANDIDATE))
        changed=[i+1 for i,(a,b) in enumerate(zip(lines,actual.splitlines())) if a!=b]
        self.assertEqual(changed,[14])
        self.assertEqual(actual.splitlines()[:13],lines[:13])
        self.assertEqual(actual.splitlines()[14:],lines[14:])

    def test_multiple_global_options_preserved_without_interpreting_values(self):
        text=KNOWN_LINE_GLOBAL_GATEWAY.replace('    auto_https off',
             '    auto_https off\n    admin off\n    email "synthetic-private@example.invalid"\n    persist_config off')
        self.assertEqual(adapt_dual_gateway(text,'8001'),text.replace(MAIN,CANDIDATE))

    def test_quoted_braces_hash_and_escaped_quote_are_not_structure(self):
        for value in ('"{"','"}"','"a # b"','"escaped \\\" quote"'):
            text=KNOWN_LINE_GLOBAL_GATEWAY.replace('"synthetic {opaque} value"',value)
            self.assertEqual(adapt_dual_gateway(text,'8001'),text.replace(MAIN,CANDIDATE))

    def test_global_crlf_is_preserved(self):
        text=KNOWN_LINE_GLOBAL_GATEWAY.replace('\n','\r\n')
        self.assertEqual(adapt_dual_gateway(text,'8001').encode(),text.replace(MAIN,CANDIDATE).encode())

    def test_static_with_and_without_global(self):
        from scripts.qa_routing import validate_static
        validate_static(STATIC)
        validate_static('{\n    auto_https off\n}\n'+STATIC)

    def test_multiple_misplaced_nested_or_routing_global_options_rejected(self):
        variants=[
            '{\n    auto_https off\n}\n'+KNOWN_LINE_GLOBAL_GATEWAY,
            GATEWAY+'{\n    auto_https off\n}\n',
            KNOWN_LINE_GLOBAL_GATEWAY.replace('    auto_https off','    import other.conf'),
            KNOWN_LINE_GLOBAL_GATEWAY.replace('    auto_https off','    order handle last'),
            KNOWN_LINE_GLOBAL_GATEWAY.replace('    auto_https off','    storage file_system {\n        root /synthetic\n    }'),
            KNOWN_LINE_GLOBAL_GATEWAY.replace('    auto_https off','    unknown_module synthetic-value'),
            KNOWN_LINE_GLOBAL_GATEWAY.replace('    auto_https off','    auto_https off\n    {\n    }'),
        ]
        for text in variants:
            with self.subTest(variant=variants.index(text)), self.assertRaises(ValueError) as error:
                adapt_dual_gateway(text,'8001')
            self.assertNotIn('synthetic-value',str(error.exception))

    def test_extra_site_and_hidden_proxy_still_rejected(self):
        for text in (KNOWN_LINE_GLOBAL_GATEWAY+':90 {\n file_server\n}\n',
                     KNOWN_LINE_GLOBAL_GATEWAY.replace('    encode gzip','    reverse_proxy '+MAIN)):
            with self.assertRaises(ValueError): adapt_dual_gateway(text,'8001')

    def test_unsupported_quoting_has_non_sensitive_error(self):
        text=KNOWN_LINE_GLOBAL_GATEWAY.replace('"synthetic {opaque} value"','"unclosed-sensitive')
        with self.assertRaises(ValueError) as error: adapt_dual_gateway(text,'8001')
        self.assertNotIn('unclosed-sensitive',str(error.exception))
