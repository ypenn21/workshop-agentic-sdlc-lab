"""Contract tests for score().

Verifies the scoring half alone. MonthSnapshot lists are written out longhand.
Every assertion and threshold traces to a decision in docs/spec.md.
"""

from __future__ import annotations

from usage import MonthSnapshot, Result, score


def test_score_baseline_healthy_account():
    months = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-9, D-11


def test_score_seat_decline_40_percent_drop():
    # Peak prior is 10 (month 1), latest is 6 (month 3) -> 40% decline
    months = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-4, D-11


def test_score_seat_decline_boundary_under_40_percent_no_deduction():
    # Peak prior is 10, latest is 7 -> 30% decline (does not trigger deduction)
    months = [
        MonthSnapshot(account_id="stable", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="stable", month="2026-02", seats_active=7, logins=5, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-4, D-11


def test_score_single_month_account_exempt_from_seat_decline():
    # Single-month account has no prior months to establish peak
    months = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-5, D-11


def test_score_zero_prior_peak_does_not_trigger_seat_decline():
    months = [
        MonthSnapshot(account_id="zero", month="2026-01", seats_active=0, logins=5, tickets_open=0),
        MonthSnapshot(account_id="zero", month="2026-02", seats_active=0, logins=5, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-6, D-11


def test_score_seat_decline_with_zero_latest_seats():
    # Peak prior is 10, latest is 0 -> 100% decline
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-4, D-11


def test_score_low_engagement_deduction():
    # Latest month has 2 logins (< 3)
    months = [
        MonthSnapshot(account_id="loweng", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="loweng", month="2026-02", seats_active=10, logins=2, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=7, tier="MEDIUM", reasons=["low engagement"])  # D-7, D-11


def test_score_engagement_boundary_three_logins_no_deduction():
    # Latest month has 3 logins (not < 3)
    months = [
        MonthSnapshot(account_id="mideng", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="mideng", month="2026-02", seats_active=10, logins=3, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-7, D-11


def test_score_unresolved_support_load_deduction():
    # Latest month has 2 open tickets (>= 2)
    months = [
        MonthSnapshot(account_id="tickets", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="tickets", month="2026-02", seats_active=10, logins=5, tickets_open=2),
    ]
    result = score(months)
    assert result == Result(score=8, tier="HEALTHY", reasons=["unresolved support load"])  # D-8, D-11


def test_score_support_load_boundary_one_ticket_no_deduction():
    # Latest month has 1 open ticket (< 2)
    months = [
        MonthSnapshot(account_id="tickets", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="tickets", month="2026-02", seats_active=10, logins=5, tickets_open=1),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-8, D-11


def test_score_cumulative_deductions_and_deterministic_reason_ordering():
    # All three deductions: 50% seat drop (-4), 1 login (-3), 3 open tickets (-2)
    months = [
        MonthSnapshot(account_id="all_penalties", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="all_penalties", month="2026-02", seats_active=5, logins=1, tickets_open=3),
    ]
    result = score(months)
    assert result.score == 1  # D-9, D-10
    assert result.tier == "AT RISK"  # D-11
    assert result.reasons == ["seats down sharply", "low engagement", "unresolved support load"]  # D-9


def test_score_floor_at_zero():
    # Starting at 10, penalties sum to 9; floor ensures no negative numbers
    months = [
        MonthSnapshot(account_id="zero_floor", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="zero_floor", month="2026-02", seats_active=0, logins=0, tickets_open=5),
    ]
    result = score(months)
    assert result.score >= 0  # D-10
    assert result.tier == "AT RISK"  # D-11


def test_score_tier_boundaries():
    # 8-10 is HEALTHY
    assert score([MonthSnapshot("t", "2026-01", 10, 5, 0)]).tier == "HEALTHY"  # D-11
    assert score([
        MonthSnapshot("t", "2026-01", 10, 5, 0),
        MonthSnapshot("t", "2026-02", 10, 5, 2),  # -2 -> score 8
    ]).tier == "HEALTHY"  # D-11

    # 5-7 is MEDIUM
    assert score([
        MonthSnapshot("t", "2026-01", 10, 5, 0),
        MonthSnapshot("t", "2026-02", 10, 2, 0),  # -3 -> score 7
    ]).tier == "MEDIUM"  # D-11
    assert score([
        MonthSnapshot("t", "2026-01", 10, 5, 0),
        MonthSnapshot("t", "2026-02", 10, 2, 2),  # -3 -2 -> score 5
    ]).tier == "MEDIUM"  # D-11

    # 0-4 is AT RISK
    assert score([
        MonthSnapshot("t", "2026-01", 10, 5, 0),
        MonthSnapshot("t", "2026-02", 5, 2, 0),  # -4 -3 -> score 3
    ]).tier == "AT RISK"  # D-11
