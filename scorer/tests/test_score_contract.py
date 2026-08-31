"""Contract tests for score().

Tests the scoring half in isolation from CSV parsing using longhand MonthSnapshot lists.
"""

from usage import MonthSnapshot, Result, score


def test_score_perfect_account_no_deductions():
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
    assert score(months) == Result(score=10, tier="HEALTHY", reasons=[])  # D-9


def test_score_single_month_account_immune_to_seat_drop():
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
    assert result.score == 10  # D-3
    assert "seats down sharply" not in result.reasons  # D-3


def test_score_seat_decline_compares_to_all_prior_months_peak():
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
    # Prior peak is 10 (month 1), latest is 5 (50% drop from peak, > 40%)
    result = score(months)
    assert result.score == 6  # D-4, D-5
    assert result.reasons == ["seats down sharply"]  # D-4, D-5, D-8


def test_score_seat_decline_exact_40_percent_threshold():
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
    # Prior peak is 10, latest is 6 (exact 40% decline)
    result = score(months)
    assert result.score == 6  # D-5
    assert result.tier == "MEDIUM"  # D-9
    assert result.reasons == ["seats down sharply"]  # D-5, D-8


def test_score_seat_decline_less_than_40_percent_does_not_fire():
    months = [
        MonthSnapshot(
            account_id="stable",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="stable",
            month="2026-02",
            seats_active=7,
            logins=5,
            tickets_open=0,
        ),
    ]
    # Drop is 30% (< 40%)
    result = score(months)
    assert result.score == 10  # D-5
    assert result.reasons == []  # D-5


def test_score_low_engagement_threshold():
    # logins == 2 triggers -3 deduction
    months_low = [
        MonthSnapshot(
            account_id="eng_low",
            month="2026-01",
            seats_active=10,
            logins=2,
            tickets_open=0,
        )
    ]
    result_low = score(months_low)
    assert result_low.score == 7  # D-6
    assert result_low.reasons == ["low engagement"]  # D-6, D-8

    # logins == 3 does not trigger deduction
    months_ok = [
        MonthSnapshot(
            account_id="eng_ok",
            month="2026-01",
            seats_active=10,
            logins=3,
            tickets_open=0,
        )
    ]
    result_ok = score(months_ok)
    assert result_ok.score == 10  # D-6
    assert "low engagement" not in result_ok.reasons  # D-6


def test_score_unresolved_support_load_threshold():
    # tickets_open == 2 triggers -2 deduction
    months_heavy = [
        MonthSnapshot(
            account_id="support_heavy",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=2,
        )
    ]
    result_heavy = score(months_heavy)
    assert result_heavy.score == 8  # D-7
    assert result_heavy.reasons == ["unresolved support load"]  # D-7, D-8

    # tickets_open == 1 does not trigger deduction
    months_light = [
        MonthSnapshot(
            account_id="support_light",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=1,
        )
    ]
    result_light = score(months_light)
    assert result_light.score == 10  # D-7
    assert "unresolved support load" not in result_light.reasons  # D-7


def test_score_cumulative_deductions_and_reason_ordering():
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
    # Deductions: seat drop (-4) + low engagement (-3) + support load (-2) = -9 -> score = 1
    result = score(months)
    assert result.score == 1  # D-5, D-6, D-7
    assert result.tier == "AT RISK"  # D-9
    assert result.reasons == [
        "seats down sharply",
        "low engagement",
        "unresolved support load",
    ]  # D-8


def test_score_tier_classification_boundaries():
    def make_snapshot(logins: int, tickets: int) -> list[MonthSnapshot]:
        return [
            MonthSnapshot(
                account_id="tier_test",
                month="2026-01",
                seats_active=10,
                logins=logins,
                tickets_open=tickets,
            )
        ]

    # Score 10 -> HEALTHY
    assert score(make_snapshot(10, 0)).tier == "HEALTHY"  # D-9
    # Score 8 -> HEALTHY (tickets_open=2 -> -2)
    assert score(make_snapshot(10, 2)).tier == "HEALTHY"  # D-9
    # Score 7 -> MEDIUM (logins=1 -> -3)
    assert score(make_snapshot(1, 0)).tier == "MEDIUM"  # D-9
    # Score 5 -> MEDIUM (logins=1, tickets=2 -> -5)
    assert score(make_snapshot(1, 2)).tier == "MEDIUM"  # D-9
    # Score 4 -> AT RISK (custom multi-month seat drop -4 + logins=1 -3 -> 3)
    at_risk_months = [
        MonthSnapshot(
            account_id="risk",
            month="2026-01",
            seats_active=10,
            logins=5,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="risk",
            month="2026-02",
            seats_active=0,
            logins=1,
            tickets_open=0,
        ),
    ]
    assert score(at_risk_months).tier == "AT RISK"  # D-9


def test_score_floored_at_zero():
    months = [
        MonthSnapshot(
            account_id="doomed",
            month="2026-01",
            seats_active=100,
            logins=10,
            tickets_open=0,
        ),
        MonthSnapshot(
            account_id="doomed",
            month="2026-02",
            seats_active=0,
            logins=0,
            tickets_open=10,
        ),
    ]
    # 10 - 4 - 3 - 2 = 1. Floored at 0 invariant holds.
    result = score(months)
    assert result.score >= 0  # D-10
    assert result.tier == "AT RISK"  # D-9
