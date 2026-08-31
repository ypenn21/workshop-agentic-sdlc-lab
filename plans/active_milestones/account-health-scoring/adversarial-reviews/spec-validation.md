# Spec Adversarial Review — Account Health Scoring (OPS-13)

> `spec-validator` · 3 independent skeptics, no shared scratchpad · default-to-reject · 2-of-3 majority gate

| Field | Value |
|---|---|
| Milestone | `account-health-scoring` |
| Artifact | `plans/active_milestones/account-health-scoring/spec.md` |
| Date | 2026-08-31 |
| Gate | 2-of-3 |
| Result | **8 confirmed · 6 unconfirmed** — highest severity **🔴 high** |

## Verdict
The specification has solid foundation, clear data models, and deterministic scoring formulas, but is currently **blocked from tactical planning** by 2 high-severity defects: a direct mathematical contradiction in the UI terminal mockup for `vandelay` (which yields score 6, MEDIUM under business rules but is mocked up as score 4, AT RISK) and unspecified error behavior for blank or non-integer values in `logins` and `tickets_open`. These defects and the unreachable 0-score acceptance scenario must be tightened before advancing to Phase 2.

## Confirmed Findings (≥ 2 votes)

### 🔴 `vandelay-mockup-contradiction` — Terminal Mockup Score Contradiction for Vandelay · 3/3
- **Clause:** `"vandelay    4  AT RISK  seats down sharply"`
- **Malicious reading:** The terminal mockup asserts `vandelay` receives score 4 and tier `AT RISK` with only `"seats down sharply"` listed. However, applying the specified baseline (10) and Rule 1 deduction (-4) yields a score of 6 and tier `MEDIUM` (10 − 4 = 6). An implementer could hardcode a -6 deduction or override account logic to pass CLI assertions while failing unit domain tests.
- **Harm:** Test harnesses asserting CLI output against the mockup will fail against pure domain score tests, or accounts with only a seat drop will be incorrectly misclassified as critical churn risks.
- **Tightening:** Update the UI/UX terminal output mockup row for `vandelay` to `vandelay    6  MEDIUM   seats down sharply` to align with the 10 − 4 = 6 deduction formula and the `MEDIUM` tier definition.

### 🔴 `blank-or-invalid-logins-tickets-unspecified` — Missing Blank/Invalid Handling for Logins & Tickets · 2/3
- **Clause:** `"seats_active: int   # Active seats; blank in CSV is parsed as 0"`
- **Malicious reading:** The spec explicitly defines fallback behavior for blank `seats_active` columns, but is silent on blank or non-integer entries in `logins` or `tickets_open`. A parser defaulting blank logins to `0` will unintentionally trigger Rule 2 (`low engagement`, < 3 logins), while a parser calling `int(col)` will crash with unhandled `ValueError`.
- **Harm:** Ingestion crashes or false penalty deductions applied to accounts with missing login telemetry.
- **Tightening:** Explicitly specify that blank values are permitted ONLY in `seats_active` (defaulting to 0); blank or non-integer values in `logins` or `tickets_open` render the row invalid and must cause `parse_usage` to raise a `ValueError` (or omit the invalid record).

### 🟠 `duplicate-month-records-unhandled` — Unhandled Duplicate Month Records per Account · 3/3
- **Clause:** `<MISSING>` / `"Parses raw CSV text into a dictionary mapping account_id to a chronologically sorted list[MonthSnapshot] in ascending order of month."`
- **Malicious reading:** If the input CSV contains duplicate rows for the same `(account_id, month)`, `parse_usage` might append both snapshots. `score()` evaluates `months[-1]` against `months[:-1]`, treating one duplicate entry as prior history and another as latest, calculating spurious seat drop deductions between records of the identical month.
- **Harm:** Non-deterministic scoring, corrupted peak prior calculations, and false seat drop deductions.
- **Tightening:** Require `parse_usage` to raise `ValueError("Duplicate month snapshot")` if multiple records for the same `(account_id, month)` pair are present in the CSV.

