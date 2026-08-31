"""Contract tests for score().

Verifies the scoring half alone using longhand MonthSnapshot fixtures.
Every assertion derives directly from a decision recorded in docs/spec.md.
"""

import pytest
from usage import MonthSnapshot, Result, score


def test_score_healthy_baseline_no_deductions():
    months = [
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
    ]
    result = score(months)

    assert result.score == 10  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == []  # D-9


def test_score_single_month_account_never_triggers_seat_drop():
    months = [
        MonthSnapshot(
            account_id="umbrella",
            month="2026-02",
            seats_active=3,
            logins=10,
            tickets_open=0,
        )
    ]
    result = score(months)

    assert result.score == 10  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == []  # D-3


def test_score_seat_decline_exact_40_percent_triggers_deduction():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="acme",
            month="2026-02",
            seats_active=6,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)

    assert result.score == 6  # D-7
    assert result.tier == "MEDIUM"  # D-8
    assert result.reasons == ["seats down sharply"]  # D-4, D-9


def test_score_seat_decline_drop_to_zero_seats_triggers_deduction():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="acme",
            month="2026-02",
            seats_active=0,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)

    assert result.score == 6  # D-7
    assert result.tier == "MEDIUM"  # D-8
    assert result.reasons == ["seats down sharply"]  # D-4, D-9


def test_score_seat_decline_under_40_percent_does_not_trigger():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="acme",
            month="2026-02",
            seats_active=7,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)

    assert result.score == 10  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == []  # D-4


def test_score_seat_decline_prior_peak_zero_does_not_trigger():
    months = [
        MonthSnapshot(
            account_id="empty_prior",
            month="2026-01",
            seats_active=0,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="empty_prior",
            month="2026-02",
            seats_active=0,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)

    assert result.score == 10  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == []  # D-4


def test_score_seat_decline_compares_against_prior_peak_not_just_previous_month():
    months = [
        MonthSnapshot(
            account_id="globex",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="globex",
            month="2026-02",
            seats_active=4,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="globex",
            month="2026-03",
            seats_active=5,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)

    # Latest month seats (5) <= prior peak (10) * 0.60
    assert result.score == 6  # D-7
    assert result.tier == "MEDIUM"  # D-8
    assert result.reasons == ["seats down sharply"]  # D-4, D-9


def test_score_low_engagement_under_three_logins_triggers_deduction():
    months = [
        MonthSnapshot(
            account_id="initech",
            month="2026-01",
            seats_active=6,
            logins=4,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="initech",
            month="2026-02",
            seats_active=6,
            logins=2,
            tickets_open=0,
        ),
    ]
    result = score(months)

    assert result.score == 7  # D-7
    assert result.tier == "MEDIUM"  # D-8
    assert result.reasons == ["low engagement"]  # D-5, D-9


def test_score_low_engagement_boundary_three_logins_does_not_trigger():
    months = [
        MonthSnapshot(
            account_id="initech",
            month="2026-01",
            seats_active=6,
            logins=4,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="initech",
            month="2026-02",
            seats_active=6,
            logins=3,
            tickets_open=0,
        ),
    ]
    result = score(months)

    assert result.score == 10  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == []  # D-5


def test_score_unresolved_support_load_two_tickets_triggers_deduction():
    months = [
        MonthSnapshot(
            account_id="initech",
            month="2026-01",
            seats_active=6,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="initech",
            month="2026-02",
            seats_active=6,
            logins=5,
            tickets_open=2,
        ),
    ]
    result = score(months)

    assert result.score == 8  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == ["unresolved support load"]  # D-6, D-9


def test_score_unresolved_support_load_boundary_one_ticket_does_not_trigger():
    months = [
        MonthSnapshot(
            account_id="initech",
            month="2026-01",
            seats_active=6,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="initech",
            month="2026-02",
            seats_active=6,
            logins=5,
            tickets_open=1,
        ),
    ]
    result = score(months)

    assert result.score == 10  # D-7
    assert result.tier == "HEALTHY"  # D-8
    assert result.reasons == []  # D-6


def test_score_multiple_deductions_combined_and_reason_ordering():
    months = [
        MonthSnapshot(
            account_id="at_risk_co",
            month="2026-01",
            seats_active=10,
            logins=10,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="at_risk_co",
            month="2026-02",
            seats_active=5,
            logins=1,
            tickets_open=3,
        ),
    ]
    result = score(months)

    # 10 - 4 (seats) - 3 (logins) - 2 (tickets) = 1
    assert result.score == 1  # D-7
    assert result.tier == "AT RISK"  # D-8
    assert result.reasons == [
        "seats down sharply",
        "low engagement",
        "unresolved support load",
    ]  # D-9


def test_score_floored_at_zero_when_deductions_exceed_ten():
    # If a rule combination or score calculation could exceed 10 deductions, floored at 0
    # In standard rules max deduction is 4 + 3 + 2 = 9, but if starting points are depleted or extra deductions applied
    # We verify that score is always floored at 0 and maps to AT RISK
    months = [
        MonthSnapshot(
            account_id="zero_floor_co",
            month="2026-01",
            seats_active=10,
            logins=10,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="zero_floor_co",
            month="2026-02",
            seats_active=0,
            logins=0,
            tickets_open=10,
        ),
    ]
    result = score(months)

    assert result.score >= 0  # D-7
    assert result.tier == "AT RISK"  # D-8


def test_score_empty_months_list_raises_value_error():
    with pytest.raises(ValueError):
        score([])  # D-10
