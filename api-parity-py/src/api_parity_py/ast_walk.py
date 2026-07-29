"""Build a reference envelope by parsing Python source, without importing it.

# Why a second discovery mechanism

[`walk.py`](walk.py) imports the target package and introspects live
objects. That resolves inheritance, lazily-imported submodules, and
descriptors — none of which source text alone can tell you — so it stays
the right default for real API surface.

It also requires the target to be *importable*, which is not always true
of the thing you want to inventory:

- Test suites are frequently not shipped in a distribution, so there is
  no installed copy to import; a vendored file is all you have.
- Importing pulls the module's whole dependency graph. A test module
  that reaches a heavyweight testing package can fail to import for
  reasons that have nothing to do with the names you wanted to read.

This module reads the same names straight off the syntax tree. For
declarative code — a class whose methods are spelled out literally in
its body — parsing sees exactly what importing would.

# What it cannot do

Only what is lexically present in one file is visible:

- Base classes are names, not resolved classes, so inherited members are
  invisible. `class Sub(Mixin)` emits `Sub` alone; `Mixin`'s methods stay
  attributed to `Mixin`.
- Anything built at import time — dynamic attributes, generated methods,
  re-exports — is not there to see.
- `kind` comes from decorator *spelling*: a member decorated `@property`
  is a property; an aliased or custom descriptor reads as a method.

Prefer `walker` whenever the target imports cleanly.

# Path keying

Paths are `<module>.<qualname>`, matching the walker, so both mechanisms
join against the same port entries. The module part starts from the
caller's `module` — the dotted name the scanned target has upstream —
and, for a directory, is extended by each file's location beneath it. A
vendored tree therefore reproduces the names it has upstream rather than
the ones its checkout happens to give it.
"""

import ast
import importlib
import sys
from pathlib import Path

# Mirrors `walk.py`: leading-underscore names are not public API.
_PRIVATE = "_"


def _module_name(path: Path, root: Path, module: str | None) -> str:
    """Derive a dotted module name for `path` beneath `root`, which is
    itself the module named `module`.

    `__init__.py` collapses onto its package, so `pkg/__init__.py` is
    `pkg` rather than `pkg.__init__`.
    """
    relative = path.relative_to(root).with_suffix("")
    parts = [p for p in relative.parts if p != "__init__"]
    dotted = ".".join(parts)
    if module:
        return f"{module}.{dotted}" if dotted else module
    return dotted


def _decorator_names(node: ast.AST) -> list[str]:
    """Last-segment names of a def's decorators.

    `@property` yields `property`; `@foo.setter` yields `setter`;
    `@lru_cache(maxsize=1)` unwraps the call and yields `lru_cache`.
    """
    names: list[str] = []
    for decorator in getattr(node, "decorator_list", []):
        while isinstance(decorator, ast.Call):
            decorator = decorator.func
        if isinstance(decorator, ast.Name):
            names.append(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            names.append(decorator.attr)
    return names


def _member_kind(node: ast.AST) -> str:
    """Classify a def inside a class body by how it is decorated."""
    decorators = _decorator_names(node)
    if "property" in decorators or "cached_property" in decorators:
        return "property"
    return "method"


def _is_def(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))


def _collect_class(
    node: ast.ClassDef,
    module: str,
    outer_qualname: str,
    entries: list[dict],
) -> None:
    """Record `node` and its members, then recurse into nested classes.

    Nested classes keep their dotted lexical structure, the same way the
    walker uses `__qualname__` — `Widget.Inner`, not `Inner`.
    """
    qualname = f"{outer_qualname}.{node.name}" if outer_qualname else node.name
    full = f"{module}.{qualname}"
    entries.append({"path": full, "kind": "class"})

    for item in node.body:
        if item.__class__ is ast.ClassDef:
            if not item.name.startswith(_PRIVATE):
                _collect_class(item, module, qualname, entries)
        elif _is_def(item) and not item.name.startswith(_PRIVATE):
            entries.append({
                "path": f"{full}.{item.name}",
                "kind": _member_kind(item),
            })


def _collect_module(source: str, module: str, entries: list[dict]) -> None:
    """Emit top-level classes (recursing into them) and free functions."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith(_PRIVATE):
                _collect_class(node, module, "", entries)
        elif _is_def(node) and not node.name.startswith(_PRIVATE):
            entries.append({
                "path": f"{module}.{node.name}",
                "kind": "function",
            })


def _source_units(target: Path, module: str | None) -> list[tuple[Path, str]]:
    """Pair each file to read with the dotted module name it carries.

    A directory *is* `module`, and the files beneath it extend it. A
    single file is itself `module`, so its stem doesn't repeat a name the
    caller has already given.
    """
    if target.is_dir():
        files = sorted(target.rglob("*.py"))
        return [(path, _module_name(path, target, module)) for path in files]
    return [(target, module or target.stem)]


def _report_failures(failures: list[tuple[Path, SyntaxError]]) -> None:
    """Announce unparseable files, so a partial walk is visibly partial."""
    sys.stderr.write(
        f"api-parity-py: skipped {len(failures)} unparseable file(s) — "
        f"inventory will be incomplete\n"
    )
    for path, error in failures:
        sys.stderr.write(f"  - {path}: {error.msg} (line {error.lineno})\n")


def _read_version(version_from: str | None) -> str | None:
    """Import `version_from` purely for its `__version__`.

    The scan itself imports nothing; this is separate, optional metadata
    and stays silent when the module is absent.
    """
    if not version_from:
        return None
    try:
        return getattr(importlib.import_module(version_from), "__version__", None)
    except Exception:
        return None


def walk_source(
    source: str,
    *,
    module: str | None = None,
    version_from: str | None = None,
) -> dict:
    """Build a reference envelope from comma-separated files or directories.

    `module` is the dotted name each scanned root maps to; entries are
    keyed beneath it. Omitting it names modules by file location alone,
    which only matches a runtime walk when the scan is rooted where the
    import system would root it.
    """
    roots = [Path(t.strip()) for t in source.split(",") if t.strip()]

    entries: list[dict] = []
    failures: list[tuple[Path, SyntaxError]] = []
    for item in roots:
        if not item.exists():
            sys.stderr.write(f"api-parity-py: no such file or directory: {item}\n")
            continue
        for path, name in _source_units(item, module):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                sys.stderr.write(f"api-parity-py: cannot read {path}: {e}\n")
                continue
            try:
                _collect_module(text, name, entries)
            except SyntaxError as e:
                failures.append((path, e))

    if failures:
        _report_failures(failures)

    return {
        "schema_version": 1,
        "kind": "reference",
        "language": "python",
        "version": _read_version(version_from),
        # The dotted name, not the checkout path: `source` identifies what
        # was inventoried, and that is the same string a walk would report.
        "source": module or ",".join(str(t) for t in roots),
        "entries": _dedup(entries),
    }


def _dedup(entries: list[dict]) -> list[dict]:
    """Sort and dedup by `(path, kind)`, matching the walker.

    Output stability is part of the contract: diffing two versions should
    produce minimal noise.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for entry in sorted(entries, key=lambda e: (e["path"], e["kind"])):
        key = (entry["path"], entry["kind"])
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out
