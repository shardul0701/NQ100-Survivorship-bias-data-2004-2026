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

### Events with no press release

Nasdaq announces some membership changes only as index notices, never as an `ir.nasdaq.com`
release: spin-off additions, deletions on a take-private, and deletions on a transfer to
another exchange. The crawler cannot see these. They are entered by hand with `evidence_url`
and `evidence_note` in place of `source_url`, and only once the change is visible in Nasdaq's
official live constituent list (see below):

```yaml
  "2026-09-14":
    difference:
      - KHC
    evidence_url: https://github.com/jmccarrell/n100tickers/pull/94
    evidence_note: deleted on the exchange transfer; KHC is absent from Nasdaq's official live
      NDX constituent list (api.nasdaq.com) as of 2026-10-01
    confidence_score: 0.90
```

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

## Live constituent check

The release crawler only finds changes Nasdaq announces with a press release. Five 2026 events
were missed that way (LITE for CSGP, HONA, EA, KHC, and the Lumentum release that parsed to
nothing), and nothing noticed because the YAML still validated. `scripts/live_check.py`
closes that gap by comparing the YAML with what the index actually holds:

```bash
python scripts/check_live_constituents.py --index nq100          # writes metadata/live_check_state.json
python scripts/check_live_constituents.py --index nq100 --gate   # exit 1 if it needs attention
```

- The official source is Nasdaq's own constituent list (`api.nasdaq.com`, `nasdaq100`). Only it
  can fail the check. The upstream `n100tickers` list is fetched as an advisory cross-check
  and is reported, never gated on.
- The comparison is by name, not count, so a one-for-one swap is caught.
- A name is reported only if it disagrees on every weekday from one day before to two days
  after the source's as-of date. That absorbs a provider publishing a change a day early or
  late without hiding a change that is simply missing.
- An unreachable official source is `source_error`. It fails the gate only once there has been
  no pass for three days, so one bad fetch does not page anyone.
- `check_freshness.py` reads the state: confidence is not `high` unless the last live check
  passed within four days.

## Alerts

Two conditions open a GitHub issue (label `live-check` or `manual-review`), refresh it while
the condition holds, comment only when the condition changes, and close it once the condition
clears. Every write is read back and compared; a body that does not round-trip is an error.

- `check_live_constituents.py --alert`: the live check disagrees with the YAML.
- `alert_manual_review.py --alert`: a fetched release in `audit/manual_review_required.csv`
  is neither recorded in the YAML (by `source_url` or `evidence_url`) nor acknowledged in
  `metadata/manual_review_ack.yaml`. Previously this CSV was read only when a PR opened, so
  a release that produced no YAML change was never seen.

Acknowledge a release only when it is not a membership change, and give the reason.

## Year-file housekeeping

`scripts/rollover_year.py` runs before every refresh and does two things:

- `tickers_as_of` needs a file for the year it is asked about. On the first run of a new year
  it creates that year's file from the previous year's final membership with empty `changes`,
  and does nothing otherwise.
- A change applied before its effective date is marked `pending: true`. Once the date arrives
  the flag is removed; nothing used to remove it, so past changes kept claiming to be future
  ones.

## GitHub Actions review flow

`.github/workflows/refresh_membership.yml` runs every weekday and on demand. It runs the
year-file housekeeping, fetches, plans, applies only high-confidence candidates, validates, runs the
live check and the manual-review alert, checks freshness, and uploads audit artifacts.
Derived metadata and audit reports are committed straight to `main`. A membership change goes
through a pull request, which the run merges itself unless a manual-review release is still
outstanding (neither recorded nor acknowledged); then the PR is labelled `needs-human-review`
and left open. The last steps fail the run red when the live check needs attention or an
alert could not be raised.

Change detection uses `git status --porcelain`, not `git diff --quiet`, because a newly
created year file is untracked and `git diff` does not see it.

Review the source links, effective dates, diff report, confidence report, manual-review CSV,
validation report, and freshness report before merging.

## Adding a source or handling parser failure

Add an official Nasdaq URL to `metadata/source_registry.yaml`, keep `official_source: true`, and
choose discovery or seed mode. Parser failures should be handled by adding a narrow parser test
from the saved raw snapshot. Do not loosen confidence checks or manually copy a third-party list.
