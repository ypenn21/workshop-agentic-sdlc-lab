"""Contract tests for parse_usage().

Verifies the CSV parsing half alone. Every assertion derives directly from
a decision recorded in docs/spec.md.
"""

import pytest
from usage import MonthSnapshot, parse_usage


def test_parse_well_formed_csv_returns_snapshots_by_account():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,12,40,0\n"
        "hooli,2026-02,12,45,1\n"
        "acme,2026-01,10,5,0\n"
    )
    result = parse_usage(csv_text)

    assert set(result.keys()) == {"hooli", "acme"}  # D-12
    assert result["hooli"] == [
        MonthSnapshot(
            account_id="hooli",
            month="2026-01",
            seats_active=12,
            logins=40,
            tickets_open=0,
        ),  # D-12
        MonthSnapshot(
            account_id="hooli",
            month="2026-02",
            seats_active=12,
            logins=45,
            tickets_open=1,
        ),  # D-12
    ]
    assert result["acme"] == [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),  # D-12
    ]


def test_parse_sorts_months_in_ascending_chronological_order():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "globex,2026-03,6,5,0\n"
        "globex,2026-01,4,5,0\n"
        "globex,2026-02,10,5,0\n"
    )
    result = parse_usage(csv_text)

    months = [s.month for s in result["globex"]]
    assert months == ["2026-01", "2026-02", "2026-03"]  # D-2


def test_parse_blank_seats_active_defaults_to_zero():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "acme,2026-03,,5,0\n"
    )
    result = parse_usage(csv_text)

    assert result["acme"][0].seats_active == 0  # D-1


def test_parse_header_position_independence():
    csv_text = (
        "month,logins,account_id,tickets_open,seats_active\n"
        "2026-01,40,hooli,0,12\n"
    )
    result = parse_usage(csv_text)

    assert result["hooli"] == [
        MonthSnapshot(
            account_id="hooli",
            month="2026-01",
            seats_active=12,
            logins=40,
            tickets_open=0,
        ),  # D-12
    ]


def test_parse_empty_input_returns_empty_dict():
    assert parse_usage("") == {}  # D-11


def test_parse_headers_only_or_whitespace_returns_empty_dict():
    csv_text = "account_id,month,seats_active,logins,tickets_open\n   \n\n"
    assert parse_usage(csv_text) == {}  # D-11


def test_parse_blank_or_missing_logins_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,10,,0\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-13


def test_parse_blank_or_missing_tickets_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,10,5,\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-13


def test_parse_non_integer_metric_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,10,five,0\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-13


def test_parse_negative_seats_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,-5,10,0\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-14


def test_parse_negative_logins_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,10,-1,0\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-14


def test_parse_negative_tickets_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,10,5,-2\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-14


def test_parse_duplicate_account_and_month_raises_value_error():
    csv_text = (
        "account_id,month,seats_active,logins,tickets_open\n"
        "hooli,2026-01,10,5,0\n"
        "hooli,2026-01,12,6,1\n"
    )
    with pytest.raises(ValueError):
        parse_usage(csv_text)  # D-15
