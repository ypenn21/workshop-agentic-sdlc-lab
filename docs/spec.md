# Account Health Scoring

**Status:** Approved

## What this does

Customer Success teams currently discover account dissatisfaction only when cancellation emails arrive, making renewal conversations reactive save attempts with low win rates. This feature provides an automated, deterministic account health scoring engine that analyzes monthly usage exports to identify at-risk accounts early. It equips CSMs with an actionable weekly Monday morning list featuring health scores, risk tiers, and explicit deduction reasons explaining why each account was flagged.

## Input

A CSV-formatted string export of historical monthly account usage data with a header row.
- **Columns:**
  - `account_id` (string, e.g., `"acme"`, `"hooli"`, `"initech"`)
  - `month` (string, ISO format `"YYYY-MM"`, e.g., `"2026-01"`, `"2026-02"`)
  - `seats_active` (integer represented as string; blank/empty string `""` coerced to `0`)
  - `logins` (integer represented as string, e.g., `"5"`, `"40"`)
  - `tickets_open` (integer represented as string, e.g., `"0"`, `"3"`)
- **Guarantees:**
  - `account_id`, `month`, `logins`, and `tickets_open` are non-empty and well-formed.
  - Each account has at most one record per month in the CSV export.
  - `seats_active` may be empty/blank (`""` or whitespace), which must be parsed as `0`.
  - Rows for an account may appear out of chronological order in the raw CSV string.

## The two halves

The system is decomposed into two pure functional interfaces in `scorer/usage.py` that have no dependencies on the filesystem, network, or external state:

### 1. Data Structures
```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MonthSnapshot:
    account_id: str
    month: str          # "YYYY-MM"
    seats_active: int   # blank in CSV parsed as 0
    logins: int
    tickets_open: int

@dataclass(frozen=True)
class Result:
    score: int          # starting at 10, floored at 0
    tier: str           # "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]  # ordered list of deduction reasons
```

