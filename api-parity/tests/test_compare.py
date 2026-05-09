"""Tests for `compare.build_report` against hand-rolled envelopes."""

import pytest

from api_parity import compare


REF = {
    "schema_version": 1,
    "kind": "reference",
    "language": "python",
    "version": "1.0",
    "source": "tinypkg",
    "entries": [
        {"path": "tinypkg.A", "kind": "class"},
        {"path": "tinypkg.A.foo", "kind": "method"},
        {"path": "tinypkg.A.bar", "kind": "method"},
        {"path": "tinypkg.A.qux", "kind": "method"},
    ],
}

PORT = {
    "schema_version": 1,
    "kind": "port",
    "language": "rust",
    "version": "0.1.0",
    "source": "mycrate",
    "entries": [
        {"path": "tinypkg.A",
         "implementation": "A", "status": "implemented"},
        {"path": "tinypkg.A.foo",
         "implementation": "A::foo", "status": "implemented"},
        {"path": "tinypkg.A.bar",
         "implementation": "A::bar", "status": "partial",
         "comment": "no streaming"},
        {"path": "tinypkg.A.ghost",
         "implementation": "A::ghost", "status": "implemented"},
    ],
}


def test_totals_split_covered_stale_and_status_buckets():
    """`covered` counts only paths present in both sides; `stale` counts
    port-only paths; the per-status counters only track the covered subset
    (so `qux`, present only on the reference side, is not in any bucket)."""
    rep = compare.build_report(REF, PORT)
    t = rep["totals"]
    assert t["reference"] == 4
    assert t["covered"] == 3      # A, A.foo, A.bar
    assert t["stale"] == 1        # A.ghost
    assert t["implemented"] == 2  # A, A.foo
    assert t["partial"] == 1      # A.bar
    assert t["unimplemented"] == 0


def test_rows_classify_present_in_correctly():
    """Each row carries `present_in ∈ {both, reference, port}`. Reference
    metadata (`kind`) is preserved on `both`/`reference` rows, while
    port-only rows have `kind=None` since the port side doesn't carry it."""
    rep = compare.build_report(REF, PORT)
    by_path = {r["path"]: r for r in rep["rows"]}

    assert by_path["tinypkg.A"]["present_in"] == "both"
    assert by_path["tinypkg.A"]["kind"] == "class"

    assert by_path["tinypkg.A.qux"]["present_in"] == "reference"
    assert by_path["tinypkg.A.qux"]["kind"] == "method"
    assert by_path["tinypkg.A.qux"]["status"] is None

    assert by_path["tinypkg.A.ghost"]["present_in"] == "port"
    assert by_path["tinypkg.A.ghost"]["kind"] is None
    assert by_path["tinypkg.A.ghost"]["implementation"] == "A::ghost"


def test_port_metadata_propagates_to_covered_rows():
    """Port-side fields (status, implementation, since, issue, comment)
    appear on every `both` row joined from the port entry."""
    rep = compare.build_report(REF, PORT)
    bar = next(r for r in rep["rows"] if r["path"] == "tinypkg.A.bar")
    assert bar["status"] == "partial"
    assert bar["implementation"] == "A::bar"
    assert bar["comment"] == "no streaming"


def test_envelope_meta_round_trips():
    rep = compare.build_report(REF, PORT)
    assert rep["reference"] == {
        "language": "python", "version": "1.0", "source": "tinypkg",
    }
    assert rep["port"] == {
        "language": "rust", "version": "0.1.0", "source": "mycrate",
    }


def test_validate_rejects_wrong_kind():
    """Reference and port envelopes must declare matching `kind`s; mixing
    them up (e.g. passing a port envelope as the reference) is a hard
    error rather than silent garbage output."""
    swapped = {**REF, "kind": "port"}
    with pytest.raises(ValueError, match="expected kind='reference'"):
        compare.build_report(swapped, PORT)


def test_validate_rejects_unknown_schema_version():
    """The `schema_version` field is the wire-format gate. Unknown
    versions must fail loudly rather than risk a malformed join."""
    bad = {**REF, "schema_version": 99}
    with pytest.raises(ValueError, match="unsupported schema_version"):
        compare.build_report(bad, PORT)
