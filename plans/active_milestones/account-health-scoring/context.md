# Phase 0 Strategic Research: Account Health Scoring (OPS-13)

## 📌 Executive Overview
- **Source Workitem:** Jira [OPS-13](https://google-team-coler8gf.atlassian.net/browse/OPS-13) / `docs/request.md`
- **Topic:** Account Health Scoring Service
- **Target Persona:** Customer Success (CS) Managers
- **Objective:** Ingest monthly usage CSV exports, calculate account health scores (0–10 scale), categorize accounts into health tiers (`HEALTHY`, `MEDIUM`, `AT RISK`), and emit human-actionable deduction reasons so CS can prioritize proactive intervention.

---

## 🏗️ Codebase Architecture & Domain Structure

### 1. File & Module Separation
- **`fixtures/usage.csv`**: Monthly account usage export fixture.
  - Columns: `account_id`, `month` (`YYYY-MM`), `seats_active` (integer or blank), `logins` (integer), `tickets_open` (integer).
- **`scorer/usage.py`**: Pure domain logic and models.
  - Dataclasses: `MonthSnapshot` (account_id, month, seats_active, logins, tickets_open), `Result` (score, tier, reasons).
  - Pure functions:
    - `parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]`
    - `score(months: list[MonthSnapshot]) -> Result`
  - **Constraint:** Strictly pure functions; no filesystem, network, or OS I/O imports (`os`, `pathlib`, `open`).
- **`scorer/main.py`**: CLI entry point and I/O boundary.
  - Loads `fixtures/usage.csv` from disk.
  - Invokes `parse_usage()` and `score()` to format and print sorted terminal summary.
- **`scorer/tests/`**: Test suite and contract validation harness.

---

## 📊 Domain Rules & Baseline Scoring Logic

### Score Scale & Tiers
- **Initial Baseline Score:** 10 points (floor at 0 points minimum).
- **Health Tiers:**
  - `HEALTHY`: 8 – 10
  - `MEDIUM`: 5 – 7
  - `AT RISK`: 0 – 4

### Deduction Rules & Reasons
1. **Seat Decline (−4 pts, reason: `seats down sharply`)**:
   - Latest month's active seats dropped by 40% or more compared to the peak seat count across all prior recorded months.
   - Single-month accounts do not trigger this deduction.
2. **Low Engagement (−3 pts, reason: `low engagement`)**:
   - Fewer than 3 logins in the latest recorded month (`logins < 3`).
3. **Unresolved Support Load (−2 pts, reason: `unresolved support load`)**:
   - 2 or more unresolved support tickets open in the latest recorded month (`tickets_open >= 2`).

---

## 🔍 Key Constraints & Discovery Focus Areas

1. **Missing Data Handling:** Handling blank `seats_active` cells in CSV (parsed as `0`).
2. **Chronological Sorting:** Guaranteeing ascending order of snapshots by `month` (`YYYY-MM`) regardless of raw CSV row ordering.
3. **Omission of Inactive / Empty Accounts:** Accounts with no valid monthly records are omitted from parsing results.
4. **Reason Ordering:** Order of deduction reasons in `Result.reasons` (e.g., matching rule evaluation order: seats drop, low engagement, support load).
