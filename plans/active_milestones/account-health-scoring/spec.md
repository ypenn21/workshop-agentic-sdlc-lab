# Product Specification: Account Health Scoring (OPS-13)

## 🎯 Executive Summary
*   **Goal:** Provide an automated, deterministic account health scoring engine that parses monthly customer usage exports, computes health scores on a 0–10 scale, assigns accounts to clear health tiers (`HEALTHY`, `MEDIUM`, `AT RISK`), and outputs human-actionable deduction reasons.
*   **Target User:** Customer Success Managers (CSMs), Account Executives, and Support Leads.
*   **Business Value:** Enable proactive, explainable outreach to at-risk accounts weeks ahead of renewal cycles, reducing customer churn by eliminating mystery metrics and equipping CS with exact operational reasons.

---

## 🛠️ User Stories & Workflows

- **As a Customer Success Manager**, I want a prioritized Monday morning summary of customer accounts categorized by health tier, so that I immediately know which accounts require urgent outreach.
- **As a Customer Success Manager**, I want explicit deduction reasons (e.g., `seats down sharply`, `low engagement`, `unresolved support load`) attached to every scored account, so that I have immediate context before getting on the phone with a customer.
- **As a Software Engineer**, I want a pure-function domain model separated cleanly from CSV file I/O, so that scoring logic is testable, deterministic, and easily embeddable into downstream batch jobs or CLI tools.

---

## 📐 Data Models & Interface Contracts

The domain logic is implemented via two pure functions in `scorer/usage.py` that perform zero filesystem, network, or OS I/O:

### 1. `MonthSnapshot` Dataclass
```python
@dataclass(frozen=True)
class MonthSnapshot:
    account_id: str
    month: str          # "YYYY-MM" format (e.g., "2026-01")
    seats_active: int   # Active seats (>= 0); blank in CSV is parsed as 0
    logins: int         # Total logins in month (>= 0)
    tickets_open: int   # Open support tickets at month close (>= 0)
```

### 2. `Result` Dataclass
```python
@dataclass(frozen=True)
class Result:
    score: int          # Final score, integer between 0 and 10 (inclusive)
    tier: str           # Health tier: "HEALTHY" | "MEDIUM" | "AT RISK"
    reasons: list[str]  # Ordered deduction reasons that triggered
```

### 3. Pure Function Contracts

#### `parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]`
- **CSV Header Mapping:** Parses rows by column header names (`account_id`, `month`, `seats_active`, `logins`, `tickets_open`) using `csv.DictReader`, independent of column order in the CSV. Raises `ValueError` if required headers are absent.
- **Chronological Sorting:** For each account, snapshots are sorted in strictly ascending chronological order by `month` (`YYYY-MM`).
- **Data Validation & Missing Data Handling:**
  - `seats_active`: Optional in raw CSV. Blank, whitespace-only, or missing values default to integer `0`. Non-blank values must be valid integers $\ge 0$.
  - `logins` and `tickets_open`: Mandatory integer fields. Blank, missing, non-integer, or negative values are invalid and cause `parse_usage` to raise a `ValueError`.
  - Negative values (`seats_active < 0`, `logins < 0`, `tickets_open < 0`) are prohibited and raise a `ValueError`.
  - Duplicate `(account_id, month)` pairs within the input CSV are prohibited and raise a `ValueError`.
- **Empty / Inactive Accounts:** Accounts with no valid monthly records are omitted from the returned dictionary. If the input CSV contains only headers or whitespace, `parse_usage` returns an empty dictionary `{}`.

#### `score(months: list[MonthSnapshot]) -> Result`
- **Input Validation:** Requires a non-empty list of snapshots (`len(months) > 0`). If `months` is empty (`[]`), `score()` must raise a `ValueError("months must not be empty")`.
- **Chronological Sequence:** Evaluates health rules across snapshots assumed to be sorted in ascending chronological order.
- **Pure Function Constraint:** Must never perform filesystem, network, or OS I/O.

---

## 📊 Business Rules & Scoring Specification

### 1. Baseline & Range
- Every account begins with a baseline score of **10**.
- The minimum possible score is **0** (scores are floored at 0 via `max(0, 10 - total_deductions)`; scores can never become negative).

### 2. Health Tiers
| Score Range | Tier Name | Description |
| :--- | :--- | :--- |
| **8 – 10** | `HEALTHY` | Strong engagement, stable seats, low ticket backlog. |
| **5 – 7** | `MEDIUM` | Moderate risk signal; warrants monitoring or low-touch check-in. |
| **0 – 4** | `AT RISK` | Critical risk; immediate CSM outreach required. |

### 3. Deduction Rules & Evaluation Sequence
Deductions are evaluated in a fixed deterministic sequence:

