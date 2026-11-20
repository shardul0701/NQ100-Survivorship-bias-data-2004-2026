#!/usr/bin/env python3
"""Fail a release when the generated freshness report is absent or unhealthy."""

from __future__ import annotations

import json
from pathlib import Path


REPORT = Path(__file__).resolve().parents[1] / "metadata" / "data_freshness.json"


def gate(report: Path = REPORT) -> int:
    try:
        state = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("freshness report must be a JSON object")
    except (OSError, ValueError) as exc:
        print(f"::error::Freshness is unknown: {report}: {exc}")
        return 1
    if state.get("confidence_level") != "high":
        print(f"::error::Freshness is {state.get('confidence_level', 'unknown')}; release blocked.")
        for warning in state.get("warnings") or []:
            print(f"::error::{warning}")
        return 1
    print("Freshness gate passed: high confidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(gate())