### 🟠 `unreachable-zero-score-scenario` — Untestable Zero-Score Flooring Acceptance Scenario · 3/3
- **Clause:** `"Scenario: Floor score at zero when total deductions exceed 10\n  Given a hypothetical scenario where cumulative deductions exceed 10 points\n  When score is invoked with the snapshots\n  Then the score is 0\n  And the tier is \"AT RISK\""`
- **Malicious reading:** The maximum possible deduction under all three defined rules combined is only 9 points (4 + 3 + 2 = 9). Starting from a baseline of 10, the lowest attainable score under valid inputs is 1. An acceptance test cannot execute this scenario using valid `MonthSnapshot` domain inputs without mocking synthetic rules.
- **Harm:** Untestable Gherkin acceptance scenario that forces test writers to create artificial test doubles or dead code paths.
- **Tightening:** Clarify that score flooring at 0 (`max(0, 10 - deductions)`) is a domain invariant guaranteed by the calculation formula rather than an end-to-end scenario achievable with standard rule inputs (where the minimum possible score is 1).

### 🟠 `csv-header-ordering-and-case` — CSV Column Ordering and Header Lookup Contract · 3/3
- **Clause:** `<MISSING>`
- **Malicious reading:** The spec does not require `parse_usage` to look up columns by named headers. A positional parser indexing `row[0..4]` will silently corrupt data if CSV columns are exported in a different order (e.g., `month, account_id, ...`), and a strict case-sensitive parser will fail on `Account_Id`.
- **Harm:** Silent data corruption or fragile ingestion pipelines when CSV column order varies across reporting tools.
- **Tightening:** Require `parse_usage` to parse CSV rows using column header names (`account_id`, `month`, `seats_active`, `logins`, `tickets_open`) via `csv.DictReader`, independent of column position, and raise `ValueError` if required headers are absent.

### 🟠 `empty-or-unsorted-months-in-score` — Lack of Input Validation in score() · 2/3
- **Clause:** `"Assumes months is non-empty and sorted in ascending chronological order."`
- **Malicious reading:** Because `score()` merely assumes valid non-empty inputs, passing an empty list `months=[]` causes unhandled runtime crashes (`IndexError: list index out of range` or `ValueError: max() arg is an empty sequence`). Passing unsorted snapshots produces incorrect latest-month calculations without warning.
- **Harm:** Unhandled runtime crashes and silent miscalculations when `score()` is invoked directly in downstream batch pipelines.
- **Tightening:** Mandate that `score(months: list[MonthSnapshot])` must raise `ValueError("months must not be empty")` when `len(months) == 0`.

### 🟡 `cli-table-formatting-unspecified` — Underspecified CLI Column Alignment and Layout · 2/3
- **Clause:** `"Then it prints formatted table rows sorted alphabetically by account_id\n  And each row displays account_id, score, tier, and deduction reasons (or \"-\" if none)"`
- **Malicious reading:** Exact column widths, alignment, and reason separators are not formally specified. An implementation using tab characters or arbitrary spacing technically passes the Gherkin text but will fail snapshot-based integration tests.
- **Harm:** Brittle integration tests and inconsistent CLI formatting across environments.
- **Tightening:** Formally specify the CLI layout format: left-aligned `account_id` (width 10), right-aligned `score` (width 2), left-aligned `tier` (width 8), and `reasons` joined by `", "` (or `"-"` if empty), with no table header.

### 🟡 `negative-metric-values-unconstrained` — Unconstrained Negative Metric Values · 2/3
- **Clause:** `<MISSING>`
- **Malicious reading:** Dataclass fields type counts as generic `int`. If negative values appear in CSV rows (e.g., `logins: -5`, `seats_active: -10`), `score()` processes them literally, causing erratic threshold triggering and invalid peak decline math.
- **Harm:** Distorted health scores and false positive deductions on dirty or corrupted CSV feeds.
- **Tightening:** Require `parse_usage` to validate that `seats_active >= 0`, `logins >= 0`, and `tickets_open >= 0`, raising `ValueError` if negative numbers are encountered.

