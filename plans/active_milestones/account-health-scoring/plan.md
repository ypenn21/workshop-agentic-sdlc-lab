# Technical Plan: Account Health Scoring (OPS-13)

## 🔍 Analysis & Context

*   **Objective:** Implement a deterministic account health scoring engine that parses monthly customer usage exports, computes health scores on a 0–10 scale, assigns accounts to health tiers (`HEALTHY`, `MEDIUM`, `AT RISK`), and outputs human-actionable deduction reasons via pure domain functions in [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py) and a CLI entry point in [`scorer/main.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py).
*   **Affected Files:**
    *   [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py) (Core pure domain logic: `MonthSnapshot`, `Result`, `parse_usage()`, and `score()`)
    *   [`scorer/main.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py) (CLI entry point and file I/O boundary)
    *   [`scorer/tests/test_parse_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_parse_contract.py) (Contract tests for `parse_usage()`)
    *   [`scorer/tests/test_score_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_score_contract.py) (Contract tests for `score()`)
    *   [`scorer/tests/test_integration.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_integration.py) (End-to-end composition and CLI formatting tests)
    *   [`docs/spec.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/docs/spec.md) (Interface Contract Specification)
    *   [`plans/active_milestones/account-health-scoring/plan.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md) (This technical plan)
*   **Key Dependencies:**
    *   Python Standard Library: `dataclasses`, `csv`, `io`, `pathlib`
    *   Test Runner: `pytest>=8.0.0` via `uv run pytest`
*   **Risks & Edge Cases:**
    1.  **Pure Function I/O Boundary Violation:** `scorer/usage.py` must NEVER import `os`, `pathlib`, `sys`, or call `open()`. All file reading belongs exclusively to `scorer/main.py` (cites `# D-14`).
    2.  **Blank Seat Coercion vs Mandatory Fields:** Blank or whitespace in `seats_active` must coerce to integer `0`, whereas blank, non-integer, or negative strings in `logins` or `tickets_open` must raise `ValueError` (cites `# D-1`, `# D-2`, `# D-3`).
    3.  **Historical Chronology & Peak Calculation:** `parse_usage()` must sort snapshots strictly in ascending order by `month` (`YYYY-MM`). In `score()`, `peak_prior_seats` is evaluated over prior months (`months[:-1]`). Single-month accounts have no prior history and never trigger seat drop (cites `# D-4`, `# D-5`).
    4.  **Zero Prior Peak Guard:** If all prior months had 0 seats (`peak_prior_seats == 0`), seat decline does not trigger (cites `# D-5`).
    5.  **Score Zero Flooring:** Scores must be floored at 0 (`max(0, 10 - total_deductions)`) and never become negative (cites `# D-9`).
    6.  **Deterministic Reason Ordering:** `Result.reasons` must strictly follow the rule evaluation sequence: `["seats down sharply", "low engagement", "unresolved support load"]` (cites `# D-10`).
    7.  **Empty Input Guard:** `score([])` called with an empty list must raise `ValueError("months must not be empty")` (cites `# D-11`).
    8.  **Duplicate Month Detection:** Multiple rows for the same `(account_id, month)` must raise `ValueError` (cites `# D-12`).

---

## 🏗️ Architecture & Component Interaction

```mermaid
flowchart TD
    subgraph Storage & I/O Boundary
        CSV["fixtures/usage.csv"] -->|load_export()| Main["scorer/main.py (CLI)"]
    end

    subgraph Pure Domain Logic (scorer/usage.py)
        Main -->|csv_text| Parse["parse_usage(csv_text)"]
        Parse -->|dict[account_id, list[MonthSnapshot]]| DictOut["Sorted Monthly Snapshots"]
        DictOut -->|list[MonthSnapshot]| Score["score(months)"]
        Score -->|Result(score, tier, reasons)| ResultOut["Result Dataclass"]
    end

    subgraph Presentation Layer
        ResultOut --> Main
        Main -->|Fixed-Width Stdout| Terminal["Terminal Output\nf'{account:<10} {score:>2}  {tier:<8} {reasons}'"]
    end
```

---

## 📋 Task Execution (Parallel Groups)

### Group 1 (Contract & Acceptance Test Harnesses - Parallel Execution)
- [ ] **Task 1.A:** Author Contract Tests for `parse_usage()` in [`scorer/tests/test_parse_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_parse_contract.py) covering column mapping, missing data handling, type coercion, sorting, duplicate detection, and negative value rejection (cites `# D-1`, `# D-2`, `# D-3`, `# D-4`, `# D-12`, `# D-13`, `# D-14`).
- [ ] **Task 1.B:** Author Contract Tests for `score()` in [`scorer/tests/test_score_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_score_contract.py) covering baseline scoring, health tiers, seat drop rules, engagement thresholds, support loads, multi-rule deductions, score flooring, reason ordering, and empty list guards (cites `# D-5`, `# D-6`, `# D-7`, `# D-8`, `# D-9`, `# D-10`, `# D-11`).
- [ ] **Task 1.C:** Author Integration & CLI Formatting Tests in [`scorer/tests/test_integration.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_integration.py) covering end-to-end execution on [`fixtures/usage.csv`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/fixtures/usage.csv) and fixed-width column stdout formatting (cites `# D-14`, `# D-9`, `# D-10`).

### Group 2 (Core Domain & CLI Implementation - Sequential Execution, Depends on Group 1)
- [ ] **Task 2.A:** Implement `parse_usage()` and `score()` pure domain functions in [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py) to satisfy all contract tests without performing any file/OS/network I/O.
- [ ] **Task 2.B:** Verify and refine CLI execution and fixed-width formatting in [`scorer/main.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py).

### Group 3 (Full Test Suite & CLI Verification - Sequential Execution, Depends on Group 2)
- [ ] **Task 3.A:** Execute full test suite (`uv run pytest -q`) and verify 100% green status across all test suites, then execute CLI (`uv run python scorer/main.py`) against [`fixtures/usage.csv`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/fixtures/usage.csv).

---

## 📝 Step-by-Step Implementation Details

### Group 1 (Contract & Acceptance Test Harnesses)

#### Task 1.A: Contract Tests for `parse_usage()` in `scorer/tests/test_parse_contract.py`

1.  **Step 1 (The Unit Test Harness):** In [`scorer/tests/test_parse_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_parse_contract.py), author acceptance contract tests citing decision IDs:
    *   `test_parse_well_formed_csv_returns_account_snapshots`: Validates parsing well-formed CSV into dict of `MonthSnapshot` objects (cites `# D-13`).
    *   `test_parse_chronological_sorting`: Validates that out-of-order month rows are sorted ascending by `month` (cites `# D-4`).
    *   `test_parse_header_position_independent`: Validates that arbitrary column order in header parses accurately via `DictReader` (cites `# D-13`).
    *   `test_parse_blank_seats_active_coerced_to_zero`: Validates empty/whitespace `seats_active` string defaults to integer `0` (cites `# D-1`).
    *   `test_parse_missing_or_invalid_logins_raises_value_error`: Validates blank, string, or non-integer `logins` raises `ValueError` (cites `# D-2`).
    *   `test_parse_missing_or_invalid_tickets_raises_value_error`: Validates blank, string, or non-integer `tickets_open` raises `ValueError` (cites `# D-2`).
    *   `test_parse_negative_values_raise_value_error`: Validates negative numbers in `seats_active`, `logins`, or `tickets_open` raise `ValueError` (cites `# D-3`).
    *   `test_parse_duplicate_account_month_raises_value_error`: Validates identical `(account_id, month)` rows raise `ValueError` (cites `# D-12`).
    *   `test_parse_empty_or_header_only_csv_returns_empty_dict`: Validates empty text or header-only CSV returns `{}` (cites Rule 8 / Spec Section 8: Validation & Empty Input Handling).
    *   `test_parse_missing_required_headers_raises_value_error`: Validates CSV missing required columns raises `ValueError` (cites `# D-13`).
    *   *Target File:* `scorer/tests/test_parse_contract.py`
2.  **Step 2 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_parse_contract.py -v`. (Verify failures due to `NotImplementedError` in `scorer/usage.py`).

---

#### Task 1.B: Contract Tests for `score()` in `scorer/tests/test_score_contract.py`

1.  **Step 1 (The Unit Test Harness):** In [`scorer/tests/test_score_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_score_contract.py), author contract tests citing decision IDs:
    *   `test_score_healthy_account_no_deductions`: 10 score, `"HEALTHY"` tier, empty `reasons` `[]` (cites `# D-9`, `# D-10`).
    *   `test_score_empty_months_raises_value_error`: `score([])` raises `ValueError` with `"months must not be empty"` (cites `# D-11`).
    *   `test_score_single_month_never_triggers_seat_drop`: Single snapshot never triggers seat decline (cites `# D-5`).
    *   `test_score_zero_peak_prior_seats_does_not_trigger_seat_drop`: Prior months with 0 seats do not trigger seat decline (cites `# D-5`).
    *   `test_score_seat_decline_40_percent_triggers_deduction`: Latest seats $\le 60\%$ of peak prior seats deducts 4 points with `"seats down sharply"` (cites `# D-6`).
    *   `test_score_seat_decline_100_percent_triggers_deduction`: 0 latest seats from positive prior peak deducts 4 points (cites `# D-6`).
    *   `test_score_seat_decline_under_40_percent_no_deduction`: 30% drop retains 10 score (cites `# D-6`).
    *   `test_score_low_engagement_triggers_deduction`: `logins < 3` deducts 3 points with `"low engagement"` (cites `# D-7`).
    *   `test_score_low_engagement_boundary_three_logins_no_deduction`: `logins == 3` does not deduct (cites `# D-7`).
    *   `test_score_support_load_triggers_deduction`: `tickets_open >= 2` deducts 2 points with `"unresolved support load"` (cites `# D-8`).
    *   `test_score_support_load_boundary_one_ticket_no_deduction`: `tickets_open == 1` does not deduct (cites `# D-8`).
    *   `test_score_multiple_deductions_additive`: Low engagement (-3) + support load (-2) yields score 5, `"MEDIUM"`, ordered reasons (cites `# D-9`, `# D-10`).
    *   `test_score_all_three_deductions_at_risk_tier`: Seat drop (-4) + low logins (-3) + support (-2) yields score 1, `"AT RISK"`, ordered reasons (cites `# D-9`, `# D-10`).
    *   `test_score_flooring_at_zero`: Validates mathematical domain invariant that total deductions $\ge 10$ are floored at 0 (`max(0, 10 - total_deductions)`) and assigned `"AT RISK"` tier (cites `# D-9`).
    *   *Target File:* `scorer/tests/test_score_contract.py`
2.  **Step 2 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_score_contract.py -v`. (Verify failures due to `NotImplementedError` in `scorer/usage.py`).

---

#### Task 1.C: Integration & CLI Composition Tests in `scorer/tests/test_integration.py`

1.  **Step 1 (The Integration Test Harness):** In [`scorer/tests/test_integration.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_integration.py), author end-to-end composition and CLI formatting tests:
    *   `test_end_to_end_fixture_scoring`: Runs `parse_usage()` and `score()` on [`fixtures/usage.csv`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/fixtures/usage.csv) and asserts exact expected scores and tiers for all fixture accounts:
        *   `acme`: score 6, tier `"MEDIUM"`, `["seats down sharply"]`
        *   `globex`: score 6, tier `"MEDIUM"`, `["seats down sharply"]`
        *   `hooli`: score 10, tier `"HEALTHY"`, `[]`
        *   `initech`: score 5, tier `"MEDIUM"`, `["low engagement", "unresolved support load"]`
        *   `umbrella`: score 10, tier `"HEALTHY"`, `[]`
        *   `vandelay`: score 6, tier `"MEDIUM"`, `["seats down sharply"]`
    *   `test_main_cli_stdout_formatting`: Invokes `main()` / captures stdout and asserts exact fixed-width column alignment matching `f"{account:<10} {result.score:>2}  {result.tier:<8} {reasons}"` (cites `# D-14`).
    *   *Target File:* `scorer/tests/test_integration.py`
2.  **Step 2 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_integration.py -v`. (Verify failures due to `NotImplementedError` in `scorer/usage.py`).

---

### Group 2 (Core Domain & CLI Implementation)

#### Task 2.A: Implement Pure Domain Logic in `scorer/usage.py`

1.  **Step 1 (The Implementation):** In [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py), implement pure functions:
    *   **`parse_usage(csv_text: str) -> dict[str, list[MonthSnapshot]]`**:
        *   Early exit guard: `if not csv_text or not csv_text.strip(): return {}` (ensures empty or whitespace-only CSV returns an empty dict `{}` prior to instantiating `csv.DictReader` and checking `reader.fieldnames`).
        *   Instantiate `reader = csv.DictReader(io.StringIO(csv_text))`.
        *   Validate header presence: verify required columns (`{"account_id", "month", "seats_active", "logins", "tickets_open"}`) are present in `reader.fieldnames`. If required headers are missing, raise `ValueError`. If headers are present but the CSV contains no data rows, return `{}`.
        *   Coerce `seats_active`: empty/whitespace string $\to 0$; non-blank $\to \text{int}(val)$; raise `ValueError` if $< 0$.
        *   Validate and parse `logins` and `tickets_open`: raise `ValueError` if missing, non-integer, or $< 0$.
        *   Track seen `(account_id, month)` pairs to raise `ValueError` on duplicates.
        *   Group snapshots by `account_id` and sort each list by `month` in ascending order.
    *   **`score(months: list[MonthSnapshot]) -> Result`**:
        *   Raise `ValueError("months must not be empty")` if `not months`.
        *   Identify `latest_month = months[-1]`.
        *   Compute Rule 1 (Seat Decline): If `len(months) > 1`, `peak_prior_seats = max(m.seats_active for m in months[:-1])`. If `peak_prior_seats > 0` and `latest_month.seats_active <= peak_prior_seats * 0.60`, deduct 4 points and record `"seats down sharply"`.
        *   Compute Rule 2 (Low Engagement): If `latest_month.logins < 3`, deduct 3 points and record `"low engagement"`.
        *   Compute Rule 3 (Support Load): If `latest_month.tickets_open >= 2`, deduct 2 points and record `"unresolved support load"`.
        *   Compute final score: `final_score = max(0, 10 - total_deductions)`.
        *   Assign tier: `final_score >= 8` $\to$ `"HEALTHY"`, `final_score >= 5` $\to$ `"MEDIUM"`, else `"AT RISK"`.
        *   Construct and return `Result(score=final_score, tier=tier, reasons=reasons)`.
    *   *Target File:* `scorer/usage.py`
2.  **Step 2 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_parse_contract.py -v`.
    *   Run `uv run pytest scorer/tests/test_score_contract.py -v`.

---

#### Task 2.B: Implement / Verify CLI Reporting in `scorer/main.py`

1.  **Step 1 (The Implementation):** In [`scorer/main.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py), ensure `main()` reads [`fixtures/usage.csv`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/fixtures/usage.csv), calls `parse_usage()`, invokes `score()`, and formats output alphabetically by account:
    ```python
    for account, months in sorted(parse_usage(text).items()):
        result = score(months)
        reasons = ", ".join(result.reasons) or "-"
        print(f"{account:<10} {result.score:>2}  {result.tier:<8} {reasons}")
    ```
    *   *Target File:* `scorer/main.py`
2.  **Step 2 (The Verification):**
    *   Run `uv run pytest scorer/tests/test_integration.py -v`.

---

### Group 3 (Full Test Suite & CLI Verification)

#### Task 3.A: Full Test Suite Execution & Verification

1.  **Step 1 (Run All Tests):**
    *   Execute full test suite across starter, contract, and integration tests:
        ```bash
        uv run pytest -v
        ```
2.  **Step 2 (Execute CLI):**
    *   Run the scorer CLI tool:
        ```bash
        uv run python scorer/main.py
        ```
    *   Verify terminal output matches expected mockup exactly:
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

*   **Starter / Smoke Tests ([`scorer/tests/test_starter.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_starter.py)):**
    *   Smoke tests verifying fixture loading, column headers, required fields, and duplicate absence in raw data.
*   **Parser Contract Tests ([`scorer/tests/test_parse_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_parse_contract.py)):**
    *   DictReader header mapping, blank seat integer coercion (`0`), chronological sorting (`YYYY-MM`), invalid string/negative value rejection (`ValueError`), duplicate account-month rejection (`ValueError`), empty/header-only CSV handling (`{}`).
*   **Scorer Contract Tests ([`scorer/tests/test_score_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_score_contract.py)):**
    *   Baseline 10 score, score zero flooring (`max(0, ...)`), tier assignment (`HEALTHY`, `MEDIUM`, `AT RISK`), seat drop rule ($40\%$ drop vs peak prior seats, single-month exemption, zero peak guard), low engagement ($< 3$ logins), support load ($\ge 2$ open tickets), additive multi-deductions, deterministic reason list ordering, empty list validation (`ValueError`).
*   **Integration Tests ([`scorer/tests/test_integration.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_integration.py)):**
    *   End-to-end execution of `load_export()` $\to$ `parse_usage()` $\to$ `score()` on `fixtures/usage.csv` and stdout fixed-width formatting verification.
*   **Test Commands:**
    ```bash
    uv run pytest scorer/tests/test_starter.py -v
    uv run pytest scorer/tests/test_parse_contract.py -v
    uv run pytest scorer/tests/test_score_contract.py -v
    uv run pytest scorer/tests/test_integration.py -v
    uv run pytest -q
    ```

---

## 🗺️ Traceability Matrix (Decisions & Acceptance Criteria)

| Spec Decision ID | Spec Scenario | Technical Plan Task | Verification / Test Assertion in `scorer/tests/` |
|---|---|---|---|
| **D-1** (Blank `seats_active` Coercion) | Scenario: Parse blank `seats_active` field as zero | Task 1.A, 2.A | `test_parse_blank_seats_active_coerced_to_zero` asserts `seats_active == 0`. |
| **D-2** (Mandatory Integer Fields) | Scenario: Reject blank or non-integer logins/tickets | Task 1.A, 2.A | `test_parse_missing_or_invalid_logins_raises_value_error` asserts `ValueError`. |
| **D-3** (Negative Metric Rejection) | Scenario: Reject negative metric values | Task 1.A, 2.A | `test_parse_negative_values_raise_value_error` asserts `ValueError` on `< 0`. |
| **D-4** (Chronological Sorting) | Scenario: Ensure chronological sorting | Task 1.A, 2.A | `test_parse_chronological_sorting` asserts snapshots sorted by `month`. |
| **D-5** (Peak Seat Scope & Single-Month Guard) | Scenario: Single-month account never triggers seat drop | Task 1.B, 2.A | `test_score_single_month_never_triggers_seat_drop` asserts score 10. |
| **D-6** (Seat Decline $\ge 40\%$ Threshold) | Scenario: Seat decline of 40% or more | Task 1.B, 2.A | `test_score_seat_decline_40_percent_triggers_deduction` asserts -4 pts & reason. |
| **D-7** (Low Engagement $< 3$ Logins) | Scenario: Low engagement deduction | Task 1.B, 2.A | `test_score_low_engagement_triggers_deduction` asserts -3 pts & reason. |
| **D-8** (Support Load $\ge 2$ Tickets) | Scenario: Support load deduction | Task 1.B, 2.A | `test_score_support_load_triggers_deduction` asserts -2 pts & reason. |
| **D-9** (Baseline, Floor & Tier Boundaries) | Scenario: All deductions / Zero-floor | Task 1.B, 2.A | `test_score_flooring_at_zero` & `test_score_healthy_account_no_deductions`. |
| **D-10** (Deterministic Reason Ordering) | Scenario: Reason ordering | Task 1.B, 2.A | `test_score_all_three_deductions_at_risk_tier` asserts exact order in list. |
| **D-11** (Empty Input Guard) | Scenario: Empty months input raises ValueError | Task 1.B, 2.A | `test_score_empty_months_raises_value_error` asserts `ValueError("months must not be empty")`. |
| **D-12** (Duplicate Month Rejection) | Scenario: Reject duplicate account and month | Task 1.A, 2.A | `test_parse_duplicate_account_month_raises_value_error` asserts `ValueError`. |
| **D-13** (Header Independence) | Scenario: Header position independence | Task 1.A, 2.A | `test_parse_header_position_independent` asserts correct column mapping. |
| **D-14** (Pure Function Boundary) | Scenario: End-to-end fixture execution | Task 1.C, 2.A, 2.B | `test_end_to_end_fixture_scoring` & `test_main_cli_stdout_formatting`. |
| **Rule 8 / Sec 8** (Empty / Whitespace CSV) | Scenario: Empty CSV produces empty dict | Task 1.A, 2.A | `test_parse_empty_or_header_only_csv_returns_empty_dict` asserts `{}`. |

---

## 🎯 Success Criteria

1.  **Strict Planning Separation:** No source code in [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py) or [`scorer/main.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py) was modified during this planning phase.
2.  **Complete Machine-Readable Plan:** [`plans/active_milestones/account-health-scoring/plan.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md) defines decoupled execution groups, dependencies, and exact test assertions.
3.  **100% Traceability:** Every decision (`D-1` through `D-14`) and scenario from [`plans/active_milestones/account-health-scoring/spec.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/spec.md) is mapped to test harness tasks.
4.  **Parallel Execution Readiness:** Group 1 test tasks (Task 1.A, Task 1.B, Task 1.C) are isolated across separate test files for safe parallel authoring.
5.  **Passing Test Suite:** Execution of `uv run pytest -q` passes completely once Phase 4 implementation concludes.
