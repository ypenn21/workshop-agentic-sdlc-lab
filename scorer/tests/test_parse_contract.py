"""Contract tests for parse_usage().

Verifies the parsing half alone. Every fixture value and assertion traces to a
decision in docs/spec.md.
"""

from __future__ import annotations

from usage import MonthSnapshot, parse_usage

FIXTURE = """account_id,month,seats_active,logins,tickets_open
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


def test_parse_usage_returns_dict_of_month_snapshots():
    parsed = parse_usage(FIXTURE)
    assert isinstance(parsed, dict)  # D-12
    assert set(parsed.keys()) == {"acme", "globex", "hooli", "initech", "umbrella", "vandelay"}  # D-3


def test_parse_usage_parses_exact_fixture_snapshots():
    parsed = parse_usage(FIXTURE)

    # hooli
    assert parsed["hooli"] == [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]  # D-2

    # acme with blank seats parsed as 0
    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-1
    ]

    # globex
    assert parsed["globex"] == [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]  # D-2

    # vandelay
    assert parsed["vandelay"] == [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]  # D-2

    # initech
    assert parsed["initech"] == [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]  # D-2

    # umbrella (single month)
    assert parsed["umbrella"] == [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]  # D-2


def test_parse_usage_coerces_blank_and_whitespace_seats_to_zero():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-03,,5,0\n"
        "beta,2026-03,   ,10,1\n"
    )
    parsed = parse_usage(csv_text)
    assert parsed["acme"][0].seats_active == 0  # D-1
    assert parsed["beta"][0].seats_active == 0  # D-1


def test_parse_usage_sorts_unordered_rows_chronologically():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-03,5,5,0\n"
        "acme,2026-01,10,5,0\n"
        "acme,2026-02,8,5,0\n"
    )
    parsed = parse_usage(csv_text)
    assert [s.month for s in parsed["acme"]] == ["2026-01", "2026-02", "2026-03"]  # D-2


def test_parse_usage_handles_empty_csv():
    assert parse_usage("") == {}  # D-3


def test_parse_usage_handles_header_only_csv():
    csv_text = "account_id,month,seats_active,logins,tickets_open\n"
    assert parse_usage(csv_text) == {}  # D-3


def test_parse_usage_omits_accounts_with_no_months():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "\n"
        "   \n"
    )
    assert parse_usage(csv_text) == {}  # D-3
