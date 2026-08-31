"""Interface and data structures for account health scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonthSnapshot:
    account_id: str
    month: str          # "YYYY-MM"
    seats_active: int   # >= 0, blank in CSV parsed as 0
    logins: int         # >= 0
    tickets_open: int   # >= 0


@dataclass(frozen=True)
class Result:
    score: int          # 0..10 inclusive
    tier: str           # "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]  # Ordered deduction reasons that fired


def parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]:
    """Group export text by account, each list in ascending month order."""
    raise NotImplementedError


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's chronological months. Never reads CSV or filesystem."""
    raise NotImplementedError
