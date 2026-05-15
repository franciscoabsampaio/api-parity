"""End-to-end acceptance tests for `api-parity compare`.

Drives `cli.main()` with on-disk fixture envelopes, in both rendering
formats, asserting structural properties of the output.
"""

import json
import sys
from pathlib import Path

import pytest

from api_parity import __main__ as cli


FIXTURES = Path(__file__).parent / "fixtures"
REF_PATH = FIXTURES / "ref.json"
PORT_PATH = FIXTURES / "port.json"


def _run(*argv: str, capsys) -> str:
    sys.argv = ["api-parity", *argv]
    rc = cli.main()
    assert rc == 0, capsys.readouterr().err
    return capsys.readouterr().out


def test_compare_markdown_against_fixtures(capsys):
    """Default `compare REF PORT` renders markdown to stdout, including
    the coverage % and stale-references sections."""
    out = _run("compare", str(REF_PATH), str(PORT_PATH), capsys=capsys)
    assert "# API parity report" in out
    assert "**3** (75.0%)" in out
    assert "## Stale port references" in out
    assert "`tinypkg.A.ghost`" in out


def test_compare_json_format_parses_as_report(capsys):
    """`--format json` round-trips through json.loads to a report dict
    with totals, rows, reference and port metadata."""
    out = _run(
        "compare", str(REF_PATH), str(PORT_PATH), "--format=json", capsys=capsys,
    )
    report = json.loads(out)
    assert report["totals"]["reference"] == 4
    assert report["totals"]["covered"] == 3
    assert report["totals"]["stale"] == 1
    assert report["reference"]["language"] == "python"
    assert report["port"]["language"] == "rust"


def test_compare_writes_output_file(tmp_path, capsys):
    """`-o PATH` writes the rendered report to a file instead of stdout."""
    out_file = tmp_path / "report.md"
    sys.argv = [
        "api-parity", "compare",
        str(REF_PATH), str(PORT_PATH),
        "-o", str(out_file),
    ]
    rc = cli.main()
    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out == ""  # nothing on stdout when -o is set
    body = out_file.read_text()
    assert "# API parity report" in body
