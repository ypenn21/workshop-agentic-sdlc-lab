"""Integration tests for parse_usage and score working together."""

from __future__ import annotations

from usage import Result, parse_usage, score

FIXTURE_CSV = """account_id,month,seats_active,logins,tickets_open
hooli,2026-01,12,40,0
hooli,2026-02,12,45,1
acme,2026-01,10,5,0
acme,2026-02,8,5,0
acme,2026-03,,5,0
globex,2026-01,4,5,0
globex,2026-02,10,5,0
globex,2026-03,6,5,0
vandelay,2026-01,10,5,0
vandelay,2026-02,6,5,0
vandelay,2026-03,5,5,0
initech,2026-01,6,4,0
initech,2026-02,6,2,3
umbrella,2026-02,3,10,0
"""


def test_integration_full_fixture():
    parsed = parse_usage(FIXTURE_CSV)

    results = {account: score(months) for account, months in parsed.items()}

    assert results["hooli"] == Result(
        score=10,
        tier="HEALTHY",
        reasons=[],
    )
    assert results["acme"] == Result(
        score=6,  # D-1
        tier="MEDIUM",
        reasons=["seats down sharply"],  # D-1, D-2
    )
    assert results["globex"] == Result(
        score=6,  # D-1
        tier="MEDIUM",
        reasons=["seats down sharply"],  # D-1
    )
    assert results["vandelay"] == Result(
        score=6,  # D-1
        tier="MEDIUM",
        reasons=["seats down sharply"],  # D-1
    )
    assert results["initech"] == Result(
        score=5,  # D-3
        tier="MEDIUM",  # D-3
        reasons=["low engagement", "unresolved support load"],  # D-3
    )
    assert results["umbrella"] == Result(
        score=10,
        tier="HEALTHY",
        reasons=[],
    )


def test_integration_unsorted_csv_rows_compose():
    csv_text = """account_id,month,seats_active,logins,tickets_open
vandelay,2026-03,5,5,0
vandelay,2026-01,10,5,0
vandelay,2026-02,6,5,0
"""
    parsed = parse_usage(csv_text)
    result = score(parsed["vandelay"])
    assert result == Result(
        score=6,  # D-1
        tier="MEDIUM",
        reasons=["seats down sharply"],  # D-1
    )


def test_integration_at_risk_account_composition():
    csv_text = """account_id,month,seats_active,logins,tickets_open
troubled,2026-01,20,10,0
troubled,2026-02,5,1,3
"""
    parsed = parse_usage(csv_text)
    result = score(parsed["troubled"])
    assert result == Result(
        score=1,  # D-1
        tier="AT RISK",
        reasons=["seats down sharply", "low engagement", "unresolved support load"],  # D-1
    )
