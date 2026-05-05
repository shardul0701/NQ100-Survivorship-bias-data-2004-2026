#!/usr/bin/env python3
"""Validate Nasdaq-100 yearly YAML files."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "nasdaq_100_ticker_history"


def parse_date(value: str):
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return data


def apply_changes(members: set[str], changes: dict) -> set[str]:
    members = set(members)
    for effective_date, change in sorted((changes or {}).items(), key=lambda x: parse_date(x[0])):
        change = change or {}
        for ticker in change.get("difference", []) or []:
            members.discard(ticker)
        for ticker in change.get("union", []) or []:
            members.add(ticker)
    return members


def main() -> int:
    errors: list[str] = []
    loaded: dict[int, dict] = {}

    for path in sorted(DATA_DIR.glob("n100-ticker-changes-*.yaml")):
        try:
            data = load_yaml(path)
            year = data.get("year")
            if not isinstance(year, int):
                errors.append(f"{path.name}: missing/integer year")
                continue
            if str(year) not in path.name:
                errors.append(f"{path.name}: year field does not match filename")
            tickers = data.get("tickers_on_Jan_1")
            if not isinstance(tickers, list) or not tickers:
                errors.append(f"{path.name}: tickers_on_Jan_1 must be a non-empty list")
            elif len(tickers) != len(set(tickers)):
                errors.append(f"{path.name}: duplicate tickers_on_Jan_1")
            changes = data.get("changes") or {}
            if not isinstance(changes, dict):
                errors.append(f"{path.name}: changes must be a mapping")
            for eff, change in changes.items():
                parse_date(eff)
                if change is None:
                    continue
                if not isinstance(change, dict):
                    errors.append(f"{path.name}: change at {eff} must be mapping")
                    continue
                for key in ("difference", "union"):
                    if key in change and change[key] is not None and not isinstance(change[key], list):
                        errors.append(f"{path.name}: {eff}.{key} must be a list or empty/null")
            loaded[year] = data
        except Exception as e:
            errors.append(f"{path.name}: {e}")

    years = sorted(loaded)
    for y1, y2 in zip(years, years[1:]):
        if y2 != y1 + 1:
            errors.append(f"Missing year between {y1} and {y2}")

    # Year-to-year continuity: Jan 1 year N + changes during N should equal Jan 1 year N+1.
    for year in years[:-1]:
        end_members = apply_changes(set(loaded[year]["tickers_on_Jan_1"]), loaded[year].get("changes") or {})
        next_members = set(loaded[year + 1]["tickers_on_Jan_1"])
        if end_members != next_members:
            missing = sorted(end_members - next_members)
            extra = sorted(next_members - end_members)
            errors.append(
                f"Continuity mismatch {year}->{year + 1}: "
                f"in end {year} not next Jan1={missing}; "
                f"in next Jan1 not end {year}={extra}"
            )

    if errors:
        print("VALIDATION FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"VALIDATION PASSED: {len(years)} files, {years[0]}-{years[-1]}")
    for year in years:
        print(f"{year}: {len(loaded[year]['tickers_on_Jan_1'])} Jan 1 tickers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
