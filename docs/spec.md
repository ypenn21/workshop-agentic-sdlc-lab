# Account Health Scoring

**Status:** Approved

## What this does

Customer Success needs early detection when an account's health is deteriorating prior to cancellation and renewal cycles. This service ingests monthly usage metrics from CSV exports and computes deterministic 0–10 health scores, tiered risk classifications (`HEALTHY`, `MEDIUM`, `AT RISK`), and transparent, explainable deduction reasons. This enables Customer Success teams to prioritize weekly outreach and intervene on high-risk accounts with actionable context.

## Input

Raw monthly usage export delivered as CSV text and processed by `parse_usage(csv_text: str)`.

- **CSV Header:** `account_id,month,seats_active,logins,tickets_open`
- **Field Definitions:**
  - `account_id`: `str` — Customer account identifier (e.g. `"acme"`, `"hooli"`). Non-empty string.
  - `month`: `str` — Billing month formatted as ISO `"YYYY-MM"` (e.g. `"2026-01"`). Non-empty string.
  - `seats_active`: `int` — Active seat count for the recorded month. Blank or whitespace-only field is coerced to integer `0`. Non-negative integer.
  - `logins`: `int` — Total user logins recorded in that month. Non-empty, non-negative integer.
  - `tickets_open`: `int` — Unresolved support ticket count in that month. Non-empty, non-negative integer.
- **Guarantees:**
  - Each account has at most one record per calendar month in the CSV export.
  - Trailing empty lines and whitespace-only lines are ignored during ingestion.
  - Accounts with zero valid monthly rows are omitted from the returned mapping so that `score()` is never invoked with an empty list.

## The two halves

The system is strictly divided into two pure functions in `scorer/usage.py` and a separate CLI module in `scorer/main.py`.

### 1. Data Structures & Domain Models (`scorer/usage.py`)
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
    score: int          # 0..10
    tier: str           # "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]  # Ordered deduction reasons