1. **Rule 1: Seat Decline (−4 points, reason: `seats down sharply`)**
   - **Condition:** The latest month's `seats_active` has decreased by **40% or more** compared to the maximum (peak) `seats_active` across all prior recorded months (`months[:-1]`).
   - **Formula:** `latest_seats <= peak_prior_seats * 0.60` (where `peak_prior_seats = max(m.seats_active for m in months[:-1])`).
   - **Guardrails:**
     - Single-month accounts have no prior history and **never** trigger this rule.
     - If all prior months had 0 seats (`peak_prior_seats == 0`), this rule does not trigger.
2. **Rule 2: Low Engagement (−3 points, reason: `low engagement`)**
   - **Condition:** The latest month's `logins` is strictly fewer than 3 (`latest_month.logins < 3`).
3. **Rule 3: Unresolved Support Load (−2 points, reason: `unresolved support load`)**
   - **Condition:** The latest month has 2 or more unresolved support tickets (`latest_month.tickets_open >= 2`).

### 4. Deduction Reason Ordering
`Result.reasons` must preserve the deterministic evaluation order:
1. `"seats down sharply"` (if Rule 1 triggered)
2. `"low engagement"` (if Rule 2 triggered)
3. `"unresolved support load"` (if Rule 3 triggered)

When no deductions trigger, `Result.reasons` is empty (`[]`).

---

## 📋 Acceptance Criteria (Gherkin Scenarios)

### Feature: Usage Export CSV Parsing (`parse_usage`)

```gherkin
Scenario: Parse well-formed CSV with multiple accounts and months
  Given a CSV text containing monthly records for accounts "hooli" and "acme"
  When parse_usage is invoked with the CSV text
  Then the returned dictionary contains keys "hooli" and "acme"
  And each MonthSnapshot has correct integer values for seats_active, logins, and tickets_open

Scenario: Ensure chronological sorting of monthly records
  Given a CSV text with records for "globex" out of order: "2026-03", "2026-01", "2026-02"
  When parse_usage is invoked with the CSV text
  Then the snapshots for "globex" are sorted in ascending order: "2026-01", "2026-02", "2026-03"

Scenario: Header position independence via DictReader
  Given a CSV text with column headers in permuted order: "month,logins,account_id,tickets_open,seats_active"
  When parse_usage is invoked with the CSV text
  Then the data is correctly mapped and parsed according to header names

Scenario: Parse blank seats_active field as zero
  Given a CSV row "acme,2026-03,,5,0" with an empty seats_active column
  When parse_usage is invoked with the CSV text
  Then the resulting MonthSnapshot for "acme" in "2026-03" has seats_active equal to 0

Scenario: Reject blank or non-integer logins or tickets_open
  Given a CSV row with a blank or non-integer "logins" or "tickets_open" value
  When parse_usage is invoked with the CSV text
  Then parse_usage raises a ValueError

Scenario: Reject negative metric values
  Given a CSV row containing negative numbers for seats_active, logins, or tickets_open (e.g., "-5")
  When parse_usage is invoked with the CSV text
  Then parse_usage raises a ValueError

Scenario: Reject duplicate account and month snapshots
  Given a CSV text containing two rows with identical account_id and month
  When parse_usage is invoked with the CSV text
  Then parse_usage raises a ValueError

Scenario: Handle whitespace and empty lines
  Given a CSV text with trailing blank lines and whitespace around headers
  When parse_usage is invoked
  Then blank lines are ignored and data is parsed cleanly without errors

Scenario: Empty CSV input produces empty dictionary
  Given a CSV text containing only the header row or whitespace
  When parse_usage is invoked
  Then the returned dictionary is empty
```

### Feature: Account Health Scoring (`score`)

