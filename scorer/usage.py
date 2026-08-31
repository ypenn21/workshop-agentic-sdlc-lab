"""Interface and data structures for account health scoring."""

from __future__ import annotations

from dataclasses import dataclass


import csv
import io


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
    if not csv_text.strip():
        return {}

    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return {}

    accounts: dict[str, list[MonthSnapshot]] = {}
    for row in reader:
        account_id = row["account_id"].strip()
        if not account_id:
            continue
        seats_raw = row.get("seats_active", "")
        seats_str = seats_raw.strip() if seats_raw is not None else ""
        seats_active = int(seats_str) if seats_str else 0
        logins = int(row["logins"].strip())
        tickets_open = int(row["tickets_open"].strip())
        month = row["month"].strip()

        snapshot = MonthSnapshot(
            account_id=account_id,
            month=month,
            seats_active=seats_active,
            logins=logins,
            tickets_open=tickets_open,
        )
        accounts.setdefault(account_id, []).append(snapshot)

    for account_id in accounts:
        accounts[account_id].sort(key=lambda x: x.month)

    return accounts


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    if not months:
        raise ValueError("months list cannot be empty")

    latest = months[-1]
    deductions = 0
    reasons: list[str] = []

    # Rule 1: Seat Decline (-4 points, "seats down sharply")
    if len(months) >= 2:
        prior_peak = max(m.seats_active for m in months[:-1])
        if prior_peak > 0 and latest.seats_active * 10 <= 6 * prior_peak:
            deductions += 4
            reasons.append("seats down sharply")

    # Rule 2: Low Engagement (-3 points, "low engagement")
    if latest.logins < 3:
        deductions += 3
        reasons.append("low engagement")

    # Rule 3: Unresolved Support Load (-2 points, "unresolved support load")
    if latest.tickets_open >= 2:
        deductions += 2
        reasons.append("unresolved support load")

    calculated_score = max(0, 10 - deductions)

    if calculated_score >= 8:
        tier = "HEALTHY"
    elif calculated_score >= 5:
        tier = "MEDIUM"
    else:
        tier = "AT RISK"

    return Result(score=calculated_score, tier=tier, reasons=reasons)

