# Account Health Scorer

**Status:** Approved

## What this does

Customer Success teams need an early warning signal before unhappy accounts reach churn and cancellation. This service processes monthly account usage export data, computes a deterministic health score from 0 to 10 floored at 0, classifies each account into an actionable risk tier (`HEALTHY`, `MEDIUM`, `AT RISK`), and emits an ordered list of human-readable deduction reason strings so CSMs can take immediate, targeted action.

## Input

Raw CSV text containing monthly account usage records.

### CSV Header & Column Schema
Header: `account_id,month,seats_active,logins,tickets_open`

- `account_id` (`str`): Unique account identifier (non-empty string).
- `month` (`str`): Calendar month formatted as `YYYY-MM`.
- `seats_active` (`int`): Count of active seats. If blank/empty in the CSV row, it is coerced to `0`.
- `logins` (`int`): Total user logins during the month (non-negative integer).
- `tickets_open` (`int`): Count of unresolved support tickets during the month (non-negative integer).

### Ingestion Guarantees
- Input rows may arrive in arbitrary order.
- `parse_usage()` groups snapshots by `account_id` and guarantees snapshots within each account list are sorted in ascending chronological order by `month`.
- Empty CSV text or CSV text with only a header row returns an empty mapping `{}`.

## The two halves

The system separates pure domain logic from filesystem I/O. All scoring and parsing operations reside in `scorer/usage.py` and are completely decoupled from filesystem, network, or environment operations. Filesystem I/O and CLI presentation reside strictly in `scorer/main.py`.

```python
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
    ...


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's months. Never reads the CSV."""
    ...
```

## Rules

1. **Baseline Score:** Every account starts with a baseline score of `10` points.
2. **Score Floor:** `Result.score` is floored at `0` (cannot be negative).
3. **Seat Decline Rule (−4 points, reason: `"seats down sharply"`):**
   - Fires if the latest month's `seats_active` is 40% or more ($\ge 40\%$) below the maximum `seats_active` across all *prior* recorded months for that account: `(peak - latest) / peak >= 0.40`.
   - Single-month accounts are exempt and do not trigger this rule.
4. **Low Engagement Rule (−3 points, reason: `"low engagement"`):**
   - Fires if `logins < 3` in the latest month.
5. **Unresolved Support Load Rule (−2 points, reason: `"unresolved support load"`):**
   - Fires if `tickets_open >= 2` in the latest month.
6. **Deduction Reason Canonical Order & Uniqueness:**
   - Reasons must appear in the exact order of rule evaluation: `"seats down sharply"`, `"low engagement"`, `"unresolved support load"`.
   - Each rule fires at most once per scoring evaluation.
7. **Tier Classification:**
   - `8` – `10`: `"HEALTHY"`
   - `5` – `7`: `"MEDIUM"`
   - `0` – `4`: `"AT RISK"`

## Out of scope

- Direct file I/O, network requests, or environment access within `scorer/usage.py`.
- Automated alerting (e.g., Slack webhooks, email triggers).
- CRM synchronization (e.g., Salesforce, HubSpot integration).
- Database persistence or schema migrations.

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| --- | --- | --- | --- |
| D-1 | Seat decline compares the latest month's seats to the maximum peak across all *prior* recorded months. If decline $\ge 40\%$, deduct 4 points. Single-month accounts are exempt. | "fallen by 40% or more compared to peak" | An account with 10 seats in month 1, 6 in month 2, and 5 in month 3 compares 5 against peak 10 (50% drop, triggers), rather than against month 2 (6 to 5 is 16.7% drop, would not trigger). Single-month accounts never trigger. |
| D-2 | A blank or missing `seats_active` value in CSV is coerced to integer `0`. `MonthSnapshot.seats_active` is strictly typed as `int`. | "seats in use... That export is what we have" | A row `acme,2026-03,,5,0` parses `seats_active` as `0` instead of raising a ValueError, returning `None`, or dropping the row. |
| D-3 | Score tiers are strictly bounded by numeric thresholds: `HEALTHY` (8–10), `MEDIUM` (5–7), `AT RISK` (0–4). Score 5 is `MEDIUM`. | "which accounts to call this week, and why" | An account scoring exactly 5 points is categorized as `MEDIUM` rather than `AT RISK`. |

## Open questions

None.

## The gate

Code starts when all three hold:

- **Status** is `Approved`
- **Open questions** is empty
- Every rule, in Rules and in Decisions, is one a builder could follow without asking anybody