```

### 2. Pure Interface Signatures (`scorer/usage.py`)
- `def parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]:`
  - Parses raw CSV string, extracts records, normalizes blank seat counts to `0`, groups records by `account_id`, and sorts each account's list in ascending chronological order by `month` (`YYYY-MM`).
  - Omits accounts with no months.
  - Never touches the filesystem.
- `def score(months: list[MonthSnapshot]) -> Result:`
  - Computes the health score, assigns the risk tier, and compiles ordered deduction reasons for a single account from its chronologically ordered monthly snapshots.
  - Raises `ValueError("Cannot score empty month list")` if `months` is empty.
  - Never reads CSV or performs I/O.

### 3. CLI Entry Point (`scorer/main.py`)
- `def load_export(path: Path | str = FIXTURE) -> str:`
  - Reads the CSV file from disk (`fixtures/usage.csv` by default).
- `def main() -> None:`
  - Loads export text, executes `parse_usage()`, iterates through accounts in alphabetical order, executes `score()`, and prints the formatted table:
    `{account:<10} {score:>2}  {tier:<8} {reasons}` where multiple reasons are joined with `", "` and empty reasons display `"-"`.

## Rules

A builder implements the scoring logic according to these deterministic rules:

1. **Base Score & Floor:** Every account begins with a baseline score of `10`. Total deductions are subtracted from the base score. The final score is floored at `0`:
   $$\text{score} = \max(0, 10 - \text{total\_deductions})$$
2. **Seat Contraction Rule (−4 points, reason: `"seats down sharply"`):**
   - Evaluates only if the account has prior history (`len(months) > 1`).
   - Identifies the maximum seats active across all prior months: $\text{peak\_prior} = \max(m.\text{seats\_active for } m \in \text{months[:-1]})$.
   - If $\text{peak\_prior} > 0$ and the latest month's seats active dropped by 40% or more ($\text{latest.seats\_active} \le 0.6 \times \text{peak\_prior}$), apply a 4-point deduction and append `"seats down sharply"` to `reasons`.
   - Single-month accounts (`len(months) == 1`) and accounts where $\text{peak\_prior} == 0$ are exempt and do not trigger this deduction.
3. **Low Engagement Rule (−3 points, reason: `"low engagement"`):**
   - Evaluates the latest month: if $\text{latest.logins} < 3$, apply a 3-point deduction and append `"low engagement"` to `reasons`.
4. **Unresolved Support Load Rule (−2 points, reason: `"unresolved support load"`):**
   - Evaluates the latest month: if $\text{latest.tickets\_open} \ge 2$, apply a 2-point deduction and append `"unresolved support load"` to `reasons`.
5. **Execution & Reason Ordering:**
   - Deductions are evaluated and appended to `Result.reasons` in fixed sequential order:
     1. `"seats down sharply"`
     2. `"low engagement"`
     3. `"unresolved support load"`
6. **Tier Thresholds:**
   - Score `8`, `9`, `10` $\rightarrow$ `"HEALTHY"`
   - Score `5`, `6`, `7` $\rightarrow$ `"MEDIUM"`
   - Score `0`, `1`, `2`, `3`, `4` $\rightarrow$ `"AT RISK"`
7. **Pure Function Discipline:**
   - `scorer/usage.py` must not import `os`, `pathlib`, `open`, or execute file or network operations.
8. **CLI Formatting & Output Ordering:**
   - Accounts are output in ascending alphabetical order.
   - Row format: `{account:<10} {score:>2}  {tier:<8} {reasons}`.
   - Empty deduction reasons are formatted as `"-"`. Multiple deduction reasons are joined with `", "`.

## Out of scope

- Automated notification dispatch (Slack webhooks, email alerts, or PagerDuty integration) in v1.0.0.
- Dynamic threshold tuning or custom per-account risk weighting.
- Direct database, SQL, or remote API ingestion (data is sourced exclusively from the CSV export).
- Modifying acceptance contract tests in `scorer/tests/` to accommodate flawed code.

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| --- | --- | --- | --- |
| **D-1** | `MonthSnapshot.seats_active` must parse to integer `0` when the CSV field is empty, blank, or contains only whitespace. | Input: "blank in CSV is parsed as 0" | Casting directly with `int(row["seats_active"])` crashes with `ValueError` on rows like `acme,2026-03,,5,0`. |
| **D-2** | `parse_usage()` must return each account's `MonthSnapshot` list sorted in ascending chronological order by `month` (`YYYY-MM`). | The two halves: "each list in ascending month order" | Unordered rows in CSV (e.g. `2026-03` before `2026-01`) would cause the parser to evaluate the wrong month as latest (`months[-1]`) and calculate incorrect peak prior seats. |
| **D-3** | Accounts with no valid monthly rows are omitted from the returned mapping; `parse_usage()` ignores trailing empty lines and whitespace-only rows. | The two halves: "An account with no months to score is omitted, so score() is never called with an empty list." | An account mapped to an empty list `[]` would cause `score([])` to raise an unhandled exception or fail in the CLI loop. |
| **D-4** | Base score starts at `10` and is floored at `0` using `max(0, 10 - total_deductions)`. | Rules: "score: int (floored at 0, starting at 10)" | An account triggering multiple deductions exceeding 10 points (e.g. −4 + −3 + −2 + extra) would compute a negative score (e.g. -1). |
| **D-5** | Deduct 4 points (`"seats down sharply"`) if and only if `len(months) > 1`, `peak_prior = max(m.seats_active for m in months[:-1]) > 0`, and `latest.seats_active <= 0.6 * peak_prior` (a drop of 40% or more). Single-month accounts (`len(months) == 1`) and accounts with `peak_prior == 0` are exempt. | Rules: "Latest month's seats fallen by 40% or more compared to the peak seat count across all prior recorded months. Single-month accounts do not trigger this rule." | Calculating peak across all months including latest, triggering on single-month accounts, or throwing a ZeroDivisionError when prior peak is 0. |
| **D-6** | Deduct 3 points (`"low engagement"`) if and only if `latest.logins < 3` in the latest month snapshot. | Rules: "Fewer than 3 logins in the latest month." | Deducting at `<= 3` logins (erroneously penalizing an account with exactly 3 logins) or evaluating average logins across prior months. |
| **D-7** | Deduct 2 points (`"unresolved support load"`) if and only if `latest.tickets_open >= 2` in the latest month snapshot. | Rules: "2 or more tickets open in the latest month." | Deducting only when strictly greater than 2 (`> 2`) or summing tickets across all historical months. |
| **D-8** | Tier classification maps `8..10` to `"HEALTHY"`, `5..7` to `"MEDIUM"`, and `0..4` to `"AT RISK"`. `Result.reasons` must preserve strict evaluation order: `["seats down sharply", "low engagement", "unresolved support load"]`. | Rules: "tier: str ('HEALTHY': 8–10, 'MEDIUM': 5–7, 'AT RISK': 0–4)" | Misclassifying boundary score 7 as HEALTHY or AT RISK, or storing reasons in non-deterministic order. |
| **D-9** | `scorer/usage.py` is pure Python and must never import `os`, `pathlib`, `open`, or perform file/network I/O. File reading belongs strictly in `scorer/main.py:load_export()`. | The two halves: "Never reads the CSV." | `parse_usage()` or `score()` attempting to read files directly from the filesystem or accepting file paths instead of text/dataclasses. |
| **D-10** | `parse_usage()` parses CSV columns by header name (`account_id`, `month`, `seats_active`, `logins`, `tickets_open`). The CLI formats output rows as `{account:<10} {score:>2}  {tier:<8} {reasons}` with multiple reasons joined by `", "` and empty reasons displayed as `"-"`, sorted alphabetically by account ID. | Input and CLI Entry Point | Positional CSV parsing failing when column order changes, or CLI formatting with irregular column spacing or missing `"-"` placeholders. |
| **D-11** | Calling `score([])` with an empty list of snapshots raises `ValueError("Cannot score empty month list")`. | The two halves: "An account with no months to score is omitted, so score() is never called with an empty list." | `score([])` raising an unhandled `IndexError` on `months[-1]` or returning an invalid `Result`. |

## Open questions

None.

## The gate

- **Status** is `Approved`
- **Open questions** is empty
- Every rule in Rules and Decisions is directly implementable without assumptions
