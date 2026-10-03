#!/usr/bin/env python3
"""Create the current year's membership file if it does not exist yet (see refresh_lib.rollover_year)."""

from __future__ import annotations

import argparse

from refresh_lib import rollover_year


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, choices=("nq100", "sp500"))
    args = parser.parse_args()
    path = rollover_year(args.index)
    print(f"created {path.name}" if path else "current year file already exists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
