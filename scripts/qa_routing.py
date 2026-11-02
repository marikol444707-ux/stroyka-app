"""Bounded Caddy structure reader for the confirmed QA dual-route fixture.
Not a general Caddy parser. Unknown routing syntax fails without exposing content.
"""
import re
import shlex

IDENTITY = '/api/users/qa-readonly-context/identity'
MAIN = 'stroyka-qa-backend:8001'
CANDIDATE = 'stroyka-qa-backend-candidate:8001'
STATIC = 'stroyka-qa-static:3000'


def require(ok, message='Unsupported or ambiguous QA routing structure'):
    if not ok:
        raise ValueError(message)


def parse(text):
    lines = text.splitlines(keepends=True)
    root = []
    stack = [root]
    for number, line in enumerate(lines):
        try:
            words = shlex.split(line, comments=True, posix=True)
        except ValueError:
            raise ValueError('Unsupported QA routing syntax') from None
        if not words:
            continue
        if words == ['}']:
            require(len(stack) > 1)
            stack.pop()
            continue
        opening = words[-1] == '{'
        if opening:
            words = words[:-1]
        require(words and '{' not in words and '}' not in words)
        require(words[0] != 'import' and not words[0].startswith(('(', '@')),
                'QA imports, snippets or named matchers require explicit review')
        node = {'words': words, 'children': [] if opening else None, 'line': number}
        stack[-1].append(node)
        if opening:
            stack.append(node['children'])
    require(len(stack) == 1)
    return lines, root


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node['children'] or [])


def adapt_dual_gateway(text, candidate_port):
    """Change ONE reviewed general API upstream; preserve all other bytes."""
    require(str(candidate_port) == '8001', 'Candidate port differs from confirmed canary route')
    lines, root = parse(text)
    require(len(root) == 1 and root[0]['children'] is not None)
    site = root[0]['children']
    handlers = [n for n in site if n['words'][0] in ('handle', 'handle_path')]
    require(len(handlers) == 3)
    canary = [n for n in handlers if n['words'] == ['handle', IDENTITY]]
    general = [n for n in handlers if n['words'] == ['handle_path', '/api/*']]
    fallback = [n for n in handlers if n['words'] == ['handle']]
    require(len(canary) == len(general) == len(fallback) == 1)
    # Require the exact known path transformation and targets, no extra directives.
    def body(node):
        require(node['children'] is not None)
        require(all(n['children'] is None for n in node['children']))
        return [n['words'] for n in node['children']]
    require(body(canary[0]) == [['uri', 'strip_prefix', '/api'], ['reverse_proxy', CANDIDATE]])
    require(body(general[0]) == [['reverse_proxy', MAIN]])
    require(body(fallback[0]) == [['reverse_proxy', STATIC]])
    # Reject additional routing elsewhere, including nested route/rewrite/proxies.
    allowed = {id(n) for h in handlers for n in (h, *(h['children'] or []))}
    routing = {'handle', 'handle_path', 'route', 'reverse_proxy', 'uri', 'rewrite',
               'redir', 'try_files', 'respond', 'invoke', 'php_fastcgi'}
    for n in walk(root):
        if n['words'][0] in routing:
            require(id(n) in allowed)
    target_line = general[0]['children'][0]['line']
    pattern = r'^(\s*reverse_proxy[ \t]+)' + re.escape(MAIN) + r'([ \t]*(?:#[^\r\n]*)?(?:\r?\n)?)$'
    match = re.fullmatch(pattern, lines[target_line])
    require(match is not None, 'General QA upstream must be an explicit literal')
    lines[target_line] = match[1] + CANDIDATE + match[2]
    return ''.join(lines)


def validate_static(text):
    _, root = parse(text)
    roots = [n for n in walk(root) if n['words'][0] == 'root']
    require(len(roots) == 1 and roots[0]['children'] is None
            and roots[0]['words'] in (['root', '*', '/srv/app'], ['root', '*', '/srv/app/build']),
            'Static QA root differs from reviewed plan')
    require(not any(n['words'][0] in ('reverse_proxy', 'handle', 'handle_path', 'route',
                                      'rewrite', 'uri', 'redir', 'invoke', 'php_fastcgi')
                    for n in walk(root)), 'Unexpected static QA routing')
