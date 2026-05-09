"""Render a comparison report as JSON (pass-through with stable key order)."""

import json


def render(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=False)
