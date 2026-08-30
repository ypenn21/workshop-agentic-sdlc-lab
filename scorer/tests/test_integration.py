"""Integration tests for the account health scoring pipeline.

Verifies the composition of parse_usage() and score() on fixtures/usage.csv.
"""

from __future__ import annotations

from main import load_export
from usage import Result, parse_usage, score


def test_integration_scoring_pipeline_on_fixture():
    csv_text = load_export()
    parsed = parse_usage(csv_text)

    results = {account: score(months) for account, months in parsed.items()}

    # acme: 10 -> 8 -> 0 seats (drop >= 40%) -> 6 MEDIUM ['seats down sharply']
    assert results["acme"] == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-4, D-11

    # globex: 4 -> 10 -> 6 seats (prior peak 10, latest 6 -> 40% drop) -> 6 MEDIUM ['seats down sharply']
    assert results["globex"] == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-4, D-11

    # hooli: 12 -> 12 seats, 45 logins, 1 ticket -> 10 HEALTHY []
    assert results["hooli"] == Result(score=10, tier="HEALTHY", reasons=[])  # D-11

    # initech: 6 -> 6 seats, 2 logins (-3), 3 tickets (-2) -> 5 MEDIUM ['low engagement', 'unresolved support load']
    assert results["initech"] == Result(
        score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"]
    )  # D-7, D-8, D-9, D-11

    # umbrella: 1 month, 3 seats, 10 logins, 0 tickets -> 10 HEALTHY [] (exempt from seat decline)
    assert results["umbrella"] == Result(score=10, tier="HEALTHY", reasons=[])  # D-5, D-11

    # vandelay: 10 -> 6 -> 5 seats (prior peak 10, latest 5 -> 50% drop) -> 6 MEDIUM ['seats down sharply']
    assert results["vandelay"] == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-4, D-11
