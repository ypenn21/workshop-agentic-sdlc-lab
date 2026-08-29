# Technical Plan: Account Health Scorer

## 🔍 Analysis & Context
*   **Objective:** Implement a pure-Python account health scoring service that ingests monthly customer usage CSV exports, calculates deterministic health scores with explicit deduction reasons, and classifies accounts into actionable health tiers.
*   **Affected Files:**
    *   `docs/spec.md` (Formal Interface Contract Specification)
    *   `scorer/usage.py` (Domain models `MonthSnapshot`, `Result`, and pure functions `parse_usage()`, `score()`)
    *   `scorer/main.py` (CLI entry point, file I/O, terminal report formatting)
    *   `scorer/tests/test_parse_contract.py` (Contract acceptance tests for CSV ingestion & parsing)
    *   `scorer/tests/test_score_contract.py` (Contract acceptance tests for scoring rules & tier classifications)
    *   `scorer/tests/test_integration.py` (End-to-end integration and CLI output tests)
*   **Key Dependencies:** Python Standard Library (`dataclasses`, `csv`, `pathlib`, `typing`), `pytest` (test execution runner).
*   **Risks/Edge Cases:**
    *   Arbitrary CSV row ordering and duplicate month entries per account.
    *   Blank/whitespace numeric columns requiring zero-coercion without raising `ValueError`.
    *   Seat decline peak evaluation must evaluate only strictly prior months ($m_1 \dots m_{n-1}$), exempting single-month histories and zero-peak histories.
    *   Strict preservation of deduction reason ordering (`"seats down sharply"`, `"low engagement"`, `"unresolved support load"`).
    *   Score clamping lower bound at `0`.
    *   Empty month history passing to `score()` must raise `ValueError`.
    *   `scorer/usage.py` must maintain pure function discipline with zero filesystem or environment I/O.

---

## 📋 Task Execution (Parallel Groups)

### Group 1 (Parallel Execution - Independent Tasks)
- [ ] Task 1.1: Interface Dataclasses & CSV Parsing Contract in `scorer/usage.py` (verified via `scorer/tests/test_parse_contract.py`)
- [ ] Task 1.2: Health Scoring Engine & Rule Evaluation in `scorer/usage.py` (verified via `scorer/tests/test_score_contract.py`)

### Group 2 (Sequential Execution - Depends on Group 1)
- [ ] Task 2.1: End-to-End CLI Integration in `scorer/main.py` (verified via `scorer/tests/test_integration.py` and `uv run python scorer/main.py`)

---

## 📝 Step-by-Step Implementation Details

### Group 1 (Parallel Execution)

#### Task 1.1: Interface Dataclasses & CSV Parsing Contract
1.  **Step 1 (The Unit Test Harness):** Author contract acceptance tests in `scorer/tests/test_parse_contract.py` verifying:
    *   Header skipping and CSV row parsing into `MonthSnapshot` domain instances.
    *   Chronological ascending sort by `month` (`YYYY-MM`) per `account_id` (cites `# D-8`).
    *   Blank, empty, or whitespace metric coercion for `seats_active`, `logins`, and `tickets_open` to `0` (cites `# D-9`).
    *   Duplicate `(account_id, month)` handling (last encountered row retained).
    *   Omission of accounts with zero valid usage rows (cites `# D-10`).
    *   *Target File:* `scorer/tests/test_parse_contract.py`
2.  **Step 2 (The Implementation):** In `scorer/usage.py`:
    *   Define immutable `@dataclass(frozen=True) class MonthSnapshot: account_id: str, month: str, seats_active: int, logins: int, tickets_open: int`.
    *   Implement `parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]` using pure string parsing / standard library `csv.reader`.
    *   Group rows by account, coerce missing fields to integer `0`, sort chronological snapshots per account, and omit empty accounts.
    *   *Target File:* `scorer/usage.py`
