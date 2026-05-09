"""CLI: `api-parity compare REF PORT [-o OUT] [--format markdown|json]`."""

import argparse
import json
import sys
from pathlib import Path

from . import compare, render_json, render_markdown


def _load(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text())


def main() -> int:
    ap = argparse.ArgumentParser(prog="api-parity")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cmp = sub.add_parser("compare", help="diff a reference and a port inventory")
    cmp.add_argument("reference", help="reference JSON path, or `-` for stdin")
    cmp.add_argument("port",      help="port JSON path, or `-` for stdin")
    cmp.add_argument("-o", "--output", default=None,
                     help="output file (default: stdout)")
    cmp.add_argument("--format", choices=("markdown", "json"), default="markdown")

    args = ap.parse_args()
    if args.cmd != "compare":
        ap.error(f"unknown command: {args.cmd}")

    if args.reference == "-" and args.port == "-":
        ap.error("only one of REF / PORT can be `-`")

    ref = _load(args.reference)
    port = _load(args.port)
    report = compare.build_report(ref, port)

    rendered = (
        render_json.render(report)
        if args.format == "json"
        else render_markdown.render(report)
    )

    if args.output:
        Path(args.output).write_text(rendered + "\n")
    else:
        sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
