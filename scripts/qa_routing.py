"""Bounded Caddy structure reader for the confirmed QA dual-route fixture.
Not a general Caddy parser. Unknown routing syntax fails without exposing content.
"""
import re
import json

IDENTITY = '/api/users/qa-readonly-context/identity'
MAIN = 'stroyka-qa-backend:8001'
CANDIDATE = 'stroyka-qa-backend-candidate:8001'
STATIC = 'stroyka-qa-static:3000'


def require(ok, message='Unsupported or ambiguous QA routing structure'):
    if not ok:
        raise ValueError(message)


def tokens_for_line(line):
    """Small literal-token lexer; quoted braces are values, never structure.

    No expansion, imports, heredocs or multiline strings. Original text is kept
    separately and never reconstructed from tokens.
    """
    tokens = []
    index = 0
    while index < len(line):
        if line[index].isspace():
            index += 1
            continue
        if line[index] == '#':
            break
        quoted = line[index] == '"'
        if quoted:
            try:
                value, size = json.JSONDecoder().raw_decode(line[index:])
            except ValueError:
                raise ValueError('Unsupported QA quoted token or multiline string') from None
            require(isinstance(value, str), 'Unsupported QA quoted token')
            index += size
            require(index == len(line) or line[index].isspace() or line[index] == '#',
                    'Concatenated QA tokens require explicit review')
        else:
            end = index
            while end < len(line) and not line[end].isspace():
                end += 1
            value = line[index:end]
            require('"' not in value and '`' not in value and not value.startswith('<<'),
                    'Unsupported QA token quoting or heredoc')
            index = end
        tokens.append((value, not quoted and value in ('{', '}')))
    return tokens


GLOBAL_OPTIONS = frozenset(('auto_https', 'admin', 'debug', 'http_port', 'https_port',
                            'email', 'default_bind', 'persist_config', 'local_certs',
                            'skip_install_trust', 'grace_period', 'shutdown_delay'))


def site_nodes(root):
    sites = [node for node in root if not node.get('global_options')]
    require(len(sites) == 1 and sites[0]['children'] is not None,
            'Expected exactly one QA site after optional leading global options')
    return sites


def parse(text):
    lines = text.splitlines(keepends=True)
    root = []
    stack = [root]
    for number, line in enumerate(lines):
        tokens = tokens_for_line(line)
        if not tokens:
            continue
        if tokens == [('}', True)]:
            require(len(stack) > 1, 'Unmatched QA closing brace')
            stack.pop()
            continue
        if tokens == [('{', True)]:
            require(len(stack) == 1 and not root,
                    'Global QA options must be the single leading block')
            node = {'words': [], 'children': [], 'line': number, 'global_options': True}
            root.append(node)
            stack.append(node['children'])
            continue
        opening = tokens[-1] == ('{', True)
        if opening:
            tokens = tokens[:-1]
        require(tokens and not any(structural for _, structural in tokens),
                'Inline or misplaced QA braces require explicit review')
        words = [value for value, _ in tokens]
        require(words[0] != 'import' and not words[0].startswith(('(', '@')),
                'QA imports, snippets or named matchers require explicit review')
        node = {'words': words, 'children': [] if opening else None, 'line': number}
        stack[-1].append(node)
        if opening:
            require(len(stack) < 16, 'QA nesting limit exceeded')
            stack.append(node['children'])
    require(len(stack) == 1, 'Unclosed QA block')
    for node in root:
        if node.get('global_options'):
            for option in node['children']:
                require(option['children'] is None,
                        'Nested QA global option blocks require explicit review')
                require(option['words'][0] in GLOBAL_OPTIONS,
                        'Unsupported QA global option; routing order/modules require explicit review')
    site_nodes(root)
    return lines, root


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node['children'] or [])


def adapt_dual_gateway(text, candidate_port):
    """Change ONE reviewed general API upstream; preserve all other bytes."""
    require(str(candidate_port) == '8001', 'Candidate port differs from confirmed canary route')
    lines, root = parse(text)
    sites = site_nodes(root)
    site = sites[0]['children']
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
    for n in walk(sites):
        if n['words'][0] in routing:
            require(id(n) in allowed)
    target_line = general[0]['children'][0]['line']
    pattern = r'^(\s*reverse_proxy[ \t]+)' + re.escape(MAIN) + r'([ \t]*(?:#[^\r\n]*)?(?:\r?\n)?)$'
    match = re.fullmatch(pattern, lines[target_line])
    require(match is not None, 'General QA upstream must be an explicit literal')
    lines[target_line] = match[1] + CANDIDATE + match[2]
    return ''.join(lines)


def validate_static(text):
    _, parsed = parse(text)
    root = site_nodes(parsed)
    roots = [n for n in walk(root) if n['words'][0] == 'root']
    require(len(roots) == 1 and roots[0]['children'] is None
            and roots[0]['words'] in (['root', '*', '/srv/app'], ['root', '*', '/srv/app/build']),
            'Static QA root differs from reviewed plan')
    require(not any(n['words'][0] in ('reverse_proxy', 'handle', 'handle_path', 'route',
                                      'rewrite', 'uri', 'redir', 'invoke', 'php_fastcgi')
                    for n in walk(root)), 'Unexpected static QA routing')
