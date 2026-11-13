"""A successful live-list comparison cannot override a failed source fetch."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gate_freshness import gate


def test_high_confidence_is_releasable(tmp_path):
    report = tmp_path / "freshness.json"
    report.write_text(json.dumps({"confidence_level": "high", "warnings": []}), encoding="utf-8")
    assert gate(report) == 0


def test_source_outage_blocks_even_when_live_list_passes(tmp_path, capsys):
    report = tmp_path / "freshness.json"
    report.write_text(json.dumps({
        "confidence_level": "stale_or_incomplete",
        "live_check_status": "pass",
        "warnings": ["no recent successful official-source fetch"],
    }), encoding="utf-8")
    assert gate(report) == 1
    assert "no recent successful official-source fetch" in capsys.readouterr().out


@pytest.mark.parametrize("contents", ["{}", "[]", "{broken", 'null'])
def test_unknown_or_malformed_report_blocks(tmp_path, contents):
    report = tmp_path / "freshness.json"
    report.write_text(contents, encoding="utf-8")
    assert gate(report) == 1


def test_missing_report_blocks(tmp_path):
    assert gate(tmp_path / "missing.json") == 1
