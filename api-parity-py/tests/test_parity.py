"""Tests for the @parity / @parity_impl / @parity_ref decorators."""

import pytest

from api_parity_py import Status, parity, parity_impl
from api_parity_py.parity import (
    collect_port_entries,
    collect_reference_entries,
    reset_registries,
)


@pytest.fixture(autouse=True)
def _isolate_registries():
    """Each test starts with empty registries and restores nothing — tests
    should not depend on residual state from earlier tests."""
    reset_registries()
    yield
    reset_registries()


def _import_fixture():
    """Re-import portpkg so its module-level decorators run again into the
    freshly-reset registries."""
    import sys

    for name in list(sys.modules):
        if name == "portpkg" or name.startswith("portpkg."):
            del sys.modules[name]
    import portpkg  # noqa: F401


def test_class_level_entry_and_relative_children():
    _import_fixture()
    entries = collect_port_entries()
    by_path = {e["path"]: e for e in entries}

    # Class-level entry: implementation = qualified class name, optional
    # fields propagate from the impl-level args.
    cls = by_path["ext.widget.Widget"]
    assert cls["implementation"].endswith(".Widget")
    assert cls["status"] == "implemented"
    assert cls["since"] == "1.0"

    # Method with no comment: comment is None, not inherited from parent.
    foo = by_path["ext.widget.Widget.foo"]
    assert foo["implementation"].endswith(".Widget.foo")
    assert foo["status"] == "implemented"
    assert foo["comment"] is None

    # Unimplemented requires a comment; the issue field round-trips.
    baz = by_path["ext.widget.Widget.baz"]
    assert baz["status"] == "unimplemented"
    assert baz["comment"] == "todo"
    assert baz["issue"] == 42


def test_parity_impl_without_args_keeps_absolute_children():
    """`@parity_impl` with no args registers no class entry, but a child
    with an absolute path still works and gets the qualified-class
    implementation prefix."""
    _import_fixture()
    entries = collect_port_entries()
    naked = [e for e in entries if e["path"] == "ext.naked.absolute_only"]
    assert len(naked) == 1
    assert naked[0]["implementation"].endswith(".Naked.whatever")


def test_free_function_uses_absolute_path():
    _import_fixture()
    entries = collect_port_entries()
    solo = next(e for e in entries if e["path"] == "ext.free.solo")
    assert solo["status"] == "partial"
    assert solo["comment"] == "wip"
    assert solo["implementation"].endswith(".free_fn")


def test_parity_ref_registers_reference_entry():
    _import_fixture()
    refs = collect_reference_entries()
    assert {"path": "ext.spec.Declared", "kind": "class"} in refs


def test_unimplemented_without_comment_raises():
    """The validator runs at decoration time, so the failure surfaces
    where the bad annotation lives — not at registry-dump time."""
    with pytest.raises(ValueError, match="comment"):
        @parity(path="x.y", status=Status.UNIMPLEMENTED)
        def _f():
            pass


def test_relative_path_without_parent_raises():
    """A leading-`.` path needs an enclosing `@parity_impl` with a path."""
    with pytest.raises(ValueError, match="enclosing @parity_impl"):
        @parity_impl  # no args = no parent path
        class _Nope:
            @parity(path=".child", status=Status.IMPLEMENTED)
            def child(self):
                pass


def test_invalid_status_type_raises():
    with pytest.raises(TypeError, match="Status"):
        @parity(path="x.y", status="bogus")
        def _f():
            pass


def test_collect_returns_sorted_unique():
    _import_fixture()
    entries = collect_port_entries()
    paths = [e["path"] for e in entries]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
