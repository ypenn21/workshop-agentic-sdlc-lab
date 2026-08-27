# Account Health Scorer

**Status:** Approved

## What this does

Customer Success needs to identify at-risk customer accounts before cancellation requests arrive. This service ingests monthly customer usage CSV exports, calculates a deterministic and explainable health score with explicit deduction reasons, and categorizes accounts into health tiers so Customer Success Managers can prioritize proactive outreach.

## Input

The input arrives as raw CSV export text (UTF-8 encoded) or a path to a CSV export file.
The CSV schema is guaranteed to have the header:
```csv
account_id,month,seats_active,logins,tickets_open
```

### Guarantees and Invariants:
1. **Header:** The first row contains column headers and must be skipped.
2. **Column Definitions:**
   - `account_id`: Non-empty string identifier (whitespace trimmed).
   - `month`: String in ISO 8601 year-month format (`YYYY-MM`).
   - `seats_active`: Integer count of active seats. If blank, empty, or whitespace, coerced to `0`.
   - `logins`: Integer count of user logins during the month. If blank, coerced to `0`.
   - `tickets_open`: Integer count of open support tickets in the month. If blank, coerced to `0`.
3. **Ordering:** Rows may appear in arbitrary order across accounts and months.
4. **Duplicate Handling:** If multiple rows exist for the same `(account_id, month)` pair, the last encountered row is retained.
5. **Empty Account Defense:** Accounts with no valid usage rows are omitted from parsed results.

## The two halves

The system is split into two pure functions in `scorer/usage.py` and a CLI boundary in `scorer/main.py`. The pure functions perform zero filesystem, network, or environment I/O.

### Data Structures (`scorer/usage.py`)

```python
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
    score: int          # Range: 0 to 10
    tier: str           # "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]  # Ordered list of deduction reasons
```

### Pure Function Interfaces (`scorer/usage.py`)

1. **CSV Ingestion Interface:**
   ```python
   def parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]:
       """Group the export text by account, each list in ascending month order.
       
       Omit accounts with no recorded months. Blank numerical fields are coerced to 0.
       """
   ```

2. **Scoring Engine Interface:**
   ```python
   def score(months: list[MonthSnapshot]) -> Result:
       """Score one account's chronological month history.
       
       Raises ValueError if months is empty.
       """
   ```

### CLI Boundary Interface (`scorer/main.py`)
- Reads the input CSV file from the filesystem.
- Invokes `parse_usage(text)`.
- Iterates over accounts sorted alphabetically by `account_id`.
- Scores each account using `score(months)`.
- Outputs formatted lines to stdout:
  `{account:<10} {score:>2}  {tier:<8} {reasons}`
  (If reasons list is empty, outputs `"-"`).

## Rules

A builder must follow these deterministic rules:

1. **Initial Score:** Every account starts with a baseline score of `10` points.
2. **Deduction Rule 1 - Seat Decline (−4 points):**
   - Condition: Compare the latest month's `seats_active` ($m_n$) against the maximum `seats_active` across all prior recorded months ($m_1, \dots, m_{n-1}$). If prior peak $> 0$ and $m_n \le 0.60 \times \text{prior\_peak}$ (a decline of $\ge 40\%$), deduct `4` points.
   - Reason String: `"seats down sharply"`.
   - Exemption: If the account has only 1 month of history or if all prior months had `seats_active == 0`, this rule does not fire.
3. **Deduction Rule 2 - Low Engagement (−3 points):**
   - Condition: If the latest month's `logins < 3`, deduct `3` points.
   - Reason String: `"low engagement"`.
4. **Deduction Rule 3 - Unresolved Support Load (−2 points):**
   - Condition: If the latest month's `tickets_open >= 2`, deduct `2` points.
   - Reason String: `"unresolved support load"`.
5. **Reason Ordering:** When multiple deductions fire, append reasons in the strict deterministic order:
   1. `"seats down sharply"`
   2. `"low engagement"`
   3. `"unresolved support load"`
