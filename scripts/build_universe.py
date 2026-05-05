#!/usr/bin/env python3
"""Build point-in-time Nasdaq-100 universe from yearly YAML files.

Example:
    python scripts/build_universe.py --date 2018-06-01
    python scripts/build_universe.py --date 2018-06-01 --output universe.csv
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "nasdaq_100_ticker_history"


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_year(year: int) -> dict:
    path = DATA_DIR / f"n100-ticker-changes-{year}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data.get("year") != year:
        raise ValueError(f"Year mismatch in {path}: expected {year}, got {data.get('year')}")
    return data


def _apply_change(members: set[str], change: dict) -> set[str]:
    members = set(members)
    for ticker in change.get("difference", []) or []:
        members.discard(ticker)
    for ticker in change.get("union", []) or []:
        members.add(ticker)
    return members


def tickers_as_of(as_of: str | date) -> list[str]:
    """Return Nasdaq-100 tickers as of a YYYY-MM-DD date.

    The earliest supported date is 2004-01-01. The latest supported date depends
    on the final YAML file and its latest change entry.
    """
    target = _parse_date(as_of) if isinstance(as_of, str) else as_of
    if target < date(2004, 1, 1):
        raise ValueError("Earliest supported date is 2004-01-01")

    current = _load_year(2004)
    members = set(current["tickers_on_Jan_1"])

    for year in range(2004, target.year + 1):
        data = _load_year(year)
        if year == 2004:
            members = set(data["tickers_on_Jan_1"])
        # If this is a later year, reset from the Jan 1 anchor for safety.
        elif date(year, 1, 1) <= target:
            members = set(data["tickers_on_Jan_1"])

        changes = data.get("changes") or {}
        for effective_date, change in sorted(changes.items()):
            eff = _parse_date(str(effective_date))
            if eff <= target:
                members = _apply_change(members, change or {})

    return sorted(members)


def write_csv(tickers: Iterable[str], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker"])
        for ticker in tickers:
            writer.writerow([ticker])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="As-of date, e.g. 2018-06-01")
    parser.add_argument("--output", help="Optional output CSV path")
    args = parser.parse_args()

    tickers = tickers_as_of(args.date)
    if args.output:
        write_csv(tickers, Path(args.output))
        print(f"Wrote {len(tickers)} tickers to {args.output}")
    else:
        print(f"{len(tickers)} tickers as of {args.date}")
        print("\n".join(tickers))


if __name__ == "__main__":
    main()
