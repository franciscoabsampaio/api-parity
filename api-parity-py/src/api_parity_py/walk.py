"""Walk a Python package and emit a reference-side envelope (see SCHEMA.md).

# Algorithm

1. Preload every submodule of each requested package, so classes defined
   in lazy-imported modules show up in `sys.modules` and forward-reference
   strings are resolvable.
2. Walk the loaded modules. For each module under one of the requested
   packages, list its public classes — but only the ones *defined* there
   (i.e. `cls.__module__ == mod_name`), so re-exports don't double-count.
3. For each class, recurse into nested classes (e.g. `SparkSession.Builder`)
   and emit one entry per public method/property. Class-level data attrs
   (`MAX_MESSAGE_LENGTH = 128`) and nested classes are handled separately.
4. Module-level free functions are emitted with `kind = "function"`.

# Path keying

Each entry's `path` is `cls.__module__ + "." + cls.__qualname__` (for a
class) or `<class path>.<member>` (for a member). `__qualname__` includes
nesting, so `SparkSession.Builder` keeps its dotted lexical structure.

This means `pyspark.sql.session.SparkSession` and
`pyspark.sql.connect.session.SparkSession` are distinct entries — both
classes are tracked, no qualname collision, no priority/preference flag.
"""

import importlib
import inspect
import pkgutil
import sys
from collections import Counter

# `inspect.getmembers(object)` brings in `__init__`, `__doc__`, etc.; we
# strip those by name to keep the public API list focused on real surface.
_OBJECT_MEMBERS = frozenset(name for name, _ in inspect.getmembers(object))
# Subclasses of these are "data shapes", not API surface. Filtering by
# class hierarchy avoids clutter from `Row` (a tuple subclass), exception
# types, etc.
_DATA_BASES = (tuple, list, dict, BaseException)


def _preload_submodules(package_name: str) -> None:
    """Import every submodule of `package_name` into `sys.modules`.

    Without this, classes defined in lazy-loaded submodules would never be
    seen by the discovery walk, and string-form forward-reference type
    annotations (`'SparkConnectClient'`) wouldn't resolve.

    Submodules whose import raises (e.g. because an optional dep like
    pandas isn't installed) are collected and summarized on stderr so an
    incomplete walk is visibly incomplete instead of silently truncated.
    """
    try:
        pkg = importlib.import_module(package_name)
    except Exception as e:
        sys.stderr.write(
            f"api-parity-py: failed to import top-level package "
            f"{package_name!r}: {type(e).__name__}: {e}\n"
        )
        return
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        return

    failures: list[tuple[str, BaseException]] = []
    total = 0
    for _, mod_name, _ in pkgutil.walk_packages(pkg_path, prefix=package_name + "."):
        total += 1
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            failures.append((mod_name, e))

    if failures:
        _report_skipped(package_name, total, failures)


def _report_skipped(
    package_name: str,
    total: int,
    failures: list[tuple[str, BaseException]],
) -> None:
    """Print a grouped, terse summary of import failures to stderr."""
    reasons: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for mod, err in failures:
        first_line = str(err).splitlines()[0][:120] if str(err) else ""
        key = f"{type(err).__name__}: {first_line}" if first_line else type(err).__name__
        reasons[key] += 1
        examples.setdefault(key, mod)

    sys.stderr.write(
        f"api-parity-py: {package_name}: "
        f"skipped {len(failures)}/{total} submodule(s) — inventory will be incomplete\n"
    )
    for reason, count in reasons.most_common():
        sys.stderr.write(f"  - [{count}x] {reason}\n")
        sys.stderr.write(f"      e.g. {examples[reason]}\n")


def _raw_attr(cls: type, name: str) -> object:
    """Return the raw descriptor for `name` on `cls`, walking the MRO.

    We can't use `getattr(cls, name)` to detect properties — that triggers
    descriptor invocation and gives us the resolved value (e.g. a `Builder`
    instance) instead of the descriptor itself. Looking up via `__dict__`
    on each MRO class returns the raw `property` / `classmethod` object.
    """
    for klass in cls.__mro__:
        if name in klass.__dict__:
            return klass.__dict__[name]
    return None


