"""End-to-end acceptance tests for `api-parity-py`.

One test per (kind, mode) cell — each invokes the CLI via `cli.main()`
with a monkeypatched `argv`, parses stdout, and asserts the envelope
shape against the synthetic fixtures.
"""

import json
import sys

import pytest

from api_parity_py import __main__ as cli
from api_parity_py.parity import reset_registries


def _purge(*roots: str) -> None:
    """Drop cached fixture modules so re-imports re-run their decorators."""
    for name in list(sys.modules):
        if name in roots or any(name.startswith(r + ".") for r in roots):
            del sys.modules[name]


@pytest.fixture(autouse=True)
def _isolate():
    reset_registries()
    _purge("tinypkg", "portpkg")
    yield
    reset_registries()
    _purge("tinypkg", "portpkg")


def _run(*argv: str, capsys) -> dict:
    """Invoke the CLI and return the parsed-JSON stdout envelope."""
    import sys as _sys
    _sys.argv = ["api-parity-py", *argv]
    rc = cli.main()
    assert rc == 0, capsys.readouterr().err
    out = capsys.readouterr().out
    return json.loads(out)


def test_reference_walker_against_tinypkg(capsys):
    """`reference` defaults to mode=walker — walks tinypkg's public API."""
    env = _run("reference", "tinypkg", capsys=capsys)
    assert env["schema_version"] == 1
    assert env["kind"] == "reference"
    assert env["language"] == "python"
    paths = {e["path"] for e in env["entries"]}
    assert "tinypkg.core.Widget" in paths
    assert "tinypkg.core.Widget.foo" in paths
    assert "tinypkg.extras.helper" in paths


def test_port_annotation_against_portpkg(capsys):
    """`port` defaults to mode=annotation — collects @parity_impl/@parity."""
    env = _run("port", "portpkg", capsys=capsys)
    assert env["kind"] == "port"
    paths = {e["path"] for e in env["entries"]}
    assert "ext.widget.Widget" in paths
    assert "ext.widget.Widget.foo" in paths
    assert "ext.free.solo" in paths


def test_reference_annotation_against_portpkg(capsys):
    """`reference --mode=annotation` collects @parity_ref decorators."""
    env = _run("reference", "--mode=annotation", "portpkg", capsys=capsys)
    assert env["kind"] == "reference"
    paths = {e["path"] for e in env["entries"]}
    assert "ext.spec.Declared" in paths


def test_port_walker_against_tinypkg(capsys):
    """`port --mode=walker` synthesizes implemented port entries from a walk.

    Useful for py↔py comparisons where neither side is annotated."""
    env = _run("port", "--mode=walker", "tinypkg", capsys=capsys)
    assert env["kind"] == "port"
    assert env["entries"], "expected at least one synthesized port entry"
    for e in env["entries"]:
        assert e["status"] == "implemented"
        assert e["implementation"] == e["path"]
