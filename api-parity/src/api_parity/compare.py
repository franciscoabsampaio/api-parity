"""Left-join port entries onto reference entries by `path`."""

from typing import Any


def build_report(reference: dict, port: dict) -> dict:
    """
    Returns a structured report:
      {
        "reference": {language, version, source},
        "port":      {language, version, source},
        "rows": [
          {path, kind, status, implementation, since, issue, comment, present_in: "both"|"reference"|"port"},
          ...
        ],
        "totals": {...},
      }
    """
    _validate(reference, expected_kind="reference")
    _validate(port, expected_kind="port")

    ref_by_path: dict[str, dict] = {e["path"]: e for e in reference["entries"]}
    port_by_path: dict[str, dict] = {e["path"]: e for e in port["entries"]}

    rows: list[dict] = []

    for path, ref in ref_by_path.items():
        p = port_by_path.get(path)
        rows.append({
            "path":           path,
            "kind":           ref.get("kind"),
            "present_in":     "both" if p is not None else "reference",
            "status":         (p or {}).get("status"),
            "implementation": (p or {}).get("implementation"),
            "since":          (p or {}).get("since"),
            "issue":          (p or {}).get("issue"),
            "comment":        (p or {}).get("comment"),
        })

    for path, p in port_by_path.items():
        if path in ref_by_path:
            continue
        rows.append({
            "path":           path,
            "kind":           None,
            "present_in":     "port",
            "status":         p.get("status"),
            "implementation": p.get("implementation"),
            "since":          p.get("since"),
            "issue":          p.get("issue"),
            "comment":        p.get("comment"),
        })

    return {
        "reference": _envelope_meta(reference),
        "port":      _envelope_meta(port),
        "rows":      rows,
        "totals":    _totals(rows),
    }


def _envelope_meta(env: dict) -> dict[str, Any]:
    return {k: env.get(k) for k in ("language", "version", "source")}


def _totals(rows: list[dict]) -> dict[str, int]:
    out = {"reference": 0, "covered": 0, "stale": 0,
           "implemented": 0, "partial": 0, "unimplemented": 0}
    for r in rows:
        if r["present_in"] in ("both", "reference"):
            out["reference"] += 1
        if r["present_in"] == "both":
            out["covered"] += 1
            if r["status"] in out:
                out[r["status"]] += 1
        if r["present_in"] == "port":
            out["stale"] += 1
    return out


def _validate(env: dict, expected_kind: str) -> None:
    if env.get("schema_version") != 1:
        raise ValueError(f"unsupported schema_version: {env.get('schema_version')}")
    if env.get("kind") != expected_kind:
        raise ValueError(f"expected kind={expected_kind!r}, got {env.get('kind')!r}")