```gherkin
Scenario: Fully healthy account with no deductions
  Given an account with 2 months of stable seats (12, 12), high logins (40, 45), and low tickets (0, 1)
  When score is invoked with the snapshots
  Then the score is 10
  And the tier is "HEALTHY"
  And reasons is empty []

Scenario: Empty months input raises ValueError
  Given an empty list of snapshots []
  When score is invoked
  Then score raises a ValueError with message "months must not be empty"

Scenario: Single-month account never triggers seat drop deduction
  Given an account with only 1 month of history ("umbrella", 3 seats, 10 logins, 0 tickets)
  When score is invoked with the snapshots
  Then the score is 10
  And the tier is "HEALTHY"
  And reasons is empty []

Scenario: Seat decline of 40% or more triggers seat drop deduction
  Given an account with prior peak of 10 seats and latest month seats of 6 (40% drop)
  And logins >= 3 and tickets_open < 2
  When score is invoked with the snapshots
  Then the score is 6
  And the tier is "MEDIUM"
  And reasons contains ["seats down sharply"]

Scenario: Seat decline of 100% (e.g. blank parsed as 0) triggers seat drop deduction
  Given an account with prior peak of 10 seats and latest month seats of 0
  And logins >= 3 and tickets_open < 2
  When score is invoked with the snapshots
  Then the score is 6
  And the tier is "MEDIUM"
  And reasons contains ["seats down sharply"]

Scenario: Seat decline under 40% does not trigger deduction
  Given an account with prior peak of 10 seats and latest month seats of 7 (30% drop)
  When score is invoked with the snapshots
  Then the score is 10
  And the tier is "HEALTHY"
  And reasons is empty []

Scenario: Low engagement deduction triggers on fewer than 3 logins
  Given an account with stable seats, latest logins equal to 2, and 0 open tickets
  When score is invoked with the snapshots
  Then the score is 7
  And the tier is "MEDIUM"
  And reasons contains ["low engagement"]

Scenario: Support load deduction triggers on 2 or more open tickets
  Given an account with stable seats, latest logins equal to 5, and 2 open tickets
  When score is invoked with the snapshots
  Then the score is 8
  And the tier is "HEALTHY"
  And reasons contains ["unresolved support load"]

Scenario: Multiple deductions combine additively
  Given an account with latest logins equal to 2 (-3 pts) and 3 open tickets (-2 pts)
  When score is invoked with the snapshots
  Then the score is 5
  And the tier is "MEDIUM"
  And reasons contains ["low engagement", "unresolved support load"]

Scenario: All three deductions trigger AT RISK tier (maximum standard deduction of 9 points)
  Given an account with a sharp seat drop (-4 pts), 1 login (-3 pts), and 4 open tickets (-2 pts)
  When score is invoked with the snapshots
  Then the score is 1
  And the tier is "AT RISK"
  And reasons contains ["seats down sharply", "low engagement", "unresolved support load"]

Scenario: Zero-floor domain invariant enforcement
  Given a scoring calculation where total deductions reach or exceed 10 points
  When the score is evaluated as max(0, 10 - total_deductions)
  Then the resulting score is floored at 0
  And the tier is "AT RISK"
```

### Feature: CLI Integration (`scorer/main.py`)

```gherkin
Scenario: End-to-end execution on sample fixture
  Given the fixture file "fixtures/usage.csv"
  When the scorer CLI entry point is executed
  Then it prints formatted table rows sorted alphabetically by account_id
  And each row displays left-aligned account_id (width 10), right-aligned score (width 2), left-aligned tier (width 8), and reasons joined by ", " (or "-" if none)
```

---

## 🚨 Constraints & Edge Cases

1. **Pure Function Boundary:** `scorer/usage.py` must NEVER import `os`, `pathlib`, `sys`, or call `open()`. All file reading is owned by `scorer/main.py`.
2. **Deterministic Reason Ordering:** `Result.reasons` must always follow `["seats down sharply", "low engagement", "unresolved support load"]` based on which rules fired.
3. **Empty / Missing Data:** Blank `seats_active` strings in CSV must parse to integer `0`. Blank strings for `logins` or `tickets_open` must raise `ValueError`.
4. **Chronological Invariance:** The order of rows in the CSV export must not affect the output. `parse_usage` must explicitly sort snapshots by `month`.
5. **Peak Calculation:** `peak_prior_seats` is evaluated strictly over prior months (`months[:-1]`), excluding the latest month itself.
6. **Zero Peak Guard:** If all prior months had 0 seats active, a seat decline deduction is not triggered.
7. **Empty Input Guard:** `score([])` must raise a `ValueError` rather than failing with unhandled indexing errors.
8. **Negative Value Guard:** Negative metric numbers in CSV must raise a `ValueError` during parsing.

---

## 🎨 UI/UX Terminal Output Specification & Mockup

The CLI output uses standardized fixed-width column formatting without a header row:
- `account_id`: left-aligned, width 10 (`f"{account:<10}"`)
- `score`: right-aligned, width 2 (`f"{result.score:>2}"`)
- `tier`: left-aligned, width 8 (`f"{result.tier:<8}"`)
- `reasons`: comma-separated strings (`", ".join(result.reasons)` or `"-"` if empty)

Formatting template:
```python
f"{account:<10} {result.score:>2}  {result.tier:<8} {reasons}"
```

### Sample Output Mockup for `fixtures/usage.csv`
```text
acme        6  MEDIUM   seats down sharply
globex      6  MEDIUM   seats down sharply
hooli      10  HEALTHY  -
initech     5  MEDIUM   low engagement, unresolved support load
umbrella   10  HEALTHY  -
vandelay    6  MEDIUM   seats down sharply
```
