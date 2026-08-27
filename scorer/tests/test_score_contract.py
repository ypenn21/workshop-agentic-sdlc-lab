"""Contract tests for score.

Verifies the scoring half of the system in isolation.
Every test specifies MonthSnapshot instances longhand.
"""

from __future__ import annotations

from usage import MonthSnapshot, Result, score


def test_score_healthy_account_no_deductions():
    snapshots = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]
    result = score(snapshots)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])


def test_score_seat_decline_from_prior_peak():
    snapshots = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]
    result = score(snapshots)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1


def test_score_seat_decline_across_multiple_prior_months():
    snapshots = [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]
    result = score(snapshots)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1


def test_score_zero_seats_triggers_seat_decline():
    snapshots = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),
    ]
    result = score(snapshots)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-2


def test_score_five_maps_to_medium_tier():
    snapshots = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]
    result = score(snapshots)

    assert result == Result(
        score=5,
        tier="MEDIUM",  # D-3
        reasons=["low engagement", "unresolved support load"],
    )


def test_score_single_month_does_not_fire_seat_decline():
    snapshots = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]
    result = score(snapshots)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])


def test_score_all_rules_fire_floored_at_zero_and_tier_at_risk():
    snapshots = [
        MonthSnapshot(account_id="troubled", month="2026-01", seats_active=50, logins=20, tickets_open=0),
        MonthSnapshot(account_id="troubled", month="2026-02", seats_active=10, logins=1, tickets_open=4),
    ]
    result = score(snapshots)

    assert result == Result(
        score=1,
        tier="AT RISK",
        reasons=["seats down sharply", "low engagement", "unresolved support load"],
    )


def test_score_floors_at_zero():
    snapshots = [
        MonthSnapshot(account_id="zeroed", month="2026-01", seats_active=100, logins=50, tickets_open=0),
        MonthSnapshot(account_id="zeroed", month="2026-02", seats_active=0, logins=0, tickets_open=10),
    ]
    result = score(snapshots)

    assert result.score == 0
    assert result.tier == "AT RISK"
