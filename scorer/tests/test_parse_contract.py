"""Contract tests for parse_usage().

Tests the parsing half in isolation from scoring.
"""

from usage import MonthSnapshot, parse_usage


def test_parse_usage_chronological_sorting():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-03,8,10,0\n"
        "acme,2026-01,10,12,1\n"
        "acme,2026-02,9,15,0\n"
    )
    result = parse_usage(csv_text)
    assert result == {
        "acme": [
            MonthSnapshot(
                account_id="acme",
                month="2026-01",
                seats_active=10,
                logins=12,
                tickets_open=1,
            ),
            MonthSnapshot(
                account_id="acme",
                month="2026-02",
                seats_active=9,
                logins=15,
                tickets_open=0,
            ),
            MonthSnapshot(
                account_id="acme",
                month="2026-03",
                seats_active=8,
                logins=10,
                tickets_open=0,
            ),
        ]
    }  # D-2


def test_parse_usage_blank_seats_coerces_to_zero():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-01,10,5,0\n"
        "acme,2026-02, ,5,0\n"
        "acme,2026-03,,5,0\n"
    )
    result = parse_usage(csv_text)
    assert result["acme"][1].seats_active == 0  # D-1
    assert result["acme"][2].seats_active == 0  # D-1


def test_parse_usage_empty_and_header_only_returns_empty_dict():
    assert parse_usage("") == {}  # D-11
    assert parse_usage("account_id,month,seats_active,logins,tickets_open\n") == {}  # D-11


def test_parse_usage_multiple_accounts_partitioning():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,12,40,0\n"
        "acme,2026-01,10,5,0\n"
        "hooli,2026-02,12,45,1\n"
    )
    result = parse_usage(csv_text)
    assert result == {
        "acme": [
            MonthSnapshot(
                account_id="acme",
                month="2026-01",
                seats_active=10,
                logins=5,
                tickets_open=0,
            )
        ],
        "hooli": [
            MonthSnapshot(
                account_id="hooli",
                month="2026-01",
                seats_active=12,
                logins=40,
                tickets_open=0,
            ),
            MonthSnapshot(
                account_id="hooli",
                month="2026-02",
                seats_active=12,
                logins=45,
                tickets_open=1,
            ),
        ],
    }  # D-2
