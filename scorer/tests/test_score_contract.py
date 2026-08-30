"""Contract tests for health scoring engine (scorer/usage.py:score).

Verifies the scoring half alone: score(longhand MonthSnapshot list) produces
the exact Result(score, tier, reasons). Never calls parse_usage or reads files.
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest

from usage import MonthSnapshot, Result, score


def test_score_pristine_account() -> None:
    """An account with steady seats, high logins, and zero tickets gets 10 HEALTHY."""
    months = [
        MonthSnapshot(account_id="hooli", month="2026-01", seats_active=12, logins=40, tickets_open=0),
        MonthSnapshot(account_id="hooli", month="2026-02", seats_active=12, logins=45, tickets_open=1),
    ]

    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-4, D-8


def test_score_seat_contraction_exact_forty_percent_drop() -> None:
    """A 40% drop from prior peak triggers a 4-point deduction and 'seats down sharply'."""
    months = [
        MonthSnapshot(account_id="vandelay", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-02", seats_active=6, logins=5, tickets_open=0),
        MonthSnapshot(account_id="vandelay", month="2026-03", seats_active=6, logins=5, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-5, D-8


def test_score_seat_contraction_greater_than_forty_percent_drop() -> None:
    """A drop exceeding 40% from prior peak triggers 'seats down sharply'."""
    months = [
        MonthSnapshot(account_id="acme", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-02", seats_active=8, logins=5, tickets_open=0),
        MonthSnapshot(account_id="acme", month="2026-03", seats_active=0, logins=5, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-5, D-8


def test_score_seat_contraction_under_forty_percent_drop_no_deduction() -> None:
    """A seat drop strictly less than 40% (e.g. 30%) does not trigger a deduction."""
    months = [
        MonthSnapshot(account_id="globex", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="globex", month="2026-02", seats_active=7, logins=5, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-5, D-8


def test_score_seat_contraction_single_month_exemption() -> None:
    """Single-month accounts have no prior peak and are exempt from seat contraction."""
    months = [
        MonthSnapshot(account_id="umbrella", month="2026-02", seats_active=3, logins=10, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-5, D-8


def test_score_seat_contraction_zero_peak_prior_exemption() -> None:
    """Accounts where all prior months had 0 seats are exempt from seat contraction."""
    months = [
        MonthSnapshot(account_id="zero_prior", month="2026-01", seats_active=0, logins=10, tickets_open=0),
        MonthSnapshot(account_id="zero_prior", month="2026-02", seats_active=0, logins=10, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-5, D-8


def test_score_low_engagement_deduction() -> None:
    """Latest month logins strictly fewer than 3 deducts 3 points for 'low engagement'."""
    months = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=7, tier="MEDIUM", reasons=["low engagement"])  # D-6, D-8


def test_score_low_engagement_boundary_three_logins() -> None:
    """Latest month with exactly 3 logins does not trigger the low engagement deduction."""
    months = [
        MonthSnapshot(account_id="boundary", month="2026-01", seats_active=6, logins=3, tickets_open=0),
    ]

    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-6, D-8


def test_score_unresolved_support_load_deduction() -> None:
    """Latest month tickets_open >= 2 deducts 2 points for 'unresolved support load'."""
    months = [
        MonthSnapshot(account_id="tickets", month="2026-01", seats_active=6, logins=5, tickets_open=2),
    ]

    result = score(months)

    assert result == Result(score=8, tier="HEALTHY", reasons=["unresolved support load"])  # D-7, D-8


def test_score_unresolved_support_load_boundary_one_ticket() -> None:
    """Latest month with exactly 1 open ticket does not trigger support load deduction."""
    months = [
        MonthSnapshot(account_id="boundary", month="2026-01", seats_active=6, logins=5, tickets_open=1),
    ]

    result = score(months)

    assert result == Result(score=10, tier="HEALTHY", reasons=[])  # D-7, D-8


def test_score_compound_deductions_and_reason_ordering() -> None:
    """Multiple deductions combine subtractively and reasons maintain strict evaluation order."""
    months = [
        MonthSnapshot(account_id="initech", month="2026-01", seats_active=6, logins=4, tickets_open=0),
        MonthSnapshot(account_id="initech", month="2026-02", seats_active=6, logins=2, tickets_open=3),
    ]

    result = score(months)

    assert result == Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"])  # D-6, D-7, D-8


def test_score_triple_deduction_and_at_risk_tier() -> None:
    """All 3 deductions fire in order, dropping score to 1 in AT RISK tier."""
    months = [
        MonthSnapshot(account_id="churn_risk", month="2026-01", seats_active=10, logins=5, tickets_open=0),
        MonthSnapshot(account_id="churn_risk", month="2026-02", seats_active=5, logins=1, tickets_open=4),
    ]

    result = score(months)

    assert result == Result(
        score=1,
        tier="AT RISK",
        reasons=["seats down sharply", "low engagement", "unresolved support load"],
    )  # D-4, D-5, D-6, D-7, D-8


def test_score_floor_at_zero() -> None:
    """Score never falls below 0 even if deductions total 10 or more."""
    months = [
        MonthSnapshot(account_id="worst", month="2026-01", seats_active=100, logins=5, tickets_open=0),
        MonthSnapshot(account_id="worst", month="2026-02", seats_active=0, logins=0, tickets_open=10),
    ]

    result = score(months)

    assert result.score == 1  # 10 - 4 - 3 - 2 = 1, floored at >= 0  # D-4
    assert result.tier == "AT RISK"  # D-8


def test_score_empty_snapshot_list_raises_value_error() -> None:
    """score([]) raises ValueError('Cannot score empty month list')."""
    with pytest.raises(ValueError, match=r"Cannot score empty month list"):
        score([])  # D-11


def test_usage_module_purity_ast_check() -> None:
    """scorer/usage.py contains no forbidden I/O imports or builtin open calls."""
    usage_file = Path(__file__).parent.parent / "usage.py"
    tree = ast.parse(usage_file.read_text(encoding="utf-8"))

    forbidden_modules = {"os", "pathlib", "sys", "socket", "urllib", "requests", "http"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_modules, f"Forbidden import {alias.name}"  # D-9
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0] not in forbidden_modules, f"Forbidden import from {node.module}"  # D-9
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            raise AssertionError("Forbidden direct call to open() in pure module")  # D-9
