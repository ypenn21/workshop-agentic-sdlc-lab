"""Integration tests composing parse_usage() and score().

Tests the end-to-end flow from CSV input to evaluated Result objects.
"""

from main import load_export
from usage import parse_usage, score


def test_integration_fixture_composition():
    csv_text = load_export()
    accounts = parse_usage(csv_text)

    # All accounts in fixtures are present
    assert set(accounts.keys()) == {
        "acme",
        "globex",
        "hooli",
        "initech",
        "umbrella",
        "vandelay",
    }

    # hooli: 12 seats -> 12 seats, 45 logins, 1 ticket -> Score 10, HEALTHY, []
    hooli_res = score(accounts["hooli"])
    assert hooli_res.score == 10
    assert hooli_res.tier == "HEALTHY"
    assert hooli_res.reasons == []

    # acme: 10 -> 8 -> 0 (blank), 5 logins, 0 tickets -> Score 4 (due to seat drop -4), AT RISK, ["seats down sharply"]
    acme_res = score(accounts["acme"])
    assert acme_res.score == 6  # 10 - 4 = 6
    assert acme_res.tier == "MEDIUM"
    assert acme_res.reasons == ["seats down sharply"]

    # globex: 4 -> 10 -> 6, 5 logins, 0 tickets -> 40% drop from peak 10 -> Score 6, MEDIUM, ["seats down sharply"]
    globex_res = score(accounts["globex"])
    assert globex_res.score == 6
    assert globex_res.tier == "MEDIUM"
    assert globex_res.reasons == ["seats down sharply"]

    # initech: 6 -> 6 seats, 2 logins, 3 tickets -> Score 5 (10 - 3 - 2 = 5), MEDIUM, ["low engagement", "unresolved support load"]
    initech_res = score(accounts["initech"])
    assert initech_res.score == 5
    assert initech_res.tier == "MEDIUM"
    assert initech_res.reasons == ["low engagement", "unresolved support load"]

    # umbrella: 1 month (3 seats, 10 logins, 0 tickets) -> Score 10, HEALTHY, []
    umbrella_res = score(accounts["umbrella"])
    assert umbrella_res.score == 10
    assert umbrella_res.tier == "HEALTHY"
    assert umbrella_res.reasons == []

    # vandelay: 10 -> 6 -> 5 seats (50% drop from peak 10), 5 logins, 0 tickets -> Score 6, MEDIUM, ["seats down sharply"]
    vandelay_res = score(accounts["vandelay"])
    assert vandelay_res.score == 6
    assert vandelay_res.tier == "MEDIUM"
    assert vandelay_res.reasons == ["seats down sharply"]
