"""Render a comparison report (from `compare.build_report`) as Markdown.

The report's `rows` are flat — each row is one path. To produce a useful
human view we group rows by their *parent* path, so methods/properties
appear under the class they belong to. The grouping is structural (split
on the last dot); we don't need any extra metadata from the entries.
"""

from collections import defaultdict


def render(report: dict) -> str:
    out: list[str] = []
    ref = report["reference"]
    port = report["port"]

    out.append("# API parity report")
    out.append("")
    out.append(
        "_Generated with [api-parity](https://github.com/franciscoabsampaio/api-parity)._"
    )
    out.append("")

    out.append(f"- Reference: {ref.get('language')} `{ref.get('source')}` "
               f"(version `{ref.get('version')}`)")
    out.append(f"- Port:      {port.get('language')} `{port.get('source')}` "
               f"(version `{port.get('version')}`)")
    out.append("")

    out.append("## Summary")
    out.append("")
    t = report["totals"]
    coverage = (100.0 * t["covered"] / t["reference"]) if t["reference"] else 0.0
    out.append(f"- Reference paths: **{t['reference']}**")
    out.append(f"- Covered: **{t['covered']}** ({coverage:.1f}%)")
    out.append(f"  - implemented: {t['implemented']}")
    out.append(f"  - partial: {t['partial']}")
    out.append(f"  - unimplemented: {t['unimplemented']}")
    out.append(f"- Stale port paths (no match in reference): **{t['stale']}**")
    out.append("")

    # Group rows by their parent path. A class entry (`kind == "class"`)
    # is the "header" for its group; methods/properties whose path
    # rpartitions to that class go underneath. Classes themselves group
    # under their containing module, but we surface them as top-level
    # headers in the output.
    classes: dict[str, dict] = {}
    members: dict[str, list[dict]] = defaultdict(list)
    other: list[dict] = []  # rows that don't fit (free functions, stale, etc.)

    for r in report["rows"]:
        if r.get("kind") == "class":
            classes[r["path"]] = r
        else:
            head, _, _tail = r["path"].rpartition(".")
            if head and head in {row["path"] for row in report["rows"] if row.get("kind") == "class"}:
                members[head].append(r)
            else:
                other.append(r)

    out.append("## Per-class coverage")
    out.append("")
    out.append("| Class | Class status | Members | Covered | % |")
    out.append("|---|---|---:|---:|---:|")

    rows_sorted = sorted(
        classes.items(),
        key=lambda kv: (-_class_pct(kv[0], members[kv[0]]),
                        -_covered_count(members[kv[0]]),
                        kv[0]),
    )
    for cls_path, cls_row in rows_sorted:
        ms = members[cls_path]
        total = len(ms)
        cov = _covered_count(ms)
        pct = (100.0 * cov / total) if total else 0.0
        cls_status = cls_row.get("status") or "—"
        out.append(f"| `{cls_path}` | {cls_status} | {total} | {cov} | {pct:.0f}% |")
    out.append("")

    out.append("## Detail")
    out.append("")
    for cls_path, cls_row in rows_sorted:
        ms = members[cls_path]
        # Skip classes with nothing covered and no class-level entry — the
        # report is noisy enough without rendering 200 fully-uncovered rows.
        if cls_row.get("status") is None and not any(m["status"] for m in ms):
            continue
        out.append(f"### `{cls_path}`")
        out.append("")
        if cls_row.get("status") is not None:
            impl = cls_row.get("implementation") or "—"
            comment = cls_row.get("comment") or ""
            line = f"- Class status: **{cls_row['status']}** (impl `{impl}`)"
            if comment:
                line += f" — {comment}"
            out.append(line)
            out.append("")
        out.append("| Member | Kind | Status | Implementation | Comment |")
        out.append("|---|---|---|---|---|")
        for m in sorted(ms, key=lambda r: r["path"]):
            _, _, name = m["path"].rpartition(".")
            kind = m.get("kind") or "—"
            status = m.get("status") or "—"
            impl = f"`{m['implementation']}`" if m.get("implementation") else "—"
            comment = m.get("comment") or ""
            out.append(f"| `{name}` | {kind} | {status} | {impl} | {comment} |")
        out.append("")

    stale = [r for r in report["rows"] if r["present_in"] == "port"]
    if stale:
        out.append("## Stale port references")
        out.append("")
        out.append("Port entries whose `path` did not resolve in the reference.")
        out.append("Likely a typo, a removed reference API, or a path-convention drift.")
        out.append("")
        out.append("| Path | Implementation | Comment |")
        out.append("|---|---|---|")
        for r in stale:
            impl = f"`{r['implementation']}`" if r.get("implementation") else "—"
            comment = r.get("comment") or ""
            out.append(f"| `{r['path']}` | {impl} | {comment} |")
        out.append("")

    return "\n".join(out)


def _covered_count(members: list[dict]) -> int:
    return sum(1 for m in members if m["present_in"] == "both")


def _class_pct(cls_path: str, members: list[dict]) -> float:
    if not members:
        return 0.0
    return 100.0 * _covered_count(members) / len(members)
