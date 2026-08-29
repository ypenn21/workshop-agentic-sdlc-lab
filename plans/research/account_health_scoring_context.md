# Strategic Research Context Report: Account Health Scoring (OPS-13)

## 1. Request Overview
- **Ticket Key:** `OPS-13`
- **Summary:** Account Health Scoring
- **Description:** Customer Success needs to know an account is in trouble before the cancellation email arrives. This reads the monthly usage export, gives each account a health score, puts it in a tier, and names the reasons, so CS can work a list rather than a hunch.
- **Priority:** Highest
- **Assignee:** `yannipeng@google.com`

## 2. Codebase & Domain Findings
- **Domain Models & Interfaces (`scorer/usage.py`):**
  - `MonthSnapshot`: Immutable dataclass representing monthly metrics (`account_id: str`, `month: str` formatted `YYYY-MM`, `seats_active: int`, `logins: int`, `tickets_open: int`).
  - `Result`: Immutable dataclass representing score outcome (`score: int`, `tier: str`, `reasons: list[str]`).
  - `parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]`: Interface for grouping CSV rows by account sorted chronologically.
  - `score(months: list[MonthSnapshot]) -> Result`: Pure function evaluating an account's health score.
- **Architecture Constraints:**
  - `scorer/usage.py` must remain completely pure: no file I/O, no network calls, no environment variables.
  - `scorer/main.py` handles CLI input/output, file reading, and console formatting.
- **Scoring Logic & Decisions:**
  - Base score: `10` points (floored at `0`).
  - Seat decline rule: −4 points if latest month seat count is down $\ge 40\%$ compared to the peak across all prior recorded months (exempt for single-month accounts).
  - Low engagement rule: −3 points if latest month logins `< 3`.
  - Unresolved support load rule: −2 points if latest month open tickets $\ge 2$.
  - Tier mapping: `HEALTHY` (8–10), `MEDIUM` (5–7), `AT RISK` (0–4).
- **Fixtures & Contracts:**
  - Fixture file: `fixtures/usage.csv`.
  - Existing contract test suite: `scorer/tests/test_parse_contract.py`, `scorer/tests/test_score_contract.py`, `scorer/tests/test_integration.py`.

## 3. Potential Edge Cases & Requirements
- CSV format variations: missing headers, blank seat fields, arbitrary row ordering.
- Chronological ordering requirements for months within accounts.
- Reason string ordering: exact deduction firing order.
