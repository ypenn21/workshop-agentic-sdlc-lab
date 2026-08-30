"""Interface and data structures for account health scoring."""

from __future__ import annotations

import csv
import io
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
    if not csv_text or not csv_text.strip():
        return {}

    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return {}

    grouped: dict[str, list[MonthSnapshot]] = {}

    for row in reader:
        if not row:
            continue
        account_id = row.get("account_id")
        if not account_id or not account_id.strip():
            continue

        account_id = account_id.strip()
        month = row.get("month", "").strip()

        raw_seats = row.get("seats_active", "")
        if raw_seats is None or raw_seats.strip() == "":
            seats_active = 0
        else:
            seats_active = int(raw_seats.strip())

        logins = int(row.get("logins", 0))
        tickets_open = int(row.get("tickets_open", 0))

        snapshot = MonthSnapshot(
            account_id=account_id,
            month=month,
            seats_active=seats_active,
            logins=logins,
            tickets_open=tickets_open,
        )

        if account_id not in grouped:
            grouped[account_id] = []
        grouped[account_id].append(snapshot)

    # Sort each account's snapshots chronologically by month YYYY-MM
    result: dict[str, list[MonthSnapshot]] = {}
    for account_id, snapshots in grouped.items():
        if snapshots:
            result[account_id] = sorted(snapshots, key=lambda s: s.month)

    return result


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    if not months:
        return Result(score=10, tier="HEALTHY", reasons=[])

    latest = months[-1]
    total_deductions = 0
    reasons: list[str] = []

    # Deduction 1: Seat Decline (-4 points, reason: "seats down sharply")
    if len(months) >= 2:
        prior_peak = max(m.seats_active for m in months[:-1])
        if prior_peak > 0 and latest.seats_active <= 0.6 * prior_peak:
            total_deductions += 4
            reasons.append("seats down sharply")

    # Deduction 2: Low Engagement (-3 points, reason: "low engagement")
    if latest.logins < 3:
        total_deductions += 3
        reasons.append("low engagement")

    # Deduction 3: Unresolved Support Load (-2 points, reason: "unresolved support load")
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

