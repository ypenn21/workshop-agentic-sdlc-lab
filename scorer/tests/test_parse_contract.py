from __future__ import annotations

from main import load_export
from usage import MonthSnapshot, parse_usage


def test_parse_usage_on_fixture():
    parsed = parse_usage(load_export())

    assert parsed == {
        "acme": [
            MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D03
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


def test_parse_blank_seats_active_parsed_as_zero():
    csv_text = "account_id,month,seats_active,logins,tickets_open\nacme,2026-03,,5,0\n"
    parsed = parse_usage(csv_text)
    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0)  # D03
    ]


def test_parse_orders_months_in_ascending_order():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-03,8,5,0\n"
        "acme,2026-01,10,5,0\n"
        "acme,2026-02,9,5,0\n"
    )
    parsed = parse_usage(csv_text)
    assert parsed["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=9, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=8, logins=5, tickets_open=0),
    ]


def test_parse_empty_csv_returns_empty_dict():
    csv_text = "account_id,month,seats_active,logins,tickets_open\n"
    assert parse_usage(csv_text) == {}
