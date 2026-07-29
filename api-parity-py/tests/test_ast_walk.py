"""Tests for `ast_walk.walk_source` against the `srctree` fixture."""

from pathlib import Path

from api_parity_py import ast_walk

FIXTURES = Path(__file__).parent / "fixtures"
SRCTREE = FIXTURES / "srctree"
BROKEN = FIXTURES / "brokensrc"


def _envelope(source: Path = SRCTREE, **kwargs) -> dict:
    return ast_walk.walk_source(str(source), **kwargs)


def _path_kinds(env: dict) -> set[tuple[str, str]]:
    return {(e["path"], e["kind"]) for e in env["entries"]}


def _paths(env: dict) -> set[str]:
    return {e["path"] for e in env["entries"]}


def test_envelope_metadata_matches_schema():
    """Top-level keys are spelled exactly as SCHEMA.md requires, so the
    differ can consume an AST envelope as readily as a walked one."""
    env = _envelope()
    assert env["schema_version"] == 1
    assert env["kind"] == "reference"
    assert env["language"] == "python"
    assert env["source"] == str(SRCTREE)  # no `module`: falls back to the path
    assert isinstance(env["entries"], list)


def test_members_classified_by_decorator_spelling():
    """`kind` comes from how a decorator is written, since there is no
    live descriptor to inspect. A plain def is a method, `@property` and
    `@cached_property` are properties, and `@classmethod` stays a method."""
    pk = _path_kinds(_envelope())
    assert ("gadgets.Gadget", "class") in pk
    assert ("gadgets.Gadget.run", "method") in pk
    assert ("gadgets.Gadget.label", "property") in pk
    assert ("gadgets.Gadget.cached", "property") in pk
    assert ("gadgets.Gadget.build", "method") in pk


def test_decorator_written_as_a_call_is_unwrapped():
    """`@lru_cache(maxsize=1)` is an `ast.Call`; the name has to be read
    from inside it or the member would be misclassified."""
    assert ("gadgets.Gadget.wrapped", "method") in _path_kinds(_envelope())


def test_underscore_and_data_attrs_excluded():
    """Underscore-prefixed defs and plain class attributes are not API
    surface, matching the walker's rules."""
    paths = _paths(_envelope())
    assert "gadgets.Gadget._hidden" not in paths
    assert "gadgets.Gadget.CONSTANT" not in paths
    assert "gadgets._private_helper" not in paths


def test_nested_class_emitted_with_dotted_qualname():
    """Nested classes keep their lexical nesting, so paths line up with
    the walker's `__qualname__`-derived ones."""
    pk = _path_kinds(_envelope())
    assert ("gadgets.Gadget.Inner", "class") in pk
    assert ("gadgets.Gadget.Inner.baz", "method") in pk


def test_module_level_function_kind():
    """Free functions are `function`, not `method`."""
    assert ("gadgets.helper", "function") in _path_kinds(_envelope())


def test_inherited_members_are_not_attributed_to_the_subclass():
    """The documented blind spot: a base class is only a name in the
    syntax tree, so `Derived` gets its own members and nothing more.
    Asserted so the limitation is visible rather than surprising."""
    paths = _paths(_envelope())
    assert "gadgets.Derived.extra" in paths
    assert "gadgets.Derived.run" not in paths


def test_directory_scan_derives_dotted_module_names():
    """Module names come from the path relative to the scanned root, and
    `__init__.py` collapses onto its package."""
    pk = _path_kinds(_envelope())
    assert ("sub.Marker", "class") in pk
    assert ("sub.nested.Deep", "class") in pk
    assert not any(p.startswith("sub.__init__") for p in _paths(_envelope()))


def test_single_file_target_is_named_by_its_stem():
    """Pointing at one file names it by its stem, rather than dragging in
    the whole directory."""
    env = _envelope(SRCTREE / "gadgets.py")
    paths = _paths(env)
    assert "gadgets.Gadget" in paths
    assert not any(p.startswith("sub") for p in paths)


def test_single_file_module_is_the_file_itself():
    """`module` names whatever was pointed at, so for one file it is that
    module — appending the stem would double the last segment."""
    env = _envelope(SRCTREE / "gadgets.py", module="acme.vendored.gadgets")
    paths = _paths(env)
    assert "acme.vendored.gadgets.Gadget" in paths
    assert "acme.vendored.gadgets.gadgets.Gadget" not in paths


def test_module_restores_upstream_paths():
    """A vendored file lives at an arbitrary checkout path, but must be
    keyed by the dotted name it has upstream so it joins against port
    annotations written against that name."""
    env = _envelope(module="acme.vendored")
    pk = _path_kinds(env)
    assert ("acme.vendored.gadgets.Gadget", "class") in pk
    assert ("acme.vendored.sub.nested.Deep", "class") in pk
    assert env["source"] == "acme.vendored"


def test_unparseable_file_is_skipped_and_reported(capsys):
    """One bad file must not sink the scan; the rest still comes through,
    and the skip is announced so a partial inventory is visibly partial."""
    env = _envelope(BROKEN)

    assert ("brokensrc.Intact", "class") not in _path_kinds(env)
    assert ("intact.Intact", "class") in _path_kinds(env)
    assert "broken.Unfinished" not in _paths(env)
    assert "skipped 1 unparseable file" in capsys.readouterr().err


def test_missing_target_is_reported_without_crashing(capsys):
    """A typo'd path should be a diagnosable message, not a traceback."""
    env = ast_walk.walk_source(str(FIXTURES / "does_not_exist"))

    assert env["entries"] == []
    assert "no such file or directory" in capsys.readouterr().err


def test_entries_are_sorted_and_deduped():
    """Output stability is part of the contract — diffing two versions of
    an inventory should produce minimal noise."""
    entries = _envelope()["entries"]
    keys = [(e["path"], e["kind"]) for e in entries]

    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))


def test_version_comes_from_an_unrelated_module():
    """`--version-from` names some installed module to read `__version__`
    off; an absent one is metadata-only and must not fail the scan."""
    import json

    assert _envelope(version_from="json")["version"] == json.__version__
    assert _envelope(version_from="no_such_module_at_all")["version"] is None


def test_scanned_source_is_never_imported():
    """The whole point of this mode: reading a file must not execute it,
    so unimportable targets still yield an inventory."""
    import sys

    for module in ("gadgets", "sub", "sub.nested"):
        sys.modules.pop(module, None)

    assert _paths(_envelope())  # non-empty, so the scan really ran

    assert not any(m in sys.modules for m in ("gadgets", "sub", "sub.nested"))
