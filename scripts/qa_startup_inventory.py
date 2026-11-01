"""Conservative source-only local import/call inventory. No module execution."""
import ast
from pathlib import Path


class StartupCalls(ast.NodeVisitor):
    def __init__(self):
        self.calls = []

    def visit_Call(self, node):
        self.calls.append({'line': node.lineno, 'call': ast.unparse(node.func)})
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for item in node.decorator_list + node.args.defaults + [x for x in node.args.kw_defaults if x]:
            self.visit(item)
        # Function bodies are not executed merely by defining the function.

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        for item in node.args.defaults:
            self.visit(item)


def inventory(root):
    root = Path(root).resolve()
    pending = [root / 'backend/main.py']
    seen, files, external = set(), [], set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text())
        calls = StartupCalls()
        calls.visit(tree)
        dependencies, dynamic = set(), []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in ('__import__', 'importlib.import_module', 'exec', 'eval'):
                dynamic.append(node.lineno)
            modules = []
            if isinstance(node, ast.Import):
                modules = [x.name for x in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = path.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    prefix = '.'.join(base.relative_to(root).parts)
                    module = '.'.join(x for x in (prefix, node.module) if x)
                else:
                    module = node.module or ''
                modules = [module] + [module + '.' + x.name for x in node.names if x.name != '*']
            for module in modules:
                found = None
                for base in (root, root / 'backend'):
                    stem = base.joinpath(*module.split('.'))
                    for candidate in (stem.with_suffix('.py'), stem / '__init__.py'):
                        if candidate.is_file() and candidate.resolve().is_relative_to(root):
                            found = candidate.resolve()
                            break
                    if found:
                        break
                if found:
                    dependencies.add(str(found.relative_to(root)))
                    pending.append(found)
                    # Importing a submodule also imports package initializers.
                    parent = found.parent
                    while parent != root and parent.is_relative_to(root):
                        init = parent / '__init__.py'
                        if init.is_file():
                            pending.append(init)
                        parent = parent.parent
                else:
                    external.add(module)
        files.append({'file': str(path.relative_to(root)), 'calls': calls.calls,
                      'local_dependencies': sorted(dependencies), 'dynamic_call_lines': dynamic})
    return {'files': sorted(files, key=lambda x: x['file']),
            'unresolved_or_external_imports': sorted(external),
            'execution_allowed': False,
            'limits': ['Conservative: includes imports inside functions and inactive branches.',
                       'Call targets are candidates, not proof of side effects.',
                       'External libraries and dynamically computed imports remain opaque.',
                       'Function bodies invoked by registration may have further effects.']}