6. **Score Lower Bound:** The final score is clamped at `0`: `score = max(0, 10 - sum(deductions))`.
7. **Tier Classification:**
   - Score `8..10`: `"HEALTHY"`
   - Score `5..7`: `"MEDIUM"`
   - Score `0..4`: `"AT RISK"`
8. **Chronological Sorting:** `parse_usage` groups entries by `account_id` and sorts each account's `MonthSnapshot` list ascending by `month` (`YYYY-MM`).
9. **Blank Metric Coercion:** Empty, blank, or whitespace strings for `seats_active`, `logins`, or `tickets_open` parse as `0`.
10. **Empty History Defense:** `score([])` raises `ValueError("Cannot score empty month history")`.

## Out of scope

1. Direct database connections, CRM integrations, or REST API endpoints.
2. Writing back health scores or updating remote ticketing systems.
3. Machine learning models, probabilistic churn predictions, or weighted trend analysis.
4. Parsing or validating months outside the standard `YYYY-MM` format.
5. Interactive GUI, web frontend, or user authentication.

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| --- | --- | --- | --- |
| **D-1** | Latest month seats compared against peak across all *prior* recorded months ($m_1 \dots m_{n-1}$). Deduct 4 points if decline $\ge 40\%$ and prior peak $> 0$. | "fallen by 40% or more compared to the peak seat count across all prior recorded months" | Latest month has 6 seats, prior months were 4 and 10. Prior peak is 10, decline is $(10-6)/10 = 40\%$, rule fires (−4). |
| **D-2** | Single-month accounts and accounts where prior peak is 0 never trigger seat decline deduction. | "Single-month accounts do not trigger this rule." | Account with only 1 month (e.g., 5 seats) or prior months having 0 seats does not trigger seat drop deduction. |
| **D-3** | Deduct 3 points if latest month `logins < 3`. | "Fewer than 3 logins in the latest month." | Account with `logins == 2` deducts 3 points; `logins == 3` triggers no deduction. |
| **D-4** | Deduct 2 points if latest month `tickets_open >= 2`. | "2 or more tickets open in the latest month." | Account with `tickets_open == 2` deducts 2 points; `tickets_open == 1` triggers no deduction. |
| **D-5** | Deduction reasons must appear in deterministic order: `"seats down sharply"`, `"low engagement"`, `"unresolved support load"`. | "ordered list of reasons for deductions that fired" | If low engagement and seat decline both fire, `reasons` is `["seats down sharply", "low engagement"]`. |
| **D-6** | Calculated score is floored at 0 (`max(0, 10 - deductions)`). | "floored at 0, starting at 10" | Cumulative deductions totaling 11 points result in a score of `0` instead of `-1`. |
| **D-7** | Tier classification ranges: `8..10` → `"HEALTHY"`, `5..7` → `"MEDIUM"`, `0..4` → `"AT RISK"`. Score `5` is `"MEDIUM"`. | `"HEALTHY"`: 8–10, `"MEDIUM"`: 5–7, `"AT RISK"`: 0–4 | A score of `5` is mapped to `"MEDIUM"`, `7` to `"MEDIUM"`, `8` to `"HEALTHY"`. |
| **D-8** | `parse_usage` skips header and sorts snapshots chronologically ascending by month per account. | "each list in ascending month order" | Unordered CSV rows `2026-03` before `2026-01` are sorted as `[2026-01, 2026-03]`. |
| **D-9** | Blank or whitespace strings in numeric CSV fields are coerced to integer `0`. | "blank in CSV is parsed as 0" | Row `acme,2026-03,,5,0` parses `seats_active` as `0`. |
| **D-10** | `score([])` raises `ValueError`. `parse_usage` omits accounts with no valid usage records. | "An account with no months to score is omitted, so score() is never called with an empty list." | Calling `score([])` directly raises `ValueError("Cannot score empty month history")`. |

## Open questions

None.

## The gate

Code starts when all three hold:

- **Status** is `Approved`
- **Open questions** is empty
- Every rule, in Rules and in Decisions, is one a builder could follow without asking anybody
