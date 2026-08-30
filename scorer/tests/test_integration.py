"""Integration tests composing parser, scorer, and CLI formatting against canonical fixture.

Verifies that load_export() -> parse_usage() -> score() compose cleanly and produce
the exact expected account scores, tiers, and formatted terminal outputs.
"""

from __future__ import annotations

from main import FIXTURE, load_export
from usage import Result, parse_usage, score


def test_fixture_pipeline_end_to_end() -> None:
    """End-to-end integration across fixtures/usage.csv produces expected results for all accounts."""
    csv_text = load_export(FIXTURE)
    parsed = parse_usage(csv_text)

    expected_results: dict[str, Result] = {
        "acme": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D-1, D-5, D-8
        "globex": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D-5, D-8
        "hooli": Result(score=10, tier="HEALTHY", reasons=[]),  # D-4, D-8
        "initech": Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"]),  # D-6, D-7, D-8
        "umbrella": Result(score=10, tier="HEALTHY", reasons=[]),  # D-5, D-8
        "vandelay": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D-5, D-8
    }

    assert sorted(parsed.keys()) == sorted(expected_results.keys())  # D-10

    for account_id, expected in expected_results.items():
        actual = score(parsed[account_id])
        assert actual == expected, f"Mismatch for account {account_id}: actual={actual}, expected={expected}"


def test_cli_formatted_row_rendering() -> None:
    """CLI format string renders each account row with fixed column widths and comma-separated reasons."""
    csv_text = load_export(FIXTURE)
    parsed = parse_usage(csv_text)

    expected_lines = [
        "acme        6  MEDIUM   seats down sharply",
        "globex      6  MEDIUM   seats down sharply",
        "hooli      10  HEALTHY  -",
        "initech     5  MEDIUM   low engagement, unresolved support load",
        "umbrella   10  HEALTHY  -",
        "vandelay    6  MEDIUM   seats down sharply",
    ]

    rendered_lines = []
    for account, months in sorted(parsed.items()):  # D-10
        result = score(months)
        reasons = ", ".join(result.reasons) or "-"  # D-10
        rendered_lines.append(f"{account:<10} {result.score:>2}  {result.tier:<8} {reasons}")  # D-10

    assert rendered_lines == expected_lines  # D-10
