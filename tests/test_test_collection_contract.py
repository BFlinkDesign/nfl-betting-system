"""Ensure test-looking modules are either collected or explicitly manual."""

from __future__ import annotations

import ast
from pathlib import Path


def _module_is_collectable(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                return True
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            return True
    return False


def _module_is_explicitly_manual(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == "MANUAL_TEST_MODULE"
            for target in targets
        ):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and value.value is True:
            return True
    return False


def test_every_test_module_is_collectable_or_explicitly_manual() -> None:
    tests_dir = Path(__file__).parent
    violations: list[str] = []

    for path in sorted(tests_dir.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not (_module_is_collectable(tree) or _module_is_explicitly_manual(tree)):
            violations.append(path.name)

    assert not violations, (
        "test-looking modules are silently uncollected; add real pytest tests "
        f"or MANUAL_TEST_MODULE = True: {violations}"
    )
