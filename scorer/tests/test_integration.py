"""Integration tests composing parse_usage and score (scorer/usage.py)."""

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


def test_integration_parse_and_score_all_fixture_accounts() -> None:
    parsed = parse_usage(FIXTURE_CSV)

    results = {account: score(months) for account, months in parsed.items()}

    assert results["hooli"] == Result(score=10, tier="HEALTHY", reasons=[])  # D-3
    assert results["acme"] == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-2, D-3
    assert results["globex"] == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-3
    assert results["vandelay"] == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-3
    assert results["initech"] == Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"])  # D-3
    assert results["umbrella"] == Result(score=10, tier="HEALTHY", reasons=[])  # D-1, D-3


def test_integration_handles_unsorted_rows_and_coerced_blanks() -> None:
    raw_csv = """account_id,month,seats_active,logins,tickets_open
acme,2026-03,,5,0
acme,2026-01,10,5,0
acme,2026-02,8,5,0
"""
    parsed = parse_usage(raw_csv)
    result = score(parsed["acme"])

    assert result == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-2, D-3
