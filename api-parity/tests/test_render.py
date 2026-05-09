"""Tests for the markdown and JSON renderers."""

import json

from api_parity import compare, render_json, render_markdown

from test_compare import REF, PORT


def test_markdown_has_top_level_sections():
    """Renderer emits the four headline sections in a stable order so
    downstream tooling (or humans grep'ing the output) can rely on them."""
    md = render_markdown.render(compare.build_report(REF, PORT))
    assert "# API parity report" in md
    assert "## Summary" in md
    assert "## Per-class coverage" in md
    assert "## Detail" in md


def test_markdown_summary_includes_coverage_percentage():
    """Coverage percentage is computed as covered / reference. With 3/4
    covered the rendered summary should show 75.0%."""
    md = render_markdown.render(compare.build_report(REF, PORT))
    assert "**3** (75.0%)" in md


def test_markdown_lists_class_in_per_class_table():
    md = render_markdown.render(compare.build_report(REF, PORT))
    assert "`tinypkg.A`" in md
    # Class status line in the Detail section.
    assert "Class status: **implemented**" in md


def test_markdown_surfaces_stale_port_paths():
    """Port entries with no matching reference path get a dedicated
    section so they aren't silently dropped."""
    md = render_markdown.render(compare.build_report(REF, PORT))
    assert "## Stale port references" in md
    assert "`tinypkg.A.ghost`" in md


def test_markdown_omits_stale_section_when_no_stale_entries():
    """The stale-references section is conditional — without any stale
    rows, the renderer should leave it out entirely."""
    no_stale_port = {
        **PORT,
        "entries": [e for e in PORT["entries"] if e["path"] != "tinypkg.A.ghost"],
    }
    md = render_markdown.render(compare.build_report(REF, no_stale_port))
    assert "## Stale port references" not in md


def test_json_render_round_trips_through_json_loads():
    """JSON output is a structural pass-through of the report dict; the
    parsed result must equal the original report."""
    rep = compare.build_report(REF, PORT)
    parsed = json.loads(render_json.render(rep))
    assert parsed["totals"] == rep["totals"]
    assert parsed["reference"] == rep["reference"]
    assert parsed["port"] == rep["port"]
    assert len(parsed["rows"]) == len(rep["rows"])
