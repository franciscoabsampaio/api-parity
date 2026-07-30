"""End-to-end acceptance tests for `api-parity-py`.

One test per (kind, mode) cell — each invokes the CLI via `cli.main()`
with a monkeypatched `argv`, parses stdout, and asserts the envelope
shape against the synthetic fixtures.
"""

import json
import sys
from pathlib import Path

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


SRCTREE = Path(__file__).parent / "fixtures" / "srctree"


def _run(*argv: str, capsys) -> dict:
    """Invoke the CLI and return the parsed-JSON stdout envelope."""
    import sys as _sys
    _sys.argv = ["api-parity-py", *argv]
    rc = cli.main()
    assert rc == 0, capsys.readouterr().err
    out = capsys.readouterr().out
    return json.loads(out)


def _fail(*argv: str, capsys) -> str:
    """Invoke the CLI expecting a usage exit, and return stderr."""
    import sys as _sys
    _sys.argv = ["api-parity-py", *argv]
    assert cli.main() == cli.EXIT_USAGE
    return capsys.readouterr().err


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


def test_reference_ast_keys_entries_under_the_target(capsys):
    """`--from-source` is the whole selector for mode=ast; `target` keeps
    its usual meaning — the dotted name — and the scanned tree is keyed
    beneath it."""
    env = _run(
        "reference", "acme.vendored", f"--from-source={SRCTREE}", capsys=capsys
    )
    assert env["kind"] == "reference"
    assert env["source"] == "acme.vendored"
    paths = {e["path"] for e in env["entries"]}
    assert "acme.vendored.gadgets.Gadget" in paths
    assert "acme.vendored.sub.nested.Deep" in paths


def test_from_source_conflicts_with_a_loading_mode(capsys):
    """The two are mutually exclusive: `--mode` picks between the
    producers that import the target, and `--from-source` exists
    precisely so nothing has to be imported."""
    err = _fail(
        "reference", "acme", "--mode=walker", f"--from-source={SRCTREE}", capsys=capsys
    )
    assert "--mode walker loads the target" in err


def test_from_source_rejects_several_targets(capsys):
    """One root maps to one dotted name; several targets have no defined
    pairing with several paths."""
    err = _fail(
        "reference", "acme,other", f"--from-source={SRCTREE}", capsys=capsys
    )
    assert "takes one target" in err
