from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonthSnapshot:
    account_id: str
    month: str          # "YYYY-MM"
    seats_active: int
    logins: int
    tickets_open: int


@dataclass(frozen=True)
class Result:
    score: int
    tier: str           # "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]


def parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]:
    """Group the export text by account, each list in ascending month order.

    An account with no months to score is omitted, so score() is never
    called with an empty list.
    """
    raise NotImplementedError


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    raise NotImplementedError
