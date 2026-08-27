"""Contract tests for health scoring (score)."""

import pytest

from usage import MonthSnapshot, Result, score


def test_score_baseline_perfect_account() -> None:
    """An account with no rule triggers returns score 10, HEALTHY, and empty reasons."""
    months = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]

    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])  # D-7


def test_score_seat_decline_rule_fires_at_forty_percent_drop() -> None:
    """A drop of 40% or more from prior peak triggers -4 deduction and reason."""
    months = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]

    assert score(months) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-5, D-7


def test_score_seat_decline_rule_fires_when_seats_drop_to_zero() -> None:
    """A drop to 0 seats triggers -4 deduction."""
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),
    ]

    assert score(months) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-5, D-7


def test_score_single_month_account_exempt_from_seat_decline() -> None:
    """An account with only 1 month history cannot trigger seat decline."""
    months = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]

    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])  # D-2, D-7


def test_score_zero_prior_peak_exempt_from_seat_decline() -> None:
    """An account with 0 prior peak seats does not trigger seat decline."""
    months = [
        MonthSnapshot(account_id="dormant", month="2026-01", seats_active=0, logins=10, tickets_open=0),
        MonthSnapshot(account_id="dormant", month="2026-02", seats_active=0, logins=10, tickets_open=0),
    ]

    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])  # D-2, D-7


def test_score_low_engagement_rule_fires() -> None:
    """Fewer than 3 logins in latest month triggers -3 deduction."""
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=10, logins=2, tickets_open=0),
    ]

    assert score(months) == Result(score=7, tier="MEDIUM", reasons=["low engagement"])  # D-3, D-5, D-7


def test_score_unresolved_support_load_rule_fires() -> None:
    """2 or more open tickets in latest month triggers -2 deduction."""
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=10, logins=5, tickets_open=2),
    ]

    assert score(months) == Result(score=8, tier="HEALTHY", reasons=["unresolved support load"])  # D-4, D-5, D-7


def test_score_multiple_deductions_ordered_deterministically() -> None:
    """Multiple firing rules preserve exact canonical reason ordering."""
    months = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]

    assert score(months) == Result(
        score=5,
        tier="MEDIUM",
        reasons=["low engagement", "unresolved support load"],
    )  # D-3, D-4, D-5, D-7


def test_score_all_three_deductions_fire() -> None:
    """All three rules fire and calculate score 1 (10 - 4 - 3 - 2)."""
    months = [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=5, logins=1, tickets_open=2),
    ]

    assert score(months) == Result(
        score=1,
        tier="AT RISK",
        reasons=["seats down sharply", "low engagement", "unresolved support load"],
    )  # D-1, D-3, D-4, D-5, D-7


def test_score_tier_boundary_score_five_is_medium() -> None:
    """Score 5 is explicitly classified as MEDIUM."""
    months = [
        MonthSnapshot(account_id="boundary", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="boundary", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]
    result = score(months)

    assert result.score == 5  # D-3, D-4
    assert result.tier == "MEDIUM"  # D-7


def test_score_empty_months_raises_value_error() -> None:
    """Calling score with an empty list raises ValueError."""
    with pytest.raises(ValueError):
        score([])  # D-10
