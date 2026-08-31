"""Integration contract tests composing parse_usage() and score().

Verifies end-to-end scoring pipeline across the fixture export.
Every assertion derives directly from a decision recorded in docs/spec.md.
"""

from pathlib import Path
from usage import parse_usage, score

FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "usage.csv"


def test_integration_fixture_composition():
    csv_text = FIXTURE_PATH.read_text(encoding="utf-8")
    parsed_accounts = parse_usage(csv_text)

    # 1. acme: blank seat parsed as 0 (D-1), drop from peak 10 -> 0 <= 6 (D-4)
    acme_result = score(parsed_accounts["acme"])
    assert acme_result.score == 6  # D-7
    assert acme_result.tier == "MEDIUM"  # D-8
    assert acme_result.reasons == ["seats down sharply"]  # D-4, D-9

    # 2. globex: out of order months sorted (D-2), drop from peak 10 -> 6 <= 6 (D-4)
    globex_result = score(parsed_accounts["globex"])
    assert globex_result.score == 6  # D-7
    assert globex_result.tier == "MEDIUM"  # D-8
    assert globex_result.reasons == ["seats down sharply"]  # D-4, D-9

    # 3. hooli: healthy baseline
    hooli_result = score(parsed_accounts["hooli"])
    assert hooli_result.score == 10  # D-7
    assert hooli_result.tier == "HEALTHY"  # D-8
    assert hooli_result.reasons == []  # D-9

    # 4. initech: low engagement (D-5) + unresolved support load (D-6)
    initech_result = score(parsed_accounts["initech"])
    assert initech_result.score == 5  # D-7
    assert initech_result.tier == "MEDIUM"  # D-8
    assert initech_result.reasons == [
        "low engagement",
        "unresolved support load",
    ]  # D-9

    # 5. umbrella: single-month account (D-3)
    umbrella_result = score(parsed_accounts["umbrella"])
    assert umbrella_result.score == 10  # D-7
    assert umbrella_result.tier == "HEALTHY"  # D-8
    assert umbrella_result.reasons == []  # D-3, D-9

    # 6. vandelay: seat drop from peak 10 -> 5 <= 6 (D-4)
    vandelay_result = score(parsed_accounts["vandelay"])
    assert vandelay_result.score == 6  # D-7
    assert vandelay_result.tier == "MEDIUM"  # D-8
    assert vandelay_result.reasons == ["seats down sharply"]  # D-4, D-9
