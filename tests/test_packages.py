"""Every source package imports cleanly (structure smoke test)."""

import importlib

import pytest

PACKAGES = [
    "common",
    "common.schemas",
    "common.ids",
    "common.logging",
    "common.config",
    "data",
    "detector",
    "scenarios",
    "tools",
    "kb",
    "agents",
    "agents.prompts",
    "eval",
    "app",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name):
    assert importlib.import_module(name) is not None
