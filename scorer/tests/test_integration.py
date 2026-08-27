"""Integration acceptance tests for parse_usage and score composition."""

from main import load_export
from usage import Result, parse_usage, score


def test_end_to_end_scoring_from_fixture():
    export_text = load_export()
    accounts = parse_usage(export_text)

    # hooli: 10, HEALTHY, no deductions
    assert score(accounts["hooli"]) == Result(score=10, tier="HEALTHY", reasons=[])

    # acme: 6, MEDIUM, seats down sharply (blank seats parsed as 0)
    assert score(accounts["acme"]) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1, D-2

    # globex: 6, MEDIUM, seats down sharply (4 -> 10 -> 6, peak 10 to 6 is 40% drop)
    assert score(accounts["globex"]) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1

    # vandelay: 6, MEDIUM, seats down sharply (10 -> 6 -> 5, peak 10 to 5 is 50% drop)
    assert score(accounts["vandelay"]) == Result(score=6, tier="MEDIUM", reasons=["seats down sharply"])  # D-1

    # initech: 5, MEDIUM, low engagement and unresolved support load (score 5 is MEDIUM)
    assert score(accounts["initech"]) == Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"])  # D-3

    # umbrella: 10, HEALTHY, single month cannot fire seat decline
    assert score(accounts["umbrella"]) == Result(score=10, tier="HEALTHY", reasons=[])
