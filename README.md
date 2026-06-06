# Nasdaq-100 Point-in-Time Universe Files, 2004-2026

This repository provides yearly YAML files for a point-in-time Nasdaq-100 universe used in backtesting.

The purpose is to avoid survivorship bias by letting a backtest ask:

> Which tickers were in the Nasdaq-100 on the signal date?

Instead of using today's Nasdaq-100 constituents for every historical date.

## Folder structure

```text
src/nasdaq_100_ticker_history/
  n100-ticker-changes-2004.yaml
  n100-ticker-changes-2005.yaml
  ...
  n100-ticker-changes-2026.yaml

scripts/
  build_universe.py
  validate_yaml.py
  audit_membership.py

source_notes.json
licenses/
  jmccarrell_n100tickers_LICENSE
```

## Data quality levels

### 2015-2026

The 2015-2026 YAML files are copied from [`jmccarrell/n100tickers`](https://github.com/jmccarrell/n100tickers), which describes itself as an API for current and limited historical Nasdaq-100 ticker membership. The upstream README says accurate coverage is provided from Jan. 1, 2015 through at least Apr. 29, 2026.

### 2004-2014

The 2004-2014 YAML files are reconstructed historical backfill files. They were built by rolling membership backward from the upstream Jan. 1, 2015 anchor and applying public historical add/remove events.

Treat this section as **research-grade**, not paid-vendor-grade. Before using it for serious strategy claims, audit each event against primary Nasdaq announcements, SEC/company releases, or a licensed constituent-history database.

## YAML format

Each file follows the same general structure as the upstream repo:

```yaml
---
year: 2015
tickers_on_Jan_1:
  - AAPL
  - MSFT
changes:
  '2015-03-23':
    difference:
      - EQIX
    union:
      - WBA
```

- `tickers_on_Jan_1` is the point-in-time ticker list on January 1 of that year.
- `changes` are effective-date changes during that year.
- `difference` means tickers removed from the universe.
- `union` means tickers added to the universe.

## How to validate the files

Install dependencies:

```bash
pip install -r requirements.txt
```

Run validation:

```bash
python scripts/validate_yaml.py
```

This checks:

- each file parses as YAML
- required fields exist
- ticker lists have no duplicates
- applying year `Y` changes produces year `Y+1` Jan. 1 membership

## Official-source refresh

The repository includes a fail-closed weekly refresh that checks official Nasdaq sources,
retains raw snapshots and audit reports, and opens a pull request for manual review:

```bash
python scripts/fetch_official_nq100_announcements.py
python scripts/update_membership_yaml.py --index nq100 --dry-run
python scripts/validate_membership.py --index nq100
python scripts/audit_membership_update.py
python scripts/check_freshness.py --index nq100
```

See `MERGE_OR_REFRESH_SPEC.md` for the source registry, confidence rules, correction mode,
validation behavior, and pull-request workflow.

## How to get the universe for a date

Example:

```bash
python scripts/build_universe.py --date 2018-06-01
```

Save to CSV:

```bash
python scripts/build_universe.py --date 2018-06-01 --output universe_2018_06_01.csv
```

Use in Python:

```python
from scripts.build_universe import tickers_as_of

universe = tickers_as_of("2018-06-01")
```

## Important ticker-normalization notes

The open-source upstream files use modern/current ticker conventions in some places. Examples:

- `BKNG` is used for historical Booking/Priceline exposure, even though the ticker was historically `PCLN` before the rename.
- `MNST/HANS` requires care around the Hansen Natural to Monster Beverage rename.
- `KFT/MDLZ/KRFT` needs care around the Kraft/Mondelez split and ticker changes.

See `source_notes.json` for more details.

## Suggested usage in a backtest

Do this:

```python
universe = tickers_as_of(signal_date)
```

Avoid this:

```python
universe = current_nasdaq_100
```

The second version has survivorship bias because it lets the strategy trade companies that may not have been in the index at that historical time.

## Attribution

2015-2026 canonical files are sourced from [`jmccarrell/n100tickers`](https://github.com/jmccarrell/n100tickers), which is MIT licensed. The upstream license is included under `licenses/jmccarrell_n100tickers_LICENSE`.

2004-2014 backfilled files are reconstructed and should be independently verified.
