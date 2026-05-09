"""CLI: `api-parity-py <kind> <target> [-o PATH]`.

Currently supports:
  api-parity-py reference <package>   walk a Python package, emit reference JSON
"""

import argparse
import json
import sys
from pathlib import Path

from . import walk

EXIT_USAGE = 64


def main() -> int:
    ap = argparse.ArgumentParser(prog="api-parity-py")
    ap.add_argument("kind", choices=("reference", "port"))
    ap.add_argument("target",
                    help="package name (or comma-separated names, e.g. "
                         "'pyspark.sql.connect,pyspark.sql.session')")
    ap.add_argument("--version-from", default=None,
                    help="module to read `__version__` from "
                         "(e.g. `pyspark`)")
    ap.add_argument("-o", "--output", default="-",
                    help="output file path, or `-` for stdout (default)")
    args = ap.parse_args()

    if args.kind != "reference":
        sys.stderr.write(f"api-parity-py: kind={args.kind!r} is not yet implemented\n")
        return EXIT_USAGE

    envelope = walk.walk_package(args.target, version_from=args.version_from)
    text = json.dumps(envelope, indent=2)

    if args.output == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(args.output).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
