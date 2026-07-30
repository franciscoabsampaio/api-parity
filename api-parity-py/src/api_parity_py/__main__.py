"""CLI: ``api-parity-py <kind> [--mode walker|annotation] <target> [-o PATH]``.

Supported combos:
  reference walker     walk a package's public API (default for reference)
  reference annotation collect ``@parity_ref`` decorators in a package
  reference ast        parse source files without importing them
  port      walker     walk a package and synthesize implemented port entries
  port      annotation collect ``@parity_impl`` / ``@parity`` decorators
                       (default for port)

``target`` is always the dotted module name being inventoried. ``walker``
and ``annotation`` import it; ``ast``, selected by ``--from-source``,
reads those files instead and takes ``target`` as the dotted name the
source has upstream.
"""

import argparse
import importlib
import json
import sys
from pathlib import Path

from . import ast_walk, walk
from .parity import collect_port_entries, collect_reference_entries

EXIT_USAGE = 64


def main() -> int:
    ap = argparse.ArgumentParser(prog="api-parity-py")
    ap.add_argument("kind", choices=("reference", "port"))
    ap.add_argument(
        "--mode",
        choices=("walker", "annotation"),
        default=None,
        help="how entries are produced (defaults: reference→walker, port→annotation)",
    )
    ap.add_argument(
        "target",
        help="dotted module name (or comma-separated names, e.g. "
        "'pyspark.sql.connect,pyspark.sql.session'); with `--from-source`, "
        "the name the scanned source has upstream",
    )
    ap.add_argument(
        "--version-from",
        default=None,
        help="module to read `__version__` from (e.g. `pyspark`)",
    )
    ap.add_argument(
        "--from-source",
        metavar="PATH",
        default=None,
        help="read the file or directory at PATH (comma-separated for "
        "several) instead of importing `target`",
    )
    ap.add_argument(
        "-o",
        "--output",
        default="-",
        help="output file path, or `-` for stdout (default)",
    )
    args = ap.parse_args()

    if args.from_source:
        error = _check_source_args(args.mode, args.target)
        if error:
            sys.stderr.write(f"api-parity-py: {error}\n")
            return EXIT_USAGE
    mode = "ast" if args.from_source else (args.mode or _default_mode(args.kind))

    envelope = _build_envelope(
        kind=args.kind,
        mode=mode,
        target=args.target,
        version_from=args.version_from,
        from_source=args.from_source,
    )
    if envelope is None:
        sys.stderr.write(
            f"api-parity-py: ({args.kind}, mode={mode}) is not yet implemented\n"
        )
        return EXIT_USAGE

    text = json.dumps(envelope, indent=2)
    if args.output == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(args.output).write_text(text + "\n")
    return 0


def _default_mode(kind: str) -> str:
    return "annotation" if kind == "port" else "walker"


def _check_source_args(mode: str | None, target: str) -> str | None:
    """Reject `--from-source` combinations that can't mean anything."""
    if mode:
        return f"--from-source reads source without importing it; --mode {mode} loads the target"
    if "," in target:
        return (
            "--from-source takes one target: the dotted name its root maps to "
            "(pass several paths instead, comma-separated)"
        )
    return None


def _build_envelope(
    *,
    kind: str,
    mode: str,
    target: str,
    version_from: str | None,
    from_source: str | None = None,
) -> dict | None:
    if kind == "reference" and mode == "walker":
        return walk.walk_package(target, version_from=version_from)
    if kind == "reference" and mode == "ast" and from_source:
        return ast_walk.walk_source(
            from_source, module=target, version_from=version_from
        )
    if kind == "reference" and mode == "annotation":
        return _collect_annotations(target, version_from, kind="reference")
    if kind == "port" and mode == "annotation":
        return _collect_annotations(target, version_from, kind="port")
    if kind == "port" and mode == "walker":
        return _walker_as_port(target, version_from)
    return None


def _import_target_packages(target: str) -> list[str]:
    """Import every submodule of every requested package so decorators run."""
    packages = [p.strip() for p in target.split(",") if p.strip()]
    for pkg in packages:
        walk._preload_submodules(pkg)
    return packages


def _read_version(version_from: str | None) -> str | None:
    if not version_from:
        return None
    try:
        mod = importlib.import_module(version_from)
        return getattr(mod, "__version__", None)
    except Exception:
        return None


def _collect_annotations(
    target: str, version_from: str | None, *, kind: str,
) -> dict:
    packages = _import_target_packages(target)
    if kind == "port":
        entries = collect_port_entries()
    else:
        entries = collect_reference_entries()
    return {
        "schema_version": 1,
        "kind": kind,
        "language": "python",
        "version": _read_version(version_from),
        "source": ",".join(packages),
        "entries": entries,
    }


def _walker_as_port(target: str, version_from: str | None) -> dict:
    """Treat every walked public API as `status=implemented`. Useful for
    py-vs-py comparisons where neither side is annotated."""
    ref = walk.walk_package(target, version_from=version_from)
    entries = []
    for e in ref["entries"]:
        impl = e["path"]
        entries.append({
            "path": e["path"],
            "implementation": impl,
            "status": "implemented",
            "since": None,
            "issue": None,
            "comment": None,
        })
    return {**ref, "kind": "port", "entries": entries}


if __name__ == "__main__":
    sys.exit(main())
