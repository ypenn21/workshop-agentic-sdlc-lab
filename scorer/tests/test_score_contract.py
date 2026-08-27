"""Contract tests for account health scoring (scorer/usage.py: score)."""

from __future__ import annotations

from usage import MonthSnapshot, Result, score


def test_score_baseline_healthy_account() -> None:
    months = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]
    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-3


def test_score_seat_decline_compares_latest_to_prior_peak() -> None:
    # An account with 10 seats in month 1, 6 in month 2, and 5 in month 3
    # compares 5 against peak 10 (50% drop >= 40% -> deduct 4), rather than against month 2 (16.7% drop).
    months = [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]
    result = score(months)

    assert result.score == 6  # D-1
    assert result.tier == "MEDIUM"  # D-3
    assert result.reasons == ["seats down sharply"]  # D-1


def test_score_single_month_account_is_exempt_from_seat_decline() -> None:
    months = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]
    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-1


def test_score_seat_decline_exact_40_percent_boundary() -> None:
    # Peak is 10 in 2026-02, latest is 6 in 2026-03 -> (10 - 6) / 10 = 0.40 (40%) -> triggers deduction
    months = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]
    result = score(months)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-3


def test_score_seat_decline_below_40_percent_boundary_does_not_trigger() -> None:
    # Peak is 10, latest is 7 -> (10 - 7) / 10 = 30% < 40% -> no deduction
    months = [
        MonthSnapshot(account_id="beta", month="2026-01", seats_active=10, logins=10, tickets_open=0),
        MonthSnapshot(account_id="beta", month="2026-02", seats_active=7, logins=10, tickets_open=0),
    ]
    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-1


def test_score_zero_seats_active_triggers_seat_decline() -> None:
    # 0 active seats (from missing/blank CSV coercion) vs peak 10 -> 100% drop >= 40%
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),
    ]
    result = score(months)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-2, D-3


def test_score_low_engagement_rule_deducts_3_points() -> None:
    # logins < 3 in latest month
    months = [
        MonthSnapshot(account_id="gamma", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="gamma", month="2026-02", seats_active=10, logins=2, tickets_open=0),
    ]
    result = score(months)

    assert result == Result(score=7, tier="MEDIUM", reasons=["low engagement"])  # D-3


def test_score_unresolved_support_load_rule_deducts_2_points() -> None:
    # tickets_open >= 2 in latest month
    months = [
        MonthSnapshot(account_id="delta", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="delta", month="2026-02", seats_active=10, logins=5, tickets_open=2),
    ]
    result = score(months)

    assert result == Result(score=8, tier="HEALTHY", reasons=["unresolved support load"])  # D-3


def test_score_multiple_deductions_canonical_reason_order_and_medium_tier_at_5() -> None:
    # logins=2 (-3), tickets_open=3 (-2) -> score = 10 - 3 - 2 = 5
    months = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]
    result = score(months)

    assert result.score == 5  # D-3
    assert result.tier == "MEDIUM"  # D-3
    assert result.reasons == ["low engagement", "unresolved support load"]


def test_score_all_three_rules_fire_in_canonical_order_and_at_risk_tier() -> None:
    # seats: 10 -> 5 (-4), logins: 1 (-3), tickets_open: 3 (-2) -> score = 10 - 4 - 3 - 2 = 1 -> AT RISK
    months = [
        MonthSnapshot(account_id="omega", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="omega", month="2026-02", seats_active=5, logins=1, tickets_open=3),
    ]
    result = score(months)

    assert result == Result(
        score=1,
        tier="AT RISK",  # D-3
        reasons=["seats down sharply", "low engagement", "unresolved support load"],  # D-1
    )


def test_score_tier_boundary_at_risk_for_score_4() -> None:
    # seats: 10 -> 5 (-4), tickets_open: 2 (-2) -> score = 10 - 4 - 2 = 4 -> AT RISK (0-4)
    months = [
        MonthSnapshot(account_id="zeta", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="zeta", month="2026-02", seats_active=5, logins=5, tickets_open=2),
    ]
    result = score(months)

    assert result.score == 4  # D-3
    assert result.tier == "AT RISK"  # D-3
    assert result.reasons == ["seats down sharply", "unresolved support load"]  # D-1


def test_score_floored_at_zero() -> None:
    # Baseline 10 with total deductions floored at 0
    months = [
        MonthSnapshot(account_id="zero", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="zero", month="2026-02", seats_active=1, logins=0, tickets_open=10),
    ]
    result = score(months)

    assert result.score >= 0
    assert result.tier == "AT RISK"  # D-3
