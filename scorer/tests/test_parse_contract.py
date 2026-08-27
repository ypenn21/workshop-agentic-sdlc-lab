"""Contract tests for usage parsing (scorer/usage.py: parse_usage)."""

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


def test_parse_usage_groups_by_account_and_parses_snapshots() -> None:
    parsed = parse_usage(FIXTURE_CSV)

    assert set(parsed.keys()) == {"hooli", "acme", "globex", "vandelay", "initech", "umbrella"}

    assert parsed["hooli"] == [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]

    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-2
    ]

    assert parsed["globex"] == [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]

    assert parsed["vandelay"] == [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]

    assert parsed["initech"] == [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]

    assert parsed["umbrella"] == [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]


def test_parse_usage_coerces_blank_seats_active_to_zero() -> None:
    csv_text = "account_id,month,seats_active,logins,tickets_open\nacme,2026-03,,5,0\n"
    parsed = parse_usage(csv_text)

    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-2
    ]


def test_parse_usage_sorts_snapshots_chronologically_ascending() -> None:
    csv_text = """account_id,month,seats_active,logins,tickets_open
acme,2026-03,5,5,0
acme,2026-01,10,5,0
acme,2026-02,8,5,0
"""
    parsed = parse_usage(csv_text)

    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]


def test_parse_usage_empty_inputs_return_empty_mapping() -> None:
    assert parse_usage("") == {}
    assert parse_usage("account_id,month,seats_active,logins,tickets_open\n") == {}
