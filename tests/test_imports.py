"""The modules of awkit form layers: no two modules import each other, directly or through others.

Function-local imports count too. They stay where they keep `awkit hook` fast or let a test replace a function in
the module that defines it; they do not hide a cycle.
"""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

from support import child_env

SRC = Path(__file__).resolve().parents[1] / "src" / "awkit"


def module_name(path):
    return path.stem if path.parent == SRC else f"{path.parent.name}.{path.stem}"


def imports():
    """{module: {modules it imports anywhere in its code}} for awkit's own modules."""
    paths = list(SRC.glob("*.py")) + list((SRC / "extras").glob("*.py"))
    names = {module_name(path) for path in paths}
    graph = {}
    for path in paths:
        me, package = module_name(path), "" if path.parent == SRC else "extras."
        found = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets = []
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level == 1:
                    targets = [package + base] if base else [package + alias.name for alias in node.names]
                elif node.level == 2:
                    targets = [base] if base else [alias.name for alias in node.names]
                elif base.startswith("awkit."):
                    targets = [base[len("awkit."):]]
            elif isinstance(node, ast.Import):
                targets = [alias.name[len("awkit."):] for alias in node.names if alias.name.startswith("awkit.")]
            found.update(target for target in targets if target in names and target != me)
        graph[me] = found
    return graph


def cycles(graph):
    """Groups of modules that reach each other (Tarjan's strongly connected components of size above one)."""
    index, low, stack, on, found, counter = {}, {}, [], set(), [], [0]

    def visit(node):
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on.add(node)
        for target in sorted(graph[node]):
            if target not in index:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            group = []
            while True:
                member = stack.pop()
                on.discard(member)
                group.append(member)
                if member == node:
                    break
            if len(group) > 1:
                found.append(sorted(group))

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return found


class Layers(unittest.TestCase):
    def test_no_module_imports_back_into_a_module_that_imports_it(self):
        self.assertEqual(cycles(imports()), [])

    def test_the_cycle_check_finds_a_cycle(self):
        self.assertEqual(cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a"}}), [["a", "b", "c"]])

    def test_a_hook_call_does_not_load_the_review_session_or_extras_code(self):
        # `awkit hook` runs on every tool call of the agent; what cli imports at the top is its start-up cost.
        probe = subprocess.run([sys.executable, "-c", "import sys, awkit.cli; print(' '.join(sorted(sys.modules)))"],
                               capture_output=True, text=True, env=child_env())
        self.assertEqual(probe.returncode, 0, probe.stderr)
        loaded = probe.stdout.split()
        heavy = [name for name in loaded if name.startswith(("awkit.review", "awkit.session", "awkit.artifact",
                                                             "awkit.extras", "awkit.codex", "awkit.claude"))]
        self.assertEqual(heavy, [])


if __name__ == "__main__":
    unittest.main()
