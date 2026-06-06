# Official Membership Refresh Specification

## Native data model

The refresh system preserves this repository's existing yearly YAML shape:

```yaml
year: 2026
tickers_on_Jan_1:
  - AAPL
changes:
  "2026-04-20":
    difference:
      - TEAM
    union:
      - SNDK
    source_url: https://ir.nasdaq.com/...
    source_title: Sandisk Corporation to Join the Nasdaq-100 Index
    announcement_date: "2026-04-13"
    confidence_score: 0.98
```

`difference` and `union` retain their established meanings. Source fields are optional for
legacy entries and mandatory for newly automated entries. Existing history is not reformatted
or backfilled merely to satisfy the new metadata policy.

## Official sources

Only enabled entries in `metadata/source_registry.yaml` are fetched. URLs must resolve to an
allowlisted Nasdaq domain. Third-party constituent lists are not accepted by this refresh path.
Raw snapshots are retained under `audit/raw_sources/nq100/`.

## Parser and safety model

The parser requires an unambiguous index name, effective date, and add/remove ticker set.
One-sided changes are accepted only when the official announcement explicitly describes them.
Unofficial domains, contradictory same-day events, unknown ticker notation, and low-confidence
parses are written to `audit/manual_review_required.csv`; they never modify YAML.

## Updating YAML

```bash
python scripts/fetch_official_nq100_announcements.py
python scripts/update_membership_yaml.py --index nq100 --dry-run
python scripts/update_membership_yaml.py --index nq100 --apply
```

The default mode may update only the current year. Older effective dates require:

```bash
python scripts/update_membership_yaml.py --index nq100 --apply --correction-mode
```

Correction mode writes `audit/correction_report.md`. It is never used by the scheduled workflow.

## Validation and audit

```bash
python scripts/validate_membership.py --index nq100
python scripts/audit_membership_update.py
python scripts/check_freshness.py --index nq100
python scripts/validate_yaml.py
```

Validation checks continuity, duplicate/blank tickers, logical add/remove state, member-count
bounds, future-date handling, ticker notation, and official domains on new sourced changes.
Legacy source gaps remain explicit warnings.

## GitHub Actions review flow

`.github/workflows/refresh_membership.yml` runs weekly and manually. It fetches, plans, applies
only high-confidence candidates, validates, uploads audit artifacts, creates a review branch,
and opens a pull request. It never pushes directly to `main`.

Review the source links, effective dates, diff report, confidence report, manual-review CSV,
validation report, and freshness report before merging.

## Adding a source or handling parser failure

Add an official Nasdaq URL to `metadata/source_registry.yaml`, keep `official_source: true`, and
choose discovery or seed mode. Parser failures should be handled by adding a narrow parser test
from the saved raw snapshot. Do not loosen confidence checks or manually copy a third-party list.
