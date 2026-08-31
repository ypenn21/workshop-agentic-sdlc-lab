"""Interface and data structures for account health scoring."""

from __future__ import annotations

import csv
import io
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
    if not csv_text or not csv_text.strip():
        return {}

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return {}

    accounts: dict[str, list[MonthSnapshot]] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for row in reader:
        if not row or not any(v.strip() for v in row.values() if v):
            continue

        account_id = (row.get("account_id") or "").strip()
        month = (row.get("month") or "").strip()
        if not account_id or not month:
            raise ValueError("Missing account_id or month")

        pair = (account_id, month)
        if pair in seen_pairs:
            raise ValueError(f"Duplicate record for account {account_id} and month {month}")
        seen_pairs.add(pair)

        seats_raw = row.get("seats_active")
        if seats_raw is None or seats_raw.strip() == "":
            seats_active = 0
        else:
            try:
                seats_active = int(seats_raw.strip())
            except ValueError:
                raise ValueError(f"Invalid seats_active value: {seats_raw}")
            if seats_active < 0:
                raise ValueError(f"Negative seats_active: {seats_active}")

        logins_raw = row.get("logins")
        if logins_raw is None or logins_raw.strip() == "":
            raise ValueError("Missing or blank logins value")
        try:
            logins = int(logins_raw.strip())
        except ValueError:
            raise ValueError(f"Invalid logins value: {logins_raw}")
        if logins < 0:
            raise ValueError(f"Negative logins: {logins}")

        tickets_raw = row.get("tickets_open")
        if tickets_raw is None or tickets_raw.strip() == "":
            raise ValueError("Missing or blank tickets_open value")
        try:
            tickets_open = int(tickets_raw.strip())
        except ValueError:
            raise ValueError(f"Invalid tickets_open value: {tickets_raw}")
        if tickets_open < 0:
            raise ValueError(f"Negative tickets_open: {tickets_open}")

        snapshot = MonthSnapshot(
            account_id=account_id,
            month=month,
            seats_active=seats_active,
            logins=logins,
            tickets_open=tickets_open,
        )

        if account_id not in accounts:
            accounts[account_id] = []
        accounts[account_id].append(snapshot)

    for account_id in accounts:
        accounts[account_id].sort(key=lambda s: s.month)

    return accounts


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's chronological months. Never reads CSV or filesystem."""
    if not months:
        raise ValueError("months must not be empty")

    latest_month = months[-1]
    total_deductions = 0
    reasons: list[str] = []

    # Rule 1: Seat Decline (-4 points, reason: "seats down sharply")
    if len(months) > 1:
        prior_months = months[:-1]
        peak_prior_seats = max(m.seats_active for m in prior_months)
        if peak_prior_seats > 0 and latest_month.seats_active <= peak_prior_seats * 0.60:
            total_deductions += 4
            reasons.append("seats down sharply")

    # Rule 2: Low Engagement (-3 points, reason: "low engagement")
    if latest_month.logins < 3:
        total_deductions += 3
        reasons.append("low engagement")

    # Rule 3: Unresolved Support Load (-2 points, reason: "unresolved support load")
    if latest_month.tickets_open >= 2:
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

