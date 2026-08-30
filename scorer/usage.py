"""Interface and data structures for account health scoring."""

from __future__ import annotations

import csv
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
    lines = [line for line in csv_text.splitlines() if line.strip()]
    if not lines:
        return {}

    reader = csv.DictReader(lines)
    records: dict[str, list[MonthSnapshot]] = {}

    for row in reader:
        account_id = row["account_id"].strip()
        if not account_id:
            continue
        month = row["month"].strip()

        seats_raw = row["seats_active"].strip() if row.get("seats_active") else ""
        seats_active = int(seats_raw) if seats_raw else 0

        logins = int(row["logins"].strip())
        tickets_open = int(row["tickets_open"].strip())

        snapshot = MonthSnapshot(
            account_id=account_id,
            month=month,
            seats_active=seats_active,
            logins=logins,
            tickets_open=tickets_open,
        )

        if account_id not in records:
            records[account_id] = []
        records[account_id].append(snapshot)

    for account_id in records:
        records[account_id].sort(key=lambda m: m.month)

    return records


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    if not months:
        raise ValueError("Cannot score empty month list")

    latest = months[-1]
    total_deductions = 0
    reasons: list[str] = []

    # Rule 1: Seat Contraction Rule (-4 points, "seats down sharply")
    if len(months) > 1:
        peak_prior = max(m.seats_active for m in months[:-1])
        if peak_prior > 0 and latest.seats_active <= 0.6 * peak_prior:
            total_deductions += 4
            reasons.append("seats down sharply")

    # Rule 2: Low Engagement Rule (-3 points, "low engagement")
    if latest.logins < 3:
        total_deductions += 3
        reasons.append("low engagement")

    # Rule 3: Unresolved Support Load Rule (-2 points, "unresolved support load")
    if latest.tickets_open >= 2:
        total_deductions += 2
        reasons.append("unresolved support load")

    final_score = max(0, 10 - total_deductions)

    if final_score >= 8:
        tier = "HEALTHY"
    elif final_score >= 5:
        tier = "MEDIUM"
    else:
        tier = "AT RISK"

    return Result(score=final_score, tier=tier, reasons=reasons)
