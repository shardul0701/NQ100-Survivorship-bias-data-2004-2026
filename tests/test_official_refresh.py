from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from refresh_lib import parse_announcement


def test_nasdaq_replacement_parser():
    html = b"""
    <html><head><meta property="article:published_time" content="2026-04-13"/></head>
    <body>
    Sandisk Corporation (Nasdaq: SNDK) will become a component of the Nasdaq-100
    Index replacing Atlassian Corporation (Nasdaq: TEAM) prior to market open on
    Monday, April 20, 2026.
    </body></html>
    """
    changes = parse_announcement(
        "nq100",
        html,
        "Sandisk Corporation (Nasdaq: SNDK) will become a component of the "
        "Nasdaq-100 Index replacing Atlassian Corporation (Nasdaq: TEAM) "
        "prior to market open on Monday, April 20, 2026.",
        "https://ir.nasdaq.com/news-releases/news-release-details/example",
        "Sandisk Corporation to Join Nasdaq-100",
    )
    assert changes[0].effective_date == "2026-04-20"
    assert changes[0].added_tickers == ["SNDK"]
    assert changes[0].removed_tickers == ["TEAM"]
    assert not changes[0].manual_review_required


def test_unofficial_source_fails_closed():
    changes = parse_announcement(
        "nq100",
        b"<html></html>",
        "AAPL will join the Nasdaq-100.",
        "https://example.com/list",
        "Unofficial list",
    )
    assert changes[0].manual_review_required
    assert changes[0].confidence_score == 0.0
