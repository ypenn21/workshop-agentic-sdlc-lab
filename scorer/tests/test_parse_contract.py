"""Contract tests for parse_usage."""

from __future__ import annotations

from usage import MonthSnapshot, parse_usage

FIXTURE_CSV = """account_id,month,seats_active,logins,tickets_open
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


def test_parse_usage_single_row():
    csv_text = """account_id,month,seats_active,logins,tickets_open
acme,2026-01,10,5,1
"""
    expected = {
        "acme": [
            MonthSnapshot(
                account_id="acme",
                month="2026-01",
                seats_active=10,
                logins=5,
                tickets_open=1,
            )
        ]
    }
    assert parse_usage(csv_text) == expected


def test_parse_usage_blank_seats_active_parsed_as_zero():
    csv_text = """account_id,month,seats_active,logins,tickets_open
acme,2026-03,,5,0
"""
    snapshots = parse_usage(csv_text)
    assert snapshots["acme"][0].seats_active == 0  # D-2
    assert isinstance(snapshots["acme"][0].seats_active, int)  # D-2
    assert snapshots == {
        "acme": [
            MonthSnapshot(
                account_id="acme",
                month="2026-03",
                seats_active=0,  # D-2
                logins=5,
                tickets_open=0,
            )
        ]
    }


def test_parse_usage_sorts_months_in_ascending_order():
    csv_text = """account_id,month,seats_active,logins,tickets_open
acme,2026-03,5,5,0
acme,2026-01,10,5,0
acme,2026-02,8,5,0
"""
    assert parse_usage(csv_text) == {
        "acme": [
            MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-03", seats_active=5, logins=5, tickets_open=0),
        ]
    }


def test_parse_usage_groups_multiple_accounts():
    csv_text = """account_id,month,seats_active,logins,tickets_open
hooli,2026-02,12,45,1
acme,2026-01,10,5,0
hooli,2026-01,12,40,0
"""
    assert parse_usage(csv_text) == {
        "hooli": [
            MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
            MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
        ],
        "acme": [
            MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        ],
    }


def test_parse_usage_omits_accounts_with_no_months_or_empty_input():
    csv_text = """account_id,month,seats_active,logins,tickets_open
"""
    assert parse_usage(csv_text) == {}


def test_parse_usage_full_fixture():
    expected = {
        "hooli": [
            MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
            MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
        ],
        "acme": [
            MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-2
        ],
        "globex": [
            MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
            MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
        ],
        "vandelay": [
            MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
            MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
        ],
        "initech": [
            MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
            MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
        ],
        "umbrella": [
            MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
        ],
    }
    assert parse_usage(FIXTURE_CSV) == expected
