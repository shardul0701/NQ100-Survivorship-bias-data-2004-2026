#!/usr/bin/env python3
"""Create an audit CSV of all add/remove events from the yearly YAML files."""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "src" / "nasdaq_100_ticker_history"
OUTPUT = ROOT / "audit" / "membership_change_audit.csv"


def main() -> None:
    rows = []
    for path in sorted(DATA_DIR.glob("n100-ticker-changes-*.yaml")):
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        year = data["year"]
        quality = "upstream_jmccarrell_n100tickers" if year >= 2015 else "research_grade_backfill"
        for effective_date, change in sorted((data.get("changes") or {}).items()):
            change = change or {}
            for ticker in change.get("difference", []) or []:
                rows.append([effective_date, year, ticker, "remove", quality])
            for ticker in change.get("union", []) or []:
                rows.append([effective_date, year, ticker, "add", quality])

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["effective_date", "year_file", "ticker", "action", "quality_level"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
