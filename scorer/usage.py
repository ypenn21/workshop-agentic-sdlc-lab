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

    f = io.StringIO(csv_text.strip())
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        return {}

    by_account: dict[str, list[MonthSnapshot]] = {}
    for row in reader:
        account_id = row.get("account_id")
        month = row.get("month")
        if account_id is None or month is None:
            continue
        account_id = account_id.strip()
        month = month.strip()
        if not account_id or not month:
            continue

        def _parse_int(val: str | None) -> int:
            if val is None or not val.strip():
                return 0
            return int(val.strip())

        seats_active = _parse_int(row.get("seats_active"))
        logins = _parse_int(row.get("logins"))
        tickets_open = _parse_int(row.get("tickets_open"))

        snapshot = MonthSnapshot(
            account_id=account_id,
            month=month,
            seats_active=seats_active,
            logins=logins,
            tickets_open=tickets_open,
        )
        by_account.setdefault(account_id, []).append(snapshot)

    for acct in by_account:
        by_account[acct].sort(key=lambda m: m.month)

    return by_account


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    if not months:
        raise ValueError("months list cannot be empty")

    current_score = 10
    reasons: list[str] = []

    # Rule 1: Seat decline rule
    if len(months) >= 2:
        latest = months[-1]
        prior_peak = max(m.seats_active for m in months[:-1])
        if prior_peak > 0:
            drop_ratio = (prior_peak - latest.seats_active) / prior_peak
            if drop_ratio >= 0.40:
                current_score -= 4
                reasons.append("seats down sharply")

    # Rule 2: Low engagement
    latest = months[-1]
    if latest.logins < 3:
        current_score -= 3
        reasons.append("low engagement")

    # Rule 3: Unresolved support load
    if latest.tickets_open >= 2:
        current_score -= 2
        reasons.append("unresolved support load")

    # Determine tier
    if current_score >= 8:
        tier = "HEALTHY"
    elif current_score >= 5:
        tier = "MEDIUM"
    else:
        tier = "AT RISK"

    return Result(score=current_score, tier=tier, reasons=reasons)
