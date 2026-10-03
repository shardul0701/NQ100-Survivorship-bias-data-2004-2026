from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from refresh_lib import mask_abbreviation_periods, parse_announcement


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


def _nq100(text: str, published: str):
    html = (
        f'<html><head><meta property="article:published_time" content="{published}"/>'
        f"</head><body>{text}</body></html>"
    ).encode()
    return parse_announcement(
        "nq100",
        html,
        text,
        "https://ir.nasdaq.com/news-releases/news-release-details/example",
        "Example",
    )[0]


def test_spaced_exchange_parenthetical_is_parsed():
    # Verbatim from the 2026-10-01 Moderna release. "( Nasdaq : MRNA)" has a
    # space inside the bracket; before the fix the release parsed to nothing.
    change = _nq100(
        "NEW YORK , Oct. 01, 2026 (GLOBE NEWSWIRE) -- Nasdaq ( Nasdaq : NDAQ) today "
        "announced that Moderna, Inc. ( Nasdaq : MRNA) will become a component of the "
        "Nasdaq -100 Index ® (NDX ® ) replacing Warner Bros. Discovery, Inc. "
        "( Nasdaq : WBD) prior to market open on Friday, October 9, 2026 . For "
        "additional information, please go to https://indexes.nasdaq.com/",
        "2026-10-01",
    )
    assert change.effective_date == "2026-10-09"
    assert change.added_tickers == ["MRNA"]
    assert change.removed_tickers == ["WBD"]
    assert not change.manual_review_required


def test_removed_company_with_inc_suffix_is_parsed():
    # Verbatim from the 2026-05-08 Lumentum release. The [^.] sentence patterns
    # stopped at "CoStar Group, Inc." and never reached CSGP, so LITE was parsed
    # as an addition with no removal and sent to manual review.
    change = _nq100(
        "NEW YORK , May 08, 2026 (GLOBE NEWSWIRE) -- Nasdaq (Nasdaq: NDAQ) today "
        "announced that Lumentum Holdings Inc. (Nasdaq: LITE) will become a component "
        "of the Nasdaq-100 Index ® replacing CoStar Group, Inc. (Nasdaq: CSGP) prior "
        "to market open on Monday, May 18, 2026 . For additional information, please "
        "go to https://indexes.nasdaq.com/",
        "2026-05-08",
    )
    assert change.effective_date == "2026-05-18"
    assert change.added_tickers == ["LITE"]
    assert change.removed_tickers == ["CSGP"]
    assert change.confidence_score == 0.98
    assert not change.manual_review_required


def test_replacement_in_a_separate_sentence_still_parses():
    # Walmart 2026-01-09: the add and the replace are two sentences. Masking
    # "Inc." must not merge them in a way that loses either half.
    change = _nq100(
        "Nasdaq (Nasdaq: NDAQ) today announced that Walmart Inc. (Nasdaq: WMT), will "
        "become a component of the Nasdaq-100 Index ® (NDX ® ) prior to market open on "
        "Tuesday, January 20, 2026 - the first trading day following the third Friday "
        "of the month. Walmart Inc. will replace AstraZeneca PLC (Nasdaq: AZN) in the "
        "Nasdaq-100 Index ® .",
        "2026-01-09",
    )
    assert change.added_tickers == ["WMT"]
    assert change.removed_tickers == ["AZN"]
    assert not change.manual_review_required


def test_fast_entry_addition_without_removal_is_not_flagged():
    change = _nq100(
        "Nasdaq (Nasdaq: NDAQ) today announced that Space Exploration Technologies "
        "Corporation (Nasdaq: SPCX) will become a component of the Nasdaq-100 Index® "
        "prior to market open on Tuesday, July 7, 2026 . For additional information, "
        "please go to https://indexes.nasdaq.com/ About Nasdaq Global Indexes The "
        "index is reviewed and constituents may be removed.",
        "2026-06-26",
    )
    assert change.added_tickers == ["SPCX"]
    assert change.removed_tickers == []
    assert change.confidence_score == 0.92
    assert not change.manual_review_required


def test_abbreviation_mask_leaves_sentence_ends_and_tickers_alone():
    masked = mask_abbreviation_periods(
        "Warner Bros. Discovery, Inc. (NYSE: BRK.B) Foo N.V. joined. Next sentence."
    )
    assert "Bros." not in masked and "Inc." not in masked and "N.V." not in masked
    assert "BRK.B" in masked
    assert masked.endswith("joined. Next sentence.")


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
