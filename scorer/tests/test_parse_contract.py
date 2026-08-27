"""Contract tests for parse_usage.

Verifies the parsing half of the system in isolation.
"""

from __future__ import annotations

from pathlib import Path

from usage import MonthSnapshot, parse_usage

FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "usage.csv"


def test_parse_usage_on_fixture():
    csv_text = FIXTURE_PATH.read_text(encoding="utf-8")
    parsed = parse_usage(csv_text)

    assert set(parsed.keys()) == {
        "hooli",
        "acme",
        "globex",
        "vandelay",
        "initech",
        "umbrella",
    }

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


def test_parse_blank_seats_active_as_zero():
    csv_text = "account_id,month,seats_active,logins,tickets_open\nacme,2026-03,,5,0\n"
    parsed = parse_usage(csv_text)

    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-2
    ]
    assert isinstance(parsed["acme"][0].seats_active, int)  # D-2


def test_parse_usage_orders_months_ascending():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "globex,2026-03,6,5,0\n"
        "globex,2026-01,4,5,0\n"
        "globex,2026-02,10,5,0\n"
    )
    parsed = parse_usage(csv_text)

    assert [s.month for s in parsed["globex"]] == ["2026-01", "2026-02", "2026-03"]


def test_parse_usage_empty_export():
    csv_text = "account_id,month,seats_active,logins,tickets_open\n"
    parsed = parse_usage(csv_text)

    assert parsed == {}
