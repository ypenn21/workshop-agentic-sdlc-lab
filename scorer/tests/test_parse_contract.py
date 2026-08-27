"""Contract tests for usage export parsing (parse_usage)."""

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


def test_parse_usage_fixture() -> None:
    """parse_usage(FIXTURE) produces exactly the expected MonthSnapshot mapping."""
    result = parse_usage(FIXTURE)

    assert result == {
        "hooli": [
            MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
            MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
        ],  # D-8
        "acme": [
            MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
            MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-9
        ],  # D-8
        "globex": [
            MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
            MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
        ],  # D-8
        "vandelay": [
            MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
            MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
            MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
        ],  # D-8
        "initech": [
            MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
            MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
        ],  # D-8
        "umbrella": [
            MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
        ],  # D-8
    }  # D-8


def test_parse_usage_chronological_sorting() -> None:
    """Rows appearing out of order are sorted in ascending month order."""
    csv_text = """account_id,month,seats_active,logins,tickets_open
acme,2026-03,10,5,0
acme,2026-01,10,5,0
acme,2026-02,10,5,0
"""
    result = parse_usage(csv_text)

    assert result["acme"] == [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=10, logins=5, tickets_open=0),
    ]  # D-8


def test_parse_usage_coerces_blank_numeric_fields() -> None:
    """Blank or whitespace values in seats_active, logins, or tickets_open parse as 0."""
    csv_text = """account_id,month,seats_active,logins,tickets_open
test_corp,2026-01,,,
"""
    result = parse_usage(csv_text)

    assert result["test_corp"] == [
        MonthSnapshot(account_id="test_corp", month="2026-01", seats_active=0, logins=0, tickets_open=0)  # D-9
    ]  # D-9


def test_parse_usage_empty_input_returns_empty_dict() -> None:
    """Empty CSV or header-only CSV returns an empty mapping."""
    assert parse_usage("") == {}  # D-10
    assert parse_usage("account_id,month,seats_active,logins,tickets_open\n") == {}  # D-8, D-10
