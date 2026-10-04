"""Network-free tests for the live-constituent check, the issue alerts and year rollover."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import github_alerts as G
import live_check as L
import refresh_lib as R

SNAPSHOT = ROOT / "tests" / "fixtures" / "nq100_official_2026-10-01.txt"
YAML_2026 = ROOT / "src" / "nasdaq_100_ticker_history" / "n100-ticker-changes-2026.yaml"
# The five events the crawler never recorded (see live_check.py).
BACKFILLED = ("2026-05-18", "2026-06-29", "2026-08-04", "2026-09-14")


def official_snapshot() -> set[str]:
    lines = SNAPSHOT.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def yaml_2026() -> dict:
    return yaml.safe_load(YAML_2026.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The check against real data
# --------------------------------------------------------------------------- #
def test_yaml_matches_the_official_list_captured_2026_10_01():
    data = yaml_2026()
    missing, extra, _ = L.persistent_diff(
        lambda d: L.members_from_yaml(data, d), official_snapshot(), date(2026, 10, 1), {}
    )
    assert (missing, extra) == ([], [])


def test_the_pre_backfill_yaml_is_caught():
    # Exactly what was on main before this change: the check names all five.
    data = yaml_2026()
    for key in BACKFILLED:
        del data["changes"][key]
    missing, extra, _ = L.persistent_diff(
        lambda d: L.members_from_yaml(data, d), official_snapshot(), date(2026, 10, 1), {}
    )
    assert missing == ["HONA", "LITE"]
    assert extra == ["CSGP", "EA", "KHC"]


def test_a_swap_that_keeps_the_count_is_still_caught():
    data = {"tickers_on_Jan_1": ["AAA", "BBB", "CCC"], "changes": {}}
    missing, extra, _ = L.persistent_diff(
        lambda d: L.members_from_yaml(data, d), {"AAA", "BBB", "DDD"}, date(2026, 10, 1), {}
    )
    assert (missing, extra) == (["DDD"], ["CCC"])


def test_a_change_published_a_day_early_is_not_reported():
    # YAML: CCC -> DDD effective Friday 10-02. Provider already shows DDD on 10-01.
    data = {
        "tickers_on_Jan_1": ["AAA", "CCC"],
        "changes": {"2026-10-02": {"difference": ["CCC"], "union": ["DDD"]}},
    }
    missing, extra, window = L.persistent_diff(
        lambda d: L.members_from_yaml(data, d), {"AAA", "DDD"}, date(2026, 10, 1), {}
    )
    assert (missing, extra) == ([], [])
    assert window == ["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-05"]


def test_a_change_missing_for_the_whole_window_is_reported():
    data = {
        "tickers_on_Jan_1": ["AAA", "CCC"],
        "changes": {"2026-10-09": {"difference": ["CCC"], "union": ["DDD"]}},
    }
    missing, extra, _ = L.persistent_diff(
        lambda d: L.members_from_yaml(data, d), {"AAA", "DDD"}, date(2026, 10, 1), {}
    )
    assert (missing, extra) == (["DDD"], ["CCC"])


def test_share_class_punctuation_is_not_a_mismatch_but_share_classes_are_distinct():
    assert L.compare_key("BRK.B", {}) == L.compare_key("BRK-B", {}) == L.compare_key("BRK/B", {})
    assert L.compare_key("GOOG", {}) != L.compare_key("GOOGL", {})


def test_weekday_window_skips_weekends():
    assert [d.isoformat() for d in L.weekday_window(date(2026, 10, 5))] == [
        "2026-10-02",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    ]


def test_needs_attention():
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=5)).isoformat()
    assert L.needs_attention({"status": "mismatch", "last_pass_at": recent}, now)
    assert not L.needs_attention({"status": "pass"}, now)
    assert not L.needs_attention({"status": "source_error", "last_pass_at": recent}, now)
    assert L.needs_attention({"status": "source_error", "last_pass_at": old}, now)
    assert L.needs_attention({"status": "source_error", "last_pass_at": None}, now)


def test_issue_body_names_the_tickers():
    state = {
        "index_name": "Nasdaq-100",
        "status": "mismatch",
        "checked_at": "2026-10-03T00:00:00+00:00",
        "pit_count_today": 101,
        "sources": [
            {
                "name": "nasdaq_api", "url": "u", "role": "official", "reachable": True,
                "as_of": "2026-10-01", "count": 101, "error": None,
                "missing_from_pit": ["LITE"], "extra_in_pit": ["CSGP"],
                "window": ["2026-09-30", "2026-10-05"],
            }
        ],
    }
    title, body = L.render_issue(state)
    assert "disagrees" in title
    assert "LITE" in body and "CSGP" in body


# --------------------------------------------------------------------------- #
# Year rollover
# --------------------------------------------------------------------------- #
def test_rollover_seeds_the_new_year_from_last_years_final_membership(tmp_path, monkeypatch):
    profiles = {k: dict(v) for k, v in R.INDEX_PROFILES.items()}
    profiles["nq100"]["data_dir"] = tmp_path
    monkeypatch.setattr(R, "INDEX_PROFILES", profiles)
    (tmp_path / "n100-ticker-changes-2026.yaml").write_text(
        YAML_2026.read_text(encoding="utf-8"), encoding="utf-8"
    )
    path = R.rollover_year("nq100", date(2027, 1, 1))
    new = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert new["year"] == 2027 and new["changes"] == {}
    assert set(new["tickers_on_Jan_1"]) == R.final_membership(yaml_2026())
    assert "MRNA" in new["tickers_on_Jan_1"] and "WBD" not in new["tickers_on_Jan_1"]
    assert R.rollover_year("nq100", date(2027, 1, 2)) is None


def test_pending_is_cleared_once_the_effective_date_arrives(tmp_path, monkeypatch):
    profiles = {k: dict(v) for k, v in R.INDEX_PROFILES.items()}
    profiles["nq100"]["data_dir"] = tmp_path
    monkeypatch.setattr(R, "INDEX_PROFILES", profiles)
    path = tmp_path / "n100-ticker-changes-2026.yaml"
    path.write_text(
        "year: 2026\ntickers_on_Jan_1: [AAA, BBB]\nchanges:\n"
        '  "2026-09-21":\n    difference: [BBB]\n    union: [CCC]\n    pending: true\n'
        '  "2026-10-09":\n    difference: [AAA]\n    union: [DDD]\n    pending: true\n',
        encoding="utf-8",
    )
    assert R.expire_elapsed_pending("nq100", date(2026, 10, 3)) == ["2026-09-21"]
    changes = yaml.safe_load(path.read_text(encoding="utf-8"))["changes"]
    assert "pending" not in changes["2026-09-21"]
    assert changes["2026-09-21"]["union"] == ["CCC"]
    assert changes["2026-10-09"]["pending"] is True
    assert R.expire_elapsed_pending("nq100", date(2026, 10, 3)) == []


# --------------------------------------------------------------------------- #
# GitHub alerts, against an in-memory fake of the issues API
# --------------------------------------------------------------------------- #
class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data = status, data
        self.content = b"x" if data is not None else b""
        self.text = str(data)

    def json(self):
        return self._data


class FakeGitHub:
    def __init__(self):
        self.headers, self.issues, self.comments, self.labels = {}, {}, {}, set()

    def get(self, url, timeout=None):
        name = url.rsplit("/labels/", 1)[-1]
        return FakeResponse(200 if name in self.labels else 404, {})

    def request(self, method, url, timeout=None, json=None, params=None):
        path = url.split("/repos/o/r", 1)[1]
        if method == "POST" and path == "/labels":
            self.labels.add(json["name"])
            return FakeResponse(201, json)
        if method == "GET" and path == "/issues":
            hits = [i for i in self.issues.values() if i["state"] == "open"]
            return FakeResponse(200, hits)
        if method == "POST" and path == "/issues":
            n = len(self.issues) + 1
            self.issues[n] = {"number": n, "state": "open", **json}
            return FakeResponse(201, self.issues[n])
        if path.startswith("/issues/comments/"):
            return FakeResponse(200, self.comments[int(path.rsplit("/", 1)[1])])
        if path.endswith("/comments"):
            cid = len(self.comments) + 1
            self.comments[cid] = {"id": cid, "issue": int(path.split("/")[2]), **json}
            return FakeResponse(201, self.comments[cid])
        number = int(path.split("/")[2])
        if method == "PATCH":
            self.issues[number].update(json)
        return FakeResponse(200, self.issues[number])


def test_alert_lifecycle_opens_once_comments_on_change_and_closes():
    fake = FakeGitHub()
    gh = G.GitHub("o/r", "token", session=fake)
    assert G.upsert_alert(gh, "live-check:nq100", "live-check", "t", "b1", ["LITE"]) == "opened #1"
    assert "live-check" in fake.labels
    # Same condition next day: body refreshed, no comment, no second issue.
    assert G.upsert_alert(gh, "live-check:nq100", "live-check", "t", "b1", ["LITE"]).startswith("refreshed #1")
    assert len(fake.issues) == 1 and not fake.comments
    # Condition changes: one comment.
    assert "commented" in G.upsert_alert(gh, "live-check:nq100", "live-check", "t", "b2", ["LITE", "HONA"])
    assert len(fake.comments) == 1
    assert G.resolve_alert(gh, "live-check:nq100", "live-check", "fixed") == "closed #1"
    assert fake.issues[1]["state"] == "closed"
    assert G.resolve_alert(gh, "live-check:nq100", "live-check", "fixed") == "no open alert"


def test_alerts_are_keyed_so_two_alerts_do_not_share_an_issue():
    fake = FakeGitHub()
    gh = G.GitHub("o/r", "token", session=fake)
    G.upsert_alert(gh, "live-check:nq100", "live-check", "t", "b", [1])
    G.upsert_alert(gh, "manual-review:nq100", "manual-review", "t", "b", [2])
    assert len(fake.issues) == 2


def test_a_write_that_does_not_round_trip_is_an_error():
    class Mangling(FakeGitHub):
        def request(self, method, url, timeout=None, json=None, params=None):
            if method == "POST" and url.endswith("/issues"):
                json = {**json, "body": "@C:/tmp/body.md"}
            return super().request(method, url, timeout=timeout, json=json, params=params)

    gh = G.GitHub("o/r", "token", session=Mangling())
    with pytest.raises(RuntimeError, match="round-trip"):
        G.upsert_alert(gh, "live-check:nq100", "live-check", "t", "b", [1])


# --------------------------------------------------------------------------- #
# Historical candidates
# --------------------------------------------------------------------------- #
def _plan_with(tmp_path, monkeypatch, added, removed):
    profiles = {k: dict(v) for k, v in R.INDEX_PROFILES.items()}
    profiles["nq100"]["data_dir"] = tmp_path
    profiles["nq100"]["candidate_file"] = tmp_path / "candidates.csv"
    monkeypatch.setattr(R, "INDEX_PROFILES", profiles)
    (tmp_path / "n100-ticker-changes-2025.yaml").write_text(
        'year: 2025\ntickers_on_Jan_1: [AAA, BBB]\nchanges:\n  "2025-12-22":\n'
        "    difference: [BBB]\n    union: [CCC]\n",
        encoding="utf-8",
    )
    R.write_csv(
        profiles["nq100"]["candidate_file"],
        [{
            "index_name": "Nasdaq-100", "announcement_date": "2025-12-12",
            "effective_date": "2025-12-22", "added_tickers": added, "removed_tickers": removed,
            "source_url": "https://ir.nasdaq.com/x", "source_title": "Annual",
            "raw_file_path": "", "confidence_score": "0.98", "parser_notes": "",
            "manual_review_required": "false",
        }],
        R.CANDIDATE_FIELDS,
    )
    return R.apply_candidates("nq100", apply=False)


def test_a_last_year_change_already_recorded_is_not_sent_to_review(tmp_path, monkeypatch):
    [action] = _plan_with(tmp_path, monkeypatch, "CCC", "BBB")
    assert action["status"] == "already_present"


def test_a_last_year_change_that_differs_still_needs_correction_mode(tmp_path, monkeypatch):
    [action] = _plan_with(tmp_path, monkeypatch, "DDD", "BBB")
    assert action["status"] == "manual_review"
    assert action["reason"] == "historical correction flag required"


# --------------------------------------------------------------------------- #
# Manual-review alert: what counts as outstanding (also gates the auto-merge)
# --------------------------------------------------------------------------- #
def test_recorded_and_acknowledged_releases_are_not_outstanding(tmp_path, monkeypatch):
    import alert_manual_review as A

    profiles = {k: dict(v) for k, v in R.INDEX_PROFILES.items()}
    profiles["nq100"]["data_dir"] = tmp_path
    monkeypatch.setattr(R, "INDEX_PROFILES", profiles)
    (tmp_path / "n100-ticker-changes-2026.yaml").write_text(
        "year: 2026\ntickers_on_Jan_1: [AAA]\nchanges:\n"
        '  "2026-05-18":\n    union: [BBB]\n    source_url: https://ir.nasdaq.com/recorded\n'
        '  "2026-06-29":\n    union: [CCC]\n    evidence_url: https://example.org/evidence\n',
        encoding="utf-8",
    )
    ack = tmp_path / "ack.yaml"
    ack.write_text("acknowledged:\n  - source_url: https://ir.nasdaq.com/statement\n", encoding="utf-8")
    monkeypatch.setattr(A, "ACK_FILE", ack)
    monkeypatch.setattr(A, "AUDIT_DIR", tmp_path)
    urls = [
        "https://ir.nasdaq.com/recorded",
        "https://example.org/evidence",
        "https://ir.nasdaq.com/statement",
        "https://ir.nasdaq.com/new",
        "https://ir.nasdaq.com/new",
    ]
    R.write_csv(
        tmp_path / "manual_review_required.csv",
        [{"index_name": "Nasdaq-100", "source_url": u} for u in urls],
        R.MANUAL_FIELDS,
    )
    assert [r["source_url"] for r in A.outstanding("nq100")] == ["https://ir.nasdaq.com/new"]


def test_written_tickers_survive_a_yaml_1_1_reader(tmp_path, monkeypatch):
    # ON Semiconductor: PyYAML reads a bare ON as True.
    profiles = {k: dict(v) for k, v in R.INDEX_PROFILES.items()}
    profiles["nq100"]["data_dir"] = tmp_path
    monkeypatch.setattr(R, "INDEX_PROFILES", profiles)
    (tmp_path / "n100-ticker-changes-2026.yaml").write_text(
        'year: 2026\ntickers_on_Jan_1: [AAPL, "ON", "NO"]\nchanges: {}\n', encoding="utf-8"
    )
    path = R.rollover_year("nq100", date(2027, 1, 1))
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["tickers_on_Jan_1"] == ["AAPL", "NO", "ON"]


# --------------------------------------------------------------------------- #
# Same-day entries: a rename recorded alongside an announced change
# --------------------------------------------------------------------------- #
def _plan_same_day(tmp_path, monkeypatch, entry_yaml):
    year = date.today().year
    profiles = {k: dict(v) for k, v in R.INDEX_PROFILES.items()}
    profiles["nq100"]["data_dir"] = tmp_path
    profiles["nq100"]["candidate_file"] = tmp_path / "candidates.csv"
    monkeypatch.setattr(R, "INDEX_PROFILES", profiles)
    (tmp_path / f"n100-ticker-changes-{year}.yaml").write_text(
        f'year: {year}\ntickers_on_Jan_1: [AAA, BBB, EQR]\nchanges:\n  "{year}-01-02":\n' + entry_yaml,
        encoding="utf-8",
    )
    R.write_csv(
        profiles["nq100"]["candidate_file"],
        [{
            "index_name": "Nasdaq-100", "announcement_date": f"{year}-01-01",
            "effective_date": f"{year}-01-02", "added_tickers": "RDDT", "removed_tickers": "AAA",
            "source_url": "https://ir.nasdaq.com/x", "source_title": "t",
            "raw_file_path": "", "confidence_score": "0.98", "parser_notes": "",
            "manual_review_required": "false",
        }],
        R.CANDIDATE_FIELDS,
    )
    [action] = R.apply_candidates("nq100", apply=False)
    return action


def test_a_same_day_entry_that_matches_exactly_is_already_present(tmp_path, monkeypatch):
    action = _plan_same_day(
        tmp_path, monkeypatch, "    difference: [AAA]\n    union: [RDDT]\n    source_url: https://ir.nasdaq.com/x\n"
    )
    assert action["status"] == "already_present"


def test_a_same_day_rename_backed_by_evidence_does_not_contradict_the_release(tmp_path, monkeypatch):
    action = _plan_same_day(
        tmp_path,
        monkeypatch,
        "    difference: [AAA, EQR]\n    union: [RDDT, VMRK]\n    source_url: https://ir.nasdaq.com/x\n"
        "    evidence_url: https://www.sec.gov/x\n    evidence_note: EQR renamed VMRK the same day\n",
    )
    assert action["status"] == "already_present"


def test_unexplained_extra_tickers_on_the_same_day_still_contradict(tmp_path, monkeypatch):
    action = _plan_same_day(
        tmp_path, monkeypatch, "    difference: [AAA, EQR]\n    union: [RDDT, VMRK]\n    source_url: https://ir.nasdaq.com/x\n"
    )
    assert action["status"] == "manual_review"
    assert action["reason"] == "contradicts existing same-day change"
