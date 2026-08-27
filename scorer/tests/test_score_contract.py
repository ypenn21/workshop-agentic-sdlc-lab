"""Contract tests for score."""

from __future__ import annotations

from usage import MonthSnapshot, score


def test_score_starting_score_healthy_single_month():
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
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []


def test_score_starting_score_healthy_multi_month():
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
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []


def test_score_single_month_cannot_fire_seat_decline():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=0,
            logins=5,
            tickets_open=0,
        )
    ]
    result = score(months)
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []


def test_score_seat_decline_exact_40_percent_drop():
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
    assert result.score == 6  # D-1
    assert result.tier == "MEDIUM"
    assert result.reasons == ["seats down sharply"]  # D-1


def test_score_seat_decline_below_40_percent_threshold_does_not_fire():
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
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []


def test_score_seat_decline_compares_to_prior_maximum_not_previous_month():
    months = [
        MonthSnapshot(
            account_id="vandelay",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="vandelay",
            month="2026-02",
            seats_active=6,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="vandelay",
            month="2026-03",
            seats_active=5,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)
    assert result.score == 6  # D-1
    assert result.tier == "MEDIUM"
    assert result.reasons == ["seats down sharply"]  # D-1


def test_score_seat_decline_compares_to_peak_in_middle_month():
    months = [
        MonthSnapshot(
            account_id="globex",
            month="2026-01",
            seats_active=4,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="globex",
            month="2026-02",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="globex",
            month="2026-03",
            seats_active=6,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)
    assert result.score == 6  # D-1
    assert result.tier == "MEDIUM"
    assert result.reasons == ["seats down sharply"]  # D-1


def test_score_seat_decline_with_zero_seats():
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
            seats_active=8,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="acme",
            month="2026-03",
            seats_active=0,
            logins=5,
            tickets_open=0,
        ),
    ]
    result = score(months)
    assert result.score == 6  # D-1
    assert result.tier == "MEDIUM"
    assert result.reasons == ["seats down sharply"]  # D-2


def test_score_low_engagement_under_three_logins():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=2,
            tickets_open=0,
        )
    ]
    result = score(months)
    assert result.score == 7
    assert result.tier == "MEDIUM"
    assert result.reasons == ["low engagement"]


def test_score_low_engagement_boundary_three_logins():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=3,
            tickets_open=0,
        )
    ]
    result = score(months)
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []


def test_score_support_load_two_or_more_tickets():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=2,
        )
    ]
    result = score(months)
    assert result.score == 8
    assert result.tier == "HEALTHY"
    assert result.reasons == ["unresolved support load"]


def test_score_support_load_boundary_one_ticket():
    months = [
        MonthSnapshot(
            account_id="acme",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=1,
        )
    ]
    result = score(months)
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []


def test_score_multiple_rules_and_tier_medium_at_five():
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
            tickets_open=3,
        ),
    ]
    result = score(months)
    assert result.score == 5  # D-3
    assert result.tier == "MEDIUM"  # D-3
    assert result.reasons == ["low engagement", "unresolved support load"]  # D-3


def test_score_all_rules_fire_reason_order_and_at_risk_tier():
    months = [
        MonthSnapshot(
            account_id="troubled",
            month="2026-01",
            seats_active=10,
            logins=10,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="troubled",
            month="2026-02",
            seats_active=5,
            logins=1,
            tickets_open=4,
        ),
    ]
    result = score(months)
    assert result.score == 1  # D-1
    assert result.tier == "AT RISK"
    assert result.reasons == [
        "seats down sharply",
        "low engagement",
        "unresolved support load",
    ]  # D-1


def test_score_tier_at_risk_boundary_at_four():
    months = [
        MonthSnapshot(
            account_id="failing",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="failing",
            month="2026-02",
            seats_active=5,
            logins=5,
            tickets_open=2,
        ),
    ]
    result = score(months)
    assert result.score == 4  # D-1
    assert result.tier == "AT RISK"
    assert result.reasons == ["seats down sharply", "unresolved support load"]  # D-1


def test_score_evaluates_rules_against_latest_month_only():
    months = [
        MonthSnapshot(
            account_id="recovering",
            month="2026-01",
            seats_active=10,
            logins=1,
            tickets_open=5,
        ),
        MonthSnapshot(
            account_id="recovering",
            month="2026-02",
            seats_active=10,
            logins=10,
            tickets_open=0,
        ),
    ]
    result = score(months)
    assert result.score == 10
    assert result.tier == "HEALTHY"
    assert result.reasons == []