### 2. Functional Signatures
```python
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

### Module Responsibilities
- `scorer/usage.py`: Contains pure domain models (`MonthSnapshot`, `Result`) and pure functions (`parse_usage`, `score`). Strictly forbidden from importing `os`, `pathlib`, `open`, or performing I/O.
- `scorer/main.py`: CLI entry point; handles file I/O (`load_export()`), loads `fixtures/usage.csv`, coordinates parsing and scoring, and formats terminal tabular reports.

## Rules

### 1. Ingestion & Parsing Rules (`parse_usage`)
- Parse the input CSV string into `MonthSnapshot` instances grouped by `account_id` into a dictionary `dict[str, list[MonthSnapshot]]`.
- If `seats_active` is blank or whitespace, coerce its value to integer `0`.
- For each account, sort the list of `MonthSnapshot` objects in strict ascending chronological order based on the `month` attribute (`YYYY-MM`).
- Omit accounts with zero monthly snapshots from the returned dictionary. If the CSV text is empty or contains only a header line, return an empty dictionary `{}`.

### 2. Scoring Logic Rules (`score`)
- **Base Score:** Every account starts with a baseline score of `10` points.
- **Deduction 1: Seat Decline (−4 points, reason: `"seats down sharply"`)**:
  - Evaluate only if the account has 2 or more recorded months (`len(months) >= 2`). Single-month accounts are exempt.
  - Calculate `prior_peak_seats = max(m.seats_active for m in months[:-1])`. The latest month is strictly excluded from the prior peak calculation.
  - If `prior_peak_seats > 0` and `latest_month.seats_active <= 0.6 * prior_peak_seats` (a decline of 40% or more from prior peak), deduct `4` points and record reason `"seats down sharply"`.
  - If `prior_peak_seats == 0`, no seat decline deduction is applied.
- **Deduction 2: Low Engagement (−3 points, reason: `"low engagement"`)**:
  - If `latest_month.logins < 3`, deduct `3` points and record reason `"low engagement"`.
- **Deduction 3: Unresolved Support Load (−2 points, reason: `"unresolved support load"`)**:
  - If `latest_month.tickets_open >= 2`, deduct `2` points and record reason `"unresolved support load"`.
- **Score Floor:** The final score is floored at `0`: `score = max(0, 10 - total_deductions)`.
- **Deterministic Reason Ordering:** Deduction reasons must appear in `Result.reasons` in the canonical sequence:
  1. `"seats down sharply"`
  2. `"low engagement"`
  3. `"unresolved support load"`
- **Health Tier Classification:**
  - `score >= 8`: Tier is `"HEALTHY"`
  - `5 <= score <= 7`: Tier is `"MEDIUM"`
  - `score <= 4`: Tier is `"AT RISK"`

## Out of scope

- Direct database connectivity, ORM integration, or external API networking.
- Real-time event streaming, webhook triggers, or automated email dispatching.
- Multi-tenant authentication, authorization, or user role management.
- Modifying CSV files on disk or writing persistence layers.
- Custom score weighting configuration or user-defined dynamic threshold rules.

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| :--- | :--- | :--- | :--- |
| **D-1** | Blank or whitespace-only values in `seats_active` must be parsed as integer `0`. | "seats_active (blank in CSV is parsed as 0)" | Row `acme,2026-03,,5,0` is parsed with `seats_active=0` instead of raising `ValueError` or setting `None`. |
| **D-2** | Snapshots for each account must be strictly sorted in ascending chronological order by `month` (`YYYY-MM`). | "each list in ascending month order" | Account rows appearing out of order in CSV (`2026-03`, `2026-01`, `2026-02`) are sorted as `[2026-01, 2026-02, 2026-03]`. |
| **D-3** | Accounts with no valid monthly records are omitted from output; header-only or empty CSV text returns an empty dictionary `{}`. | "An account with no months to score is omitted" | Input `""` or `"account_id,month,seats_active,logins,tickets_open\n"` returns `{}` rather than erroring. |
| **D-4** | Seat decline (−4 points) triggers if `latest_seats <= 0.6 * prior_peak_seats` where `prior_peak = max(m.seats_active for m in months[:-1])`. | "fallen by 40% or more compared to peak seat count across all prior recorded months" | Account with months [4, 10, 6] has prior peak 10, latest 6 (40% drop from 10), triggering deduction (−4). |
| **D-5** | Accounts with exactly 1 month of history are exempt from seat decline rule regardless of seat count. | "Single-month accounts do not trigger this rule" | Single-month account `umbrella` (3 seats) has 0 prior months and does not trigger `"seats down sharply"`. |
| **D-6** | If peak seats across prior months is 0 (`prior_peak == 0`), seat decline rule does not fire. | "Zero prior peak seats does not trigger seat decline" | Account with prior seats 0 and latest seats 0 does not trigger `"seats down sharply"`. |
| **D-7** | Low engagement (−3 points, `"low engagement"`) fires if `latest_month.logins < 3`. | "Fewer than 3 logins in the latest month" | Account with 2 logins in latest month triggers −3 deduction; 3 logins does not trigger deduction. |
| **D-8** | Unresolved support load (−2 points, `"unresolved support load"`) fires if `latest_month.tickets_open >= 2`. | "2 or more tickets open in the latest month" | Account with 2 open tickets triggers −2 deduction; 1 open ticket does not trigger deduction. |
| **D-9** | Base score starts at 10; reasons list must strictly follow canonical sequence: 1. `"seats down sharply"`, 2. `"low engagement"`, 3. `"unresolved support load"`. | "starting at 10... ordered list of reasons for deductions that fired" | Account `initech` with all deductions active produces `score=1`, `tier="AT RISK"`, `reasons=["seats down sharply", "low engagement", "unresolved support load"]`. |
| **D-10** | Final score is floored at 0 (`max(0, 10 - total_deductions)`). | "floored at 0, starting at 10" | An account with cumulative deductions >= 10 receives score 0 and tier `"AT RISK"`. |
| **D-11** | Health tiers are strictly bounded: 8–10 is `"HEALTHY"`, 5–7 is `"MEDIUM"`, 0–4 is `"AT RISK"`. | `"HEALTHY": 8–10, "MEDIUM": 5–7, "AT RISK": 0–4` | Score 8 is `"HEALTHY"`, score 7 is `"MEDIUM"`, score 5 is `"MEDIUM"`, score 4 is `"AT RISK"`. |
| **D-12** | Pure function discipline: `scorer/usage.py` must perform zero file, network, or filesystem I/O. File reading belongs exclusively in `scorer/main.py`. | "Pure function discipline: scorer/usage.py must NEVER import os, pathlib, open" | `parse_usage()` accepts `csv_text: str` and returns in-memory structures without reading from disk. |

## Open questions

None.

## The gate

- **Status** is `Approved`
- **Open questions** is empty
- Every rule in Rules and Decisions is directly implementable without assumptions
