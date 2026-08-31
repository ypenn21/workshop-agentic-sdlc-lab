# Account Health Scorer Spec

**Status:** `Approved`

## What this does

Customer Success finds out an account is in trouble when the cancellation email arrives. By then the renewal conversation is already a save conversation, and we lose most of those. This service reads the monthly usage export, gives each account an explainable health score, places it in a risk tier, and attaches actionable reasons so CS can proactively work a prioritized list each Monday morning.

## Input

The monthly usage export as raw CSV text (`fixtures/usage.csv`).
- Header: `account_id,month,seats_active,logins,tickets_open`
- `account_id`: string identifier (e.g. `hooli`, `acme`)
- `month`: calendar month string in `YYYY-MM` format (e.g. `2026-01`)
- `seats_active`: non-negative integer or blank/whitespace (blank parses as `0`)
- `logins`: non-negative integer (always populated)
- `tickets_open`: non-negative integer (always populated)
- Each account has at most one row per month. Rows in the CSV can arrive in any order.

## The two halves

The system is partitioned into two pure functions in `scorer/usage.py`:

```python
@dataclass(frozen=True)
class MonthSnapshot:
    account_id: str
    month: str          # "YYYY-MM"
    seats_active: int   # blank parses as 0
    logins: int
    tickets_open: int


@dataclass(frozen=True)
class Result:
    score: int          # 0..10 (baseline starts at 10, floored at 0)
    tier: str           # "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]  # Ordered list of reasons that fired


def parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]:
    """Group export text by account, each list in ascending month order."""


def score(months: list[MonthSnapshot]) -> Result:
    """Score one account's chronological months. Never reads the CSV."""
```

The CLI entry point `scorer/main.py` owns reading the CSV file, calling `parse_usage()`, calling `score()` for each account, and formatting the output.

## Rules

### 1. Parsing Rules (`parse_usage`)
- Groups rows by `account_id`.
- Sorts each account's `MonthSnapshot` list in strictly ascending chronological order by `month` (`YYYY-MM`).
- Parses blank or whitespace `seats_active` values as integer `0`.
- Omits accounts with no recorded months (empty CSV returns `{}`).

### 2. Scoring Rules (`score`)
Baseline score starts at **10 points**. Deductions are evaluated on the latest recorded month (`months[-1]`):
1. **Seat Decline (−4 points, reason: `"seats down sharply"`):** Latest month's `seats_active` has fallen by 40% or more compared to the peak `seats_active` across all prior recorded months (`months[:-1]`). Single-month accounts are exempt and do not trigger this rule.
2. **Low Engagement (−3 points, reason: `"low engagement"`):** Fewer than 3 logins in the latest month (`logins < 3`).
3. **Unresolved Support Load (−2 points, reason: `"unresolved support load"`):** 2 or more tickets open in the latest month (`tickets_open >= 2`).

### 3. Tier Classification Rules
- `"HEALTHY"`: Score 8 – 10
- `"MEDIUM"`: Score 5 – 7
- `"AT RISK"`: Score 0 – 4

### 4. Reason Ordering & Score Bounds
- `reasons` list strictly preserves the evaluation order: `["seats down sharply", "low engagement", "unresolved support load"]`.
- The final score is floored at `0` (`max(0, calculated_score)`).

## Out of scope

- Direct filesystem/network I/O inside `scorer/usage.py`.
- Multi-quarter custom metric weighting or dynamic churn regression models.
- Automated Slack/email notification dispatching.

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| --- | --- | --- | --- |
| **D-1** | Blank or whitespace `seats_active` values in CSV parse to `0`. | "seats in use, logins, and open support tickets. That export is what we have." | Blank string causes `ValueError` or parses to `None`. |
| **D-2** | `parse_usage` sorts each account's months in ascending chronological order (`YYYY-MM`). | "reads the monthly usage export" | Unordered rows cause latest month evaluation to be non-deterministic. |
| **D-3** | Accounts with only a single recorded month do not trigger the seat decline deduction. | "fallen by 40% or more compared to peak across prior months" | New accounts with 1 month would error or falsely trigger seat drop. |
| **D-4** | Seat decline compares latest seats against the maximum peak seats across ALL prior months (`months[:-1]`). | "peak seat count across all prior recorded months" | Comparing only to immediately preceding month misses stepped churn. |
| **D-5** | Seat decline triggers when latest seats `<= 0.60 * peak_prior_seats` (drop `>= 40%`, −4 pts, `"seats down sharply"`). | "fallen by 40% or more" | Exact 40% drop (e.g. 10 -> 6) boundary missed if strict inequality used. |
| **D-6** | Low engagement triggers when latest month `logins < 3` (−3 pts, `"low engagement"`). | "fewer than 3 logins" | Accounts with exactly 3 logins penalized if `<=` used. |
| **D-7** | Unresolved support load triggers when latest month `tickets_open >= 2` (−2 pts, `"unresolved support load"`). | "2 or more tickets open" | Accounts with 2 tickets not penalized if `>` used. |
| **D-8** | `Result.reasons` strictly maintains order: `["seats down sharply", "low engagement", "unresolved support load"]`. | "names the reasons, so CS can work a list" | Non-deterministic reason list ordering across runs. |
| **D-9** | Tier mapping: 8–10 = `"HEALTHY"`, 5–7 = `"MEDIUM"`, 0–4 = `"AT RISK"`. | "puts it in a tier" | Discrepancy at boundary scores 5 and 8. |
| **D-10** | Final score is floored at `0` (`max(0, 10 - deductions)`). | "health score (floored at 0, starting at 10)" | Accumulated deductions result in negative score. |
| **D-11** | Accounts with no data rows return no keys in `parse_usage` dictionary. | "An account with no months to score is omitted" | Empty list passed to `score([])` causing index errors. |

## Open questions

*(None — all decisions resolved and approved)*

## The gate

- **Status** is `Approved`
- **Open questions** is empty
- Every rule, in Rules and in Decisions, is one a builder could follow without asking anybody