def _member_kind(cls: type, name: str, value: object) -> str | None:
    """Classify a class member, or `None` to drop it from the inventory.

    `isinstance(raw, property)` catches `property` subclasses like pyspark's
    `classproperty`. Nested classes return None — they're emitted as their
    own top-level entries by the recursion in `_collect_class`. Callable
    values (functions, classmethods after descriptor invocation, etc.)
    become methods.
    """
    raw = _raw_attr(cls, name)
    if isinstance(raw, property):
        return "property"
    if isinstance(value, type):
        return None
    if callable(value):
        return "method"
    # Plain class attributes (constants, default values) are not API surface.
    return None


def _is_api_class(obj: object) -> bool:
    return isinstance(obj, type) and not issubclass(obj, _DATA_BASES)


def _collect_class(cls: type, entries: list[dict]) -> None:
    """Record `cls` and its members, then recurse into nested classes."""
    full = f"{cls.__module__}.{cls.__qualname__}"
    # Cheap dedup: re-exports may cause us to revisit a class. We bail
    # before doing redundant member walks.
    if any(e["path"] == full and e["kind"] == "class" for e in entries):
        return
    entries.append({"path": full, "kind": "class"})

    for name, value in inspect.getmembers(cls):
        if name.startswith("_") or name in _OBJECT_MEMBERS:
            continue
        kind = _member_kind(cls, name, value)
        if kind is None:
            continue
        entries.append({"path": f"{full}.{name}", "kind": kind})

    # Nested classes: their `__module__` matches the outer class's, and
    # their `__qualname__` is prefixed with `<outer>.` — those two checks
    # together filter out unrelated classes that happen to be exposed as
    # attributes (e.g. types pulled in for type hints).
    for name, obj in inspect.getmembers(cls):
        if name.startswith("_") or not _is_api_class(obj):
            continue
        if obj.__module__ != cls.__module__:
            continue
        if not obj.__qualname__.startswith(cls.__qualname__ + "."):
            continue
        _collect_class(obj, entries)


def _discover(packages: list[str]) -> list[dict]:
    """Walk every loaded module under `packages`, emit entries."""
    entries: list[dict] = []
    for mod_name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if not any(mod_name == p or mod_name.startswith(p + ".") for p in packages):
            continue

        # Top-level classes, recursing into their nested classes.
        for name, obj in inspect.getmembers(mod):
            if name.startswith("_") or not _is_api_class(obj):
                continue
            # Skip re-exports: only record a class in its defining module.
            # Without this, `pyspark.sql.SparkSession` (re-export from
            # `pyspark.sql.session`) would be listed twice with different
            # paths.
            if obj.__module__ != mod_name:
                continue
            _collect_class(obj, entries)

        # Module-level free functions (e.g. `pyspark.sql.functions.col`).
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_"):
                continue
            if obj.__module__ != mod_name:
                continue
            entries.append({
                "path": f"{obj.__module__}.{obj.__qualname__}",
                "kind": "function",
            })

    # Sort + dedup by (path, kind). Stability matters because the JSON
    # output is part of the contract — diffing two versions should produce
    # minimal noise.
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for e in sorted(entries, key=lambda e: (e["path"], e["kind"])):
        key = (e["path"], e["kind"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def walk_package(target: str, *, version_from: str | None = None) -> dict:
    """Build a reference envelope for one or more comma-separated packages.

    `version_from` names a module to import for its `__version__` (e.g.
    `"pyspark"`). If unimportable or missing the attribute, version is
    left null; this is informational metadata, not part of the join key.
    """
    packages = [p.strip() for p in target.split(",") if p.strip()]
    for pkg in packages:
        _preload_submodules(pkg)

    version = None
    if version_from:
        try:
            mod = importlib.import_module(version_from)
            version = getattr(mod, "__version__", None)
        except Exception:
            pass

    return {
        "schema_version": 1,
        "kind": "reference",
        "language": "python",
        "version": version,
        "source": ",".join(packages),
        "entries": _discover(packages),
    }
