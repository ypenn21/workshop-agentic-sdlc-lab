"""Interface and data structures for account health scoring."""

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
    if not csv_text or not csv_text.strip():
        return {}

    import csv
    import io
    from collections import defaultdict

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return {}

    grouped: dict[str, list[MonthSnapshot]] = defaultdict(list)
    for row in reader:
        account_id = row.get("account_id", "").strip() if row.get("account_id") else ""
        if not account_id:
            continue

        month = row.get("month", "").strip() if row.get("month") else ""

        seats_raw = row.get("seats_active")
        seats_active = int(seats_raw.strip()) if seats_raw is not None and seats_raw.strip() else 0

        logins_raw = row.get("logins")
        logins = int(logins_raw.strip()) if logins_raw is not None and logins_raw.strip() else 0

        tickets_raw = row.get("tickets_open")
        tickets_open = int(tickets_raw.strip()) if tickets_raw is not None and tickets_raw.strip() else 0

        snapshot = MonthSnapshot(
            account_id=account_id,
            month=month,
            seats_active=seats_active,
            logins=logins,
            tickets_open=tickets_open,
        )
        grouped[account_id].append(snapshot)

    result: dict[str, list[MonthSnapshot]] = {}
    for account_id, snapshots in grouped.items():
        if snapshots:
            snapshots.sort(key=lambda s: s.month)
            result[account_id] = snapshots

    return result


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    if not months:
        return Result(score=10, tier="HEALTHY", reasons=[])

    reasons: list[str] = []
    current_score = 10

    # 1. Seat Decline Rule (-4 points, reason: "seats down sharply")
    if len(months) >= 2:
        prior_peak = max(m.seats_active for m in months[:-1])
        if prior_peak > 0:
            latest_seats = months[-1].seats_active
            if (prior_peak - latest_seats) / prior_peak >= 0.40:
                current_score -= 4
                reasons.append("seats down sharply")

    # 2. Low Engagement Rule (-3 points, reason: "low engagement")
    if months[-1].logins < 3:
        current_score -= 3
        reasons.append("low engagement")

    # 3. Unresolved Support Load Rule (-2 points, reason: "unresolved support load")
    if months[-1].tickets_open >= 2:
        current_score -= 2
        reasons.append("unresolved support load")

    current_score = max(0, current_score)

    if current_score >= 8:
        tier = "HEALTHY"
    elif current_score >= 5:
        tier = "MEDIUM"
    else:
        tier = "AT RISK"

    return Result(score=current_score, tier=tier, reasons=reasons)

