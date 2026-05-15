"""Annotation API for Python plugins.

Three decorators:

- ``@parity_impl(path=..., status=...)`` on a class. Sets a parent path
  for its methods; if both ``path`` and ``status`` are given, also
  registers a class-level port entry.
- ``@parity(path=..., status=...)`` on a method. A leading ``.`` makes
  the path relative to the enclosing ``@parity_impl``'s path. Free
  functions (no enclosing class) are supported with absolute paths.
- ``@parity_ref(path=..., kind=...)`` on a class / method / function.
  For declaring a reference inventory in code (rare; usually a walker
  is better).

Decorators write to module-level registries that the CLI dumps in
``port`` / ``reference`` mode with ``--mode annotation``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

_PORT_ENTRIES: list[dict] = []
_REFERENCE_ENTRIES: list[dict] = []


class Status(str, Enum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    UNIMPLEMENTED = "unimplemented"


def _normalize_status(status: Any) -> str:
    if isinstance(status, Status):
        return status.value
    if isinstance(status, str) and status in {s.value for s in Status}:
        return status
    raise TypeError(
        f"status must be a Status enum or one of {{implemented, partial, unimplemented}}, "
        f"got {status!r}"
    )


def _validate_port_args(status: str, comment: str | None) -> None:
    if status == Status.UNIMPLEMENTED.value and not comment:
        raise ValueError(
            "status=Unimplemented requires a comment explaining why"
        )


def parity(
    path: str,
    status: Status | str,
    *,
    since: str | None = None,
    issue: int | None = None,
    comment: str | None = None,
) -> Callable:
    """Method-level / free-function port annotation.

    Inside a ``@parity_impl`` class, a leading ``.`` in ``path`` is
    rewritten as ``parent_path + child`` when the class decorator runs.
    For free functions the path must be absolute.
    """
    status_str = _normalize_status(status)
    _validate_port_args(status_str, comment)
    meta = {
        "path": path,
        "status": status_str,
        "since": since,
        "issue": issue,
        "comment": comment,
    }

    def decorate(fn: Callable) -> Callable:
        if path.startswith("."):
            # Relative path: stash meta so the enclosing `parity_impl`
            # sweep can resolve it against the parent path.
            fn._parity_meta = meta  # type: ignore[attr-defined]
            return fn
        # Absolute path: register immediately. Works for free functions
        # and for class methods whose path is unrelated to their enclosing
        # type. We don't stash meta — that would cause `parity_impl` to
        # double-register the same entry.
        impl = f"{fn.__module__}.{fn.__qualname__}"
        _PORT_ENTRIES.append({**meta, "implementation": impl})
        return fn

    return decorate


def parity_impl(
    path: Any = None,
    status: Status | str | None = None,
    *,
    since: str | None = None,
    issue: int | None = None,
    comment: str | None = None,
) -> Callable:
    """Class-level port annotation.

    Two call forms:

    - ``@parity_impl(path="...", status=...)`` — with args, registers a
      class-level entry and provides a parent path for relative children.
    - ``@parity_impl`` — bare, no args. Sweeps the class for relative
      ``@parity`` children but registers no class-level entry (and a
      child with a leading-``.`` path is an error in this form).

    Either way, the class's ``__dict__`` is swept and any
    ``@parity``-decorated method with relative path gets joined with the
    parent's ``path`` and registered.
    """
    # Bare-decorator form: Python passes the class as the first arg.
    if isinstance(path, type) and status is None:
        return parity_impl()(path)

    parent_path = path
    parent_status = _normalize_status(status) if status is not None else None
    if parent_status is not None:
        _validate_port_args(parent_status, comment)

    def decorate(cls: type) -> type:
        # Class-level entry, if both path and status given.
        if parent_path and parent_status:
            _PORT_ENTRIES.append({
                "path": parent_path,
                "implementation": f"{cls.__module__}.{cls.__qualname__}",
                "status": parent_status,
                "since": since,
                "issue": issue,
                "comment": comment,
            })

        # Sweep methods. We look at __dict__ rather than dir() so we
        # only see things defined on this class (not inherited), and so
        # properties / classmethods come back as their raw descriptor
        # (which is what the @parity decorator attached the meta to).
        for name, value in cls.__dict__.items():
            inner = value
            if isinstance(value, (classmethod, staticmethod)):
                inner = value.__func__
            elif isinstance(value, property):
                inner = value.fget
            meta = getattr(inner, "_parity_meta", None)
            if not meta:
                continue
            child_path = meta["path"]
            if child_path.startswith("."):
                if not parent_path:
                    raise ValueError(
                        f"@parity({child_path!r}) on {cls.__qualname__}.{name} "
                        f"requires the enclosing @parity_impl to declare a path"
                    )
                full_path = f"{parent_path}{child_path}"
            else:
                full_path = child_path
            _PORT_ENTRIES.append({
                "path": full_path,
                "implementation": f"{cls.__module__}.{cls.__qualname__}.{name}",
                "status": meta["status"],
                "since": meta["since"],
                "issue": meta["issue"],
                "comment": meta["comment"],
            })
        return cls

    return decorate


def parity_ref(path: str, kind: str) -> Callable:
    """Code-level reference entry. Apply to a class / method / function."""
    if kind not in {"class", "method", "property", "function"}:
        raise ValueError(
            f"kind must be one of class/method/property/function, got {kind!r}"
        )
    entry = {"path": path, "kind": kind}

    def decorate(target: Any) -> Any:
        _REFERENCE_ENTRIES.append(entry)
        return target

    return decorate


def collect_port_entries() -> list[dict]:
    """Return all port entries registered so far, sorted+deduped by path."""
    return _sort_dedup(_PORT_ENTRIES, key=("path",))


def collect_reference_entries() -> list[dict]:
    """Return all reference entries registered so far, sorted+deduped."""
    return _sort_dedup(_REFERENCE_ENTRIES, key=("path", "kind"))


def reset_registries() -> None:
    """Clear both registries. Intended for tests."""
    _PORT_ENTRIES.clear()
    _REFERENCE_ENTRIES.clear()


def _sort_dedup(entries: list[dict], key: tuple[str, ...]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for e in sorted(entries, key=lambda d: tuple(d.get(k) or "" for k in key)):
        k = tuple(e.get(field) for field in key)
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out