3.  **Step 3 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_parse_contract.py` and ensure all parsing contract tests pass.

#### Task 1.2: Health Scoring Engine & Rule Evaluation
1.  **Step 1 (The Unit Test Harness):** Author contract acceptance tests in `scorer/tests/test_score_contract.py` verifying:
    *   Baseline perfect score: returns `Result(score=10, tier="HEALTHY", reasons=[])` for healthy usage.
    *   Rule 1 (Seat Decline): −4 points and `"seats down sharply"` reason when latest month seats drop $\ge 40\%$ from prior peak (cites `# D-1`).
    *   Rule 1 Exemptions: single-month accounts and prior peak $= 0$ accounts do not trigger seat decline (cites `# D-2`).
    *   Rule 2 (Low Engagement): −3 points and `"low engagement"` reason when latest month `logins < 3` (cites `# D-3`).
    *   Rule 3 (Unresolved Support): −2 points and `"unresolved support load"` reason when latest month `tickets_open >= 2` (cites `# D-4`).
    *   Deterministic Reason Ordering: strictly preserves order `["seats down sharply", "low engagement", "unresolved support load"]` (cites `# D-5`).
    *   Score Clamping: floored at `0` for extreme cumulative deductions (cites `# D-6`).
    *   Tier Classification: `8..10` → `"HEALTHY"`, `5..7` → `"MEDIUM"`, `0..4` → `"AT RISK"`, with boundary test for score `5` as `"MEDIUM"` (cites `# D-7`).
    *   Empty Input Defense: `score([])` raises `ValueError("Cannot score empty month history")` (cites `# D-10`).
    *   *Target File:* `scorer/tests/test_score_contract.py`
2.  **Step 2 (The Implementation):** In `scorer/usage.py`:
    *   Define immutable `@dataclass(frozen=True) class Result: score: int, tier: str, reasons: list[str]`.
    *   Implement `score(months: list[MonthSnapshot]) -> Result`:
        *   Validate non-empty `months` list; raise `ValueError` on empty input.
        *   Extract latest month ($m_n$) and prior months ($m_1 \dots m_{n-1}$).
        *   Calculate prior peak seats `max((m.seats_active for m in months[:-1]), default=0)`.
        *   Evaluate Rule 1 (Seat drop $\ge 40\%$ with prior peak $> 0$).
        *   Evaluate Rule 2 (Logins $< 3$).
        *   Evaluate Rule 3 (Tickets open $\ge 2$).
        *   Compute total deductions, floor score at `0`, assign tier, and return `Result`.
    *   *Target File:* `scorer/usage.py`
3.  **Step 3 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_score_contract.py` and ensure all scoring contract tests pass.

---

### Group 2 (Sequential Execution)

#### Task 2.1: End-to-End CLI Integration
1.  **Step 1 (The Unit Test Harness):** Author integration tests in `scorer/tests/test_integration.py` verifying:
    *   End-to-end processing of `fixtures/usage.csv`.
    *   Correct account health outcomes for all fixture accounts (`acme`, `globex`, `hooli`, `initech`, `umbrella`, `vandelay`).
    *   Output string formatting matching `{account:<10} {result.score:>2}  {result.tier:<8} {reasons}` with `"-"` for empty reasons.
    *   Alphabetical sorting of accounts in final CLI output.
    *   *Target File:* `scorer/tests/test_integration.py`
2.  **Step 2 (The Implementation):** In `scorer/main.py`:
    *   Verify `load_export()` correctly reads the CSV fixture.
    *   Implement `main()` to load file text, parse into account snapshot map with `parse_usage()`, score each account with `score()`, and print formatted report lines sorted by `account_id`.
    *   *Target File:* `scorer/main.py`
3.  **Step 3 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_integration.py` and ensure all integration tests pass.
    *   Run `uv run python scorer/main.py` and verify console output matches expected CLI report:
        ```text
        acme        6  MEDIUM   seats down sharply
        globex      6  MEDIUM   seats down sharply
        hooli      10  HEALTHY  -
        initech     5  MEDIUM   low engagement, unresolved support load
        umbrella   10  HEALTHY  -
        vandelay    6  MEDIUM   seats down sharply
        ```

---

## 🧪 Global Testing Strategy
*   **Unit Tests (`scorer/tests/test_parse_contract.py`, `scorer/tests/test_score_contract.py`):**
    *   Zero I/O, pure domain logic verification.
    *   100% test coverage over decisions D-1 through D-10.
    *   Edge case verification: single month history, zero peak seats, multiple simultaneous deductions, blank CSV values, unordered dates.
*   **Integration Tests (`scorer/tests/test_integration.py`):**
    *   End-to-end execution parsing `fixtures/usage.csv` through `load_export()`, `parse_usage()`, `score()`, and CLI formatter.
    *   Validates exact stdout formatting and alphabetical account ordering.
*   **Global Test Command:** `uv run pytest -q`

---

## 🎯 Success Criteria
1.  `docs/spec.md` is fully defined and adheres to `docs/spec-template.md` with decisions D-1 through D-10.
2.  `scorer/usage.py` maintains pure function discipline with zero filesystem or network I/O.
3.  All acceptance contract tests in `scorer/tests/` pass cleanly under `uv run pytest -q`.
4.  CLI execution via `uv run python scorer/main.py` produces expected account health summary report.