---

## Unconfirmed (FYI · 1 vote)

| `id` | severity | clause | note |
|---|---|---|---|
| `csv-row-validity-undefined` | 🔴 high | `"Accounts with no valid monthly records are omitted from the dictionary."` | Skeptic 1 noted that criteria for what constitutes an invalid row vs. missing account was not formally enumerated. |
| `unbounded-prior-peak-lookback` | 🟠 medium | `"The latest month's seats_active has decreased by 40% or more compared to the maximum (peak) seats_active across all prior recorded months"` | Skeptic 2 noted that lifetime peak lookback means a company that downsized 2 years ago triggers Rule 1 permanently every month. |
| `month-format-validation` | 🟠 medium | `"month: str          # \"YYYY-MM\" format (e.g., \"2026-01\")"` | Skeptic 3 noted that non-zero-padded months (e.g., `2026-2` vs `2026-10`) sort incorrectly lexicographically unless strict ISO regex `^\d{4}-(0[1-9]\|1[0-2])$` is validated. |
| `data-cell-whitespace-handling` | 🟠 medium | `"Given a CSV text with trailing blank lines and whitespace around headers"` | Skeptic 3 noted that whitespace inside data cells (e.g., `' acme '`) was not explicitly required to be trimmed, potentially splitting account keys. |
| `integer-truncation-decline-calculation` | 🟠 medium | `"The latest month's seats_active has decreased by 40% or more..."` | Skeptic 3 noted integer division `(peak * 4 // 10)` could trigger false deductions on `peak=9, latest=6` (33% drop). |
| `cli-file-argument-unspecified` | 🟡 low | `"When the scorer CLI entry point is executed"` | Skeptic 3 noted that `main.py` CLI argument parsing (`sys.argv` vs hardcoded fixture path) was not specified. |

---

## Attacks That Failed
- **Single-month account seat decline attack:** Skeptics attempted to trigger Rule 1 on single-month accounts; failed because the spec explicitly provides a guardrail and dedicated acceptance scenario forbidding seat drop deductions on single-month accounts.
- **Zero peak prior seats attack:** Skeptics attempted to trigger `0 <= 0 * 0.60` when all prior months had 0 seats; failed because the spec explicitly specifies that `peak_prior_seats == 0` does not trigger Rule 1.
- **Deduction reason ordering attack:** Skeptics attempted to emit reasons out of sequence; failed because the spec strictly fixes the deterministic evaluation and output ordering `["seats down sharply", "low engagement", "unresolved support load"]`.
- **Health tier boundary thresholds:** Skeptics attacked tier boundaries (8, 5, 0); failed because tier ranges are exhaustively and non-overlappingly defined as closed integer ranges (8–10 `HEALTHY`, 5–7 `MEDIUM`, 0–4 `AT RISK`).
- **Pure function boundary enforcement:** Skeptics checked for file/network I/O in domain logic; failed because Constraint 1 strictly forbids importing `os`, `pathlib`, `sys`, or calling `open()` in `scorer/usage.py`.

---

## Actions Taken
- [ ] Folded `vandelay-mockup-contradiction` tightening into spec §🎨 UI/UX Terminal Output Mockup
- [ ] Folded `blank-or-invalid-logins-tickets-unspecified` tightening into spec §📐 Data Models & Interface Contracts
- [ ] Folded `duplicate-month-records-unhandled` tightening into spec §📐 Data Models & Interface Contracts
- [ ] Folded `unreachable-zero-score-scenario` clarification into spec §📋 Acceptance Criteria
- [ ] Folded `csv-header-ordering-and-case` tightening into spec §📐 Data Models & Interface Contracts
- [ ] Folded `empty-or-unsorted-months-in-score` tightening into spec §📐 Data Models & Interface Contracts
- [ ] Surfaced unconfirmed findings (`unbounded-prior-peak-lookback`, `month-format-validation`, `data-cell-whitespace-handling`) to the Product Owner
- [ ] Re-ran panel on revision → `spec-validation-r2.md` _(or: not needed)_
