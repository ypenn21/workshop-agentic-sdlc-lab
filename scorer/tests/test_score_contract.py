"""Acceptance tests for the scoring half of the account health scorer."""

from usage import MonthSnapshot, Result, score


def test_score_healthy_account_no_deductions_hooli():
    months = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])


def test_score_single_month_cannot_fire_seat_decline_umbrella():
    months = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=10, tier="HEALTHY", reasons=[])


def test_score_seat_decline_compares_to_prior_peak_vandelay():
    months = [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1


def test_score_seat_decline_compares_to_prior_peak_globex():
    months = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]
    result = score(months)
    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1


def test_score_blank_seat_count_parsed_as_zero_fires_seat_decline_acme():
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D-2
    ]
    result = score(months)
    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1


def test_score_low_engagement_and_support_load_initech():
    months = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]
    result = score(months)
    assert result == Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"])  # D-3


def test_score_all_rules_fire_in_order_with_at_risk_tier():
    months = [
        MonthSnapshot(account_id="crisis_corp", month="2026-01", seats_active=10, logins=10, tickets_open=0),
        MonthSnapshot(account_id="crisis_corp", month="2026-02", seats_active=5, logins=1, tickets_open=4),
    ]
    result = score(months)
    assert result == Result(  # D-1
        score=1,
        tier="AT RISK",
        reasons=["seats down sharply", "low engagement", "unresolved support load"],
    )


def test_score_tier_boundary_medium_score_5():
    months = [
        MonthSnapshot(account_id="sample", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="sample", month="2026-02", seats_active=10, logins=1, tickets_open=2),
    ]
    result = score(months)
    assert result.score == 5
    assert result.tier == "MEDIUM"  # D-3
