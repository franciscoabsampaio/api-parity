"""Tests for `walk.walk_package` against a synthetic `tinypkg` fixture."""

import pytest

from api_parity_py import walk


def _envelope() -> dict:
    return walk.walk_package("tinypkg")


def _path_kinds(env: dict) -> set[tuple[str, str]]:
    return {(e["path"], e["kind"]) for e in env["entries"]}


def _paths(env: dict) -> set[str]:
    return {e["path"] for e in env["entries"]}


def test_envelope_metadata_matches_schema():
    """Top-level envelope keys are spelled exactly as SCHEMA.md requires."""
    env = _envelope()
    assert env["schema_version"] == 1
    assert env["kind"] == "reference"
    assert env["language"] == "python"
    assert env["source"] == "tinypkg"
    assert isinstance(env["entries"], list)


def test_widget_class_and_members_are_emitted():
    """Regular method, property, and classmethod all appear with the
    correct `kind`. The property must be detected via raw-attribute
    lookup (a `getattr` on the class would invoke the descriptor)."""
    pk = _path_kinds(_envelope())
    assert ("tinypkg.core.Widget", "class") in pk
    assert ("tinypkg.core.Widget.foo", "method") in pk
    assert ("tinypkg.core.Widget.bar", "property") in pk
    assert ("tinypkg.core.Widget.bake", "method") in pk


def test_underscore_and_data_attrs_excluded():
    """Underscore-prefixed members and plain class attributes are not
    API surface and must be omitted from the inventory."""
    paths = _paths(_envelope())
    assert "tinypkg.core.Widget._private" not in paths
    assert "tinypkg.core.Widget.CONSTANT" not in paths


def test_nested_class_emitted_with_dotted_qualname():
    """Nested classes use `cls.__qualname__`, so `Widget.Inner` keeps its
    lexical structure in the path. Their members get the same treatment."""
    pk = _path_kinds(_envelope())
    assert ("tinypkg.core.Widget.Inner", "class") in pk
    assert ("tinypkg.core.Widget.Inner.baz", "method") in pk


def test_data_shape_subclass_filtered_out():
    """`RowLike(tuple)` is a data container, not API surface. The walker
    filters subclasses of `(tuple, list, dict, BaseException)`."""
    paths = _paths(_envelope())
    assert "tinypkg.core.RowLike" not in paths


def test_free_function_kind_is_function():
    """Module-level free functions are tagged `kind="function"`, distinct
    from class methods (which use `kind="method"`)."""
    pk = _path_kinds(_envelope())
    assert ("tinypkg.extras.helper", "function") in pk


def test_underscore_free_function_excluded():
    paths = _paths(_envelope())
    assert "tinypkg.extras._hidden" not in paths


def test_reexports_not_duplicated():
    """`tinypkg/__init__.py` re-exports `Widget` and `helper`. They must
    only appear under their *defining* module to keep the join key
    unambiguous on the differ side."""
    paths = _paths(_envelope())
    assert "tinypkg.Widget" not in paths
    assert "tinypkg.helper" not in paths


def test_entries_are_sorted_and_deduped():
    """Output stability is part of the wire contract — diffs across two
    runs of the walker must be minimal noise."""
    entries = _envelope()["entries"]
    keys = [(e["path"], e["kind"]) for e in entries]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))


def test_submodule_import_failures_surface_on_stderr(capsys, monkeypatch):
    """A missing optional dep silently dropped submodules used to make an
    incomplete walk look complete. The walker now prints a grouped stderr
    summary so the user notices."""
    original = walk.importlib.import_module

    def flaky(name: str, *a, **kw):
        # Make every submodule import after the top-level package raise.
        if name.startswith("tinypkg.") and name != "tinypkg":
            raise ImportError("simulated missing dep: pandas")
        return original(name, *a, **kw)

    monkeypatch.setattr(walk.importlib, "import_module", flaky)
    walk._preload_submodules("tinypkg")
    err = capsys.readouterr().err
    assert "skipped" in err
    assert "tinypkg" in err
    assert "simulated missing dep: pandas" in err
