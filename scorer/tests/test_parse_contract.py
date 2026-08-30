"""Contract tests for usage export parser (scorer/usage.py:parse_usage).

Verifies the parsing half alone: parse_usage(csv_text) produces the exact
dictionary of account IDs mapped to chronologically ordered MonthSnapshot lists.
"""

from __future__ import annotations

from usage import MonthSnapshot, parse_usage


CANONICAL_CSV = """account_id,month,seats_active,logins,tickets_open
hooli,2026-01,12,40,0
hooli,2026-02,12,45,1
acme,2026-01,10,5,0
acme,2026-02,8,5,0
acme,2026-03,,5,0
globex,2026-01,4,5,0
globex,2026-02,10,5,0
globex,2026-03,6,5,0
vandelay,2026-01,10,5,0
vandelay,2026-02,6,5,0
vandelay,2026-03,5,5,0
initech,2026-01,6,4,0
initech,2026-02,6,2,3
umbrella,2026-02,3,10,0
"""


def test_parse_usage_canonical_fixture() -> None:
    """parse_usage parses all fixture accounts into exact MonthSnapshot instances."""
    parsed = parse_usage(CANONICAL_CSV)

    expected = {
        "acme": [
            MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-1
        ],
        "globex": [
            MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
            MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
        ],
        "hooli": [
            MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
            MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
        ],
        "initech": [
            MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
            MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
        ],
        "umbrella": [
            MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
        ],
        "vandelay": [
            MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
            MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
        ],
    }

    assert parsed == expected  # D-1, D-2, D-10


def test_parse_usage_chronological_sorting() -> None:
    """parse_usage returns MonthSnapshot list sorted ascending by month."""
    unordered_csv = """account_id,month,seats_active,logins,tickets_open
acme,2026-03,5,10,0
acme,2026-01,10,10,0
acme,2026-02,8,10,0
"""
    parsed = parse_usage(unordered_csv)

    assert [m.month for m in parsed["acme"]] == ["2026-01", "2026-02", "2026-03"]  # D-2


def test_parse_usage_blank_and_whitespace_seats_coercion() -> None:
    """parse_usage coerces empty or whitespace-only seats_active to integer 0."""
    csv_text = """account_id,month,seats_active,logins,tickets_open
acme,2026-01,,10,0
acme,2026-02,   ,12,1
"""
    parsed = parse_usage(csv_text)

    assert parsed["acme"][0].seats_active == 0  # D-1
    assert parsed["acme"][1].seats_active == 0  # D-1


def test_parse_usage_empty_lines_and_account_omission() -> None:
    """parse_usage ignores empty and whitespace-only lines and omits empty accounts."""
    csv_text = """account_id,month,seats_active,logins,tickets_open

hooli,2026-01,12,40,0

   
hooli,2026-02,12,45,1

"""
    parsed = parse_usage(csv_text)

    assert set(parsed.keys()) == {"hooli"}  # D-3
    assert len(parsed["hooli"]) == 2  # D-3


def test_parse_usage_header_column_reordering() -> None:
    """parse_usage maps columns by header name regardless of column position."""
    reordered_csv = """month,tickets_open,account_id,seats_active,logins
2026-01,0,hooli,12,40
"""
    parsed = parse_usage(reordered_csv)

    expected = [
        MonthSnapshot(
            account_id="hooli",
            month="2026-01",
            seats_active=12,
            logins=40,
            tickets_open=0,
        )
    ]
    assert parsed["hooli"] == expected  # D-10
