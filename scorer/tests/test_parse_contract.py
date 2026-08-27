"""Acceptance tests for the parsing half of the account health scorer."""

from main import load_export
from usage import MonthSnapshot, parse_usage

EXPECTED_ACME = [
    MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
    MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
    MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-2
]

EXPECTED_GLOBEX = [
    MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
    MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
    MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
]

EXPECTED_HOOLI = [
    MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
    MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
]

EXPECTED_INITECH = [
    MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
    MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
]

EXPECTED_UMBRELLA = [
    MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
]

EXPECTED_VANDELAY = [
    MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
    MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
    MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
]


def test_parse_usage_all_fixture_accounts():
    parsed = parse_usage(load_export())
    assert parsed["acme"] == EXPECTED_ACME  # D-2
    assert parsed["globex"] == EXPECTED_GLOBEX
    assert parsed["hooli"] == EXPECTED_HOOLI
    assert parsed["initech"] == EXPECTED_INITECH
    assert parsed["umbrella"] == EXPECTED_UMBRELLA
    assert parsed["vandelay"] == EXPECTED_VANDELAY


def test_parse_usage_blank_seats_becomes_zero_int():
    csv_data = "account_id,month,seats_active,logins,tickets_open\nacme,2026-03,,5,0\n"
    parsed = parse_usage(csv_data)
    assert parsed["acme"][0].seats_active == 0  # D-2
    assert isinstance(parsed["acme"][0].seats_active, int)  # D-2


def test_parse_usage_orders_months_ascending():
    csv_data = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-03,5,5,0\n"
        "acme,2026-01,10,5,0\n"
        "acme,2026-02,8,5,0\n"
    )
    parsed = parse_usage(csv_data)
    assert [m.month for m in parsed["acme"]] == ["2026-01", "2026-02", "2026-03"]
