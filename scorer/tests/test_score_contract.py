from __future__ import annotations

from usage import MonthSnapshot, Result, score


def test_score_healthy_account_no_deductions():
    months = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]
    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])


def test_score_seat_decline_compares_latest_against_first_month():
    # vandelay: 10 -> 6 -> 5 compares 5 against 10 (50% drop, fires)
    months = [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=5, logins=5, tickets_open=0),
    ]
    assert score(months) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D01


def test_score_seat_drop_from_intermediate_month_does_not_fire():
    # globex: 4 -> 10 -> 6 compares 6 against 4 (50% increase, does not fire)
    months = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=4, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]
    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])  # D01


def test_score_single_month_cannot_fire_seat_decline():
    # umbrella: only one month present, cannot lose 4 points for seat decline
    months = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]
    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])


def test_score_five_is_medium_tier():
    # initech: logins < 3 (-3), tickets >= 2 (-2) => score 5 => MEDIUM
    months = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]
    result = score(months)
    assert result.score == 5
    assert result.tier == "MEDIUM"  # D02
    assert result.reasons == ["low engagement", "unresolved support load"]


def test_score_acme_zero_seats_drop():
    # acme: 10 -> 8 -> 0 (100% drop, fires)
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),  # D03
    ]
    assert score(months) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])


def test_score_all_rules_firing_produces_at_risk_tier_and_ordered_reasons():
    # seats: 10 -> 5 (50% drop, -4), logins: 1 (<3, -3), tickets: 2 (>=2, -2) => score 1 => AT RISK
    months = [
        MonthSnapshot(account_id="test_co", month="2026-01", seats_active=10, logins=10, tickets_open=0),
        MonthSnapshot(account_id="test_co", month="2026-02", seats_active=5, logins=1, tickets_open=2),
    ]
    assert score(months) == Result(
        score=1,
        tier="AT RISK",  # D02
        reasons=["seats down sharply", "low engagement", "unresolved support load"],
    )


def test_score_tier_boundaries():
    # HEALTHY: 8-10 (e.g. -2 for tickets => score 8)
    months_8 = [
        MonthSnapshot(account_id="co8", month="2026-01", seats_active=10, logins=10, tickets_open=2),
    ]
    assert score(months_8).tier == "HEALTHY"  # D02

    # MEDIUM: 5-7 (e.g. -3 for logins => score 7)
    months_7 = [
        MonthSnapshot(account_id="co7", month="2026-01", seats_active=10, logins=2, tickets_open=0),
    ]
    assert score(months_7).tier == "MEDIUM"  # D02

    # AT RISK: 0-4 (e.g. -4 for seats, -2 for tickets => score 4)
    months_4 = [
        MonthSnapshot(account_id="co4", month="2026-01", seats_active=10, logins=10, tickets_open=0),
        MonthSnapshot(account_id="co4", month="2026-02", seats_active=5, logins=10, tickets_open=2),
    ]
    assert score(months_4).tier == "AT RISK"  # D02
