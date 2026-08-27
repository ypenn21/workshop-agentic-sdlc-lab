"""Integration contract tests verifying parse_usage and score composition."""

from usage import Result, parse_usage, score

FIXTURE = """account_id,month,seats_active,logins,tickets_open
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


def test_integration_pipeline_composition() -> None:
    """parse_usage and score compose end-to-end to produce exact account health results."""
    parsed = parse_usage(FIXTURE)
    results = {account: score(months) for account, months in parsed.items()}

    assert results == {
        "acme": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D-1, D-7, D-9
        "globex": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D-1, D-7
        "hooli": Result(score=10, tier="HEALTHY", reasons=[]),  # D-7
        "initech": Result(score=5, tier="MEDIUM", reasons=["low engagement", "unresolved support load"]),  # D-3, D-4, D-5, D-7
        "umbrella": Result(score=10, tier="HEALTHY", reasons=[]),  # D-2, D-7
        "vandelay": Result(score=6, tier="MEDIUM", reasons=["seats down sharply"]),  # D-1, D-7
    }
