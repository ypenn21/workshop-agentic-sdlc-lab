from __future__ import annotations

from main import load_export
from usage import Result, parse_usage, score


def test_integration_full_pipeline_on_fixture():
    csv_text = load_export()
    accounts = parse_usage(csv_text)

    results = {account: score(months) for account, months in accounts.items()}

    assert results == {
        "acme": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D03
        "globex": Result(score=10, tier="HEALTHY", reasons=[]),  # D01
        "hooli": Result(score=10, tier="HEALTHY", reasons=[]),
        "initech": Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"]),  # D02
        "umbrella": Result(score=10, tier="HEALTHY", reasons=[]),
        "vandelay": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D01
    }
