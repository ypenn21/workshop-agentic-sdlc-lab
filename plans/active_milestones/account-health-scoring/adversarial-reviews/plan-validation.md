# Plan Adversarial Review — Account Health Scoring (OPS-13)

> `plan-validator` · 3 independent skeptics, no shared scratchpad · default-to-reject · skeptics READ the codebase · 2-of-3 majority gate

| Field | Value |
|---|---|
| Milestone | `account-health-scoring` |
| Artifact | [`plans/active_milestones/account-health-scoring/plan.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md) |
| Date | 2026-08-31 |
| Gate | 2-of-3 majority |
| Result | **2 confirmed · 3 unconfirmed** — highest severity **medium** |
| 🁢 First domino | `empty-csv-header-validation-order` — Header presence check on empty text raises `TypeError`/`ValueError` before returning `{}` |

## Verdict
The technical plan is well-structured and grounded in the repository code, but will experience an early failure in `Task 2.A` if `csv.DictReader` header presence validation is executed before checking for empty or whitespace-only CSV input. Applying the confirmed fixes ensures seamless transition from contract test authoring to core implementation.

## Confirmed Findings (≥ 2 votes)

### 🟠 `empty-csv-header-validation-order` — DictReader header validation order on empty input · ordering · 3/3 · confidence high
- **Step:** Task 2.A: Implement Pure Domain Logic in [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py) (Step 1)
- **Failure:** Task 2.A Step 1 prescribes validating CSV header presence immediately upon instantiating `csv.DictReader`. When `csv_text` is empty or whitespace-only, `csv.DictReader(io.StringIO(csv_text)).fieldnames` evaluates to `None`. Validating required header presence (`{"account_id", ...}`) directly against `None` causes a `TypeError` or `ValueError` instead of cleanly returning an empty dictionary `{}`, breaking the contract specified in [`docs/spec.md:74`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/docs/spec.md#L74) and tested in `test_parse_empty_or_header_only_csv_returns_empty_dict`.
- **Evidence:** [`plans/active_milestones/account-health-scoring/plan.md:137-138`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md#L137-L138), [`docs/spec.md:74`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/docs/spec.md#L74)
- **Fix:** In Task 2.A Step 1, explicitly specify an initial guard: `if not csv_text.strip(): return {}` before inspecting `reader.fieldnames` and validating required header presence.

### 🟡 `spec-decision-mis-citation-empty-csv` — Empty CSV contract test cites D-14 instead of Section 8 · false-assumption · 2/3 · confidence high
- **Step:** Task 1.A: Contract Tests for `parse_usage()` in [`scorer/tests/test_parse_contract.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/tests/test_parse_contract.py)
- **Failure:** The plan attributes `test_parse_empty_or_header_only_csv_returns_empty_dict` to Decision `# D-14`. In [`docs/spec.md:101`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/docs/spec.md#L101), `D-14` strictly specifies the pure function boundary prohibiting filesystem/network I/O in `scorer/usage.py`, while empty and header-only CSV return behavior is specified in Section 8 (Validation & Omission Rules).
- **Evidence:** [`docs/spec.md:101`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/docs/spec.md#L101), [`docs/spec.md:74`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/docs/spec.md#L74), [`plans/active_milestones/account-health-scoring/plan.md:83`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md#L83)
- **Fix:** Update the citation for `test_parse_empty_or_header_only_csv_returns_empty_dict` in Task 1.A and the traceability matrix from `# D-14` to `Rule 8 / Spec Section 8 (Empty Input Handling)`.

## Unconfirmed (FYI · 1 vote)
| `id` | severity | step | note |
|---|---|---|---|
| `unreachable-zero-score-flooring` | 🔴 high | Task 1.B | With standard deductions summing to at most 9 points ($4+3+2$), the lowest achievable score with valid metrics is 1. Score flooring at 0 (`max(0, 10 - deductions)`) is a domain safety invariant rather than a scenario reachable from standard input data. |
| `group-1c-verification-unclear-expected-failure` | 🟡 low | Task 1.C | Step 2 omitted the note `(Verify failures due to NotImplementedError in scorer/usage.py)` present in Tasks 1.A and 1.B. |
| `redundant-main-implementation-task` | 🟡 low | Task 2.B | [`scorer/main.py:31-35`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py#L31-L35) already implements the CLI loop; Task 2.B should emphasize verification rather than re-implementation. |

## Checks That Passed
- Dataclass definitions `MonthSnapshot` and `Result` with `frozen=True` match in [`scorer/usage.py:8-22`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py#L8-L22) and the plan — [`scorer/usage.py:8-22`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py#L8-L22)
- All 6 fixture accounts in [`fixtures/usage.csv`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/fixtures/usage.csv) produce the exact calculated scores, tiers, and reasons asserted in Task 1.C and Task 3.A — [`fixtures/usage.csv:1-16`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/fixtures/usage.csv#L1-L16)
- Pure function I/O isolation boundary is preserved with zero imports of `os`, `pathlib`, `sys`, or `open` in [`scorer/usage.py`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py) — [`scorer/usage.py:1-36`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/usage.py#L1-L36)
- Pytest configuration in [`pyproject.toml:21`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/pyproject.toml#L21) configures `pythonpath = [".", "scorer"]`, ensuring imports resolve uniformly across test execution and CLI runs — [`pyproject.toml:21`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/pyproject.toml#L21)
- Terminal fixed-width format string `f"{account:<10} {result.score:>2}  {result.tier:<8} {reasons}"` matches existing CLI implementation in [`scorer/main.py:34`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py#L34) — [`scorer/main.py:34`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/scorer/main.py#L34)
- Task isolation across Group 1 test files (`test_parse_contract.py`, `test_score_contract.py`, `test_integration.py`) safely allows parallel authoring — [`plans/active_milestones/account-health-scoring/plan.md:54-58`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md#L54-L58)
- Single-month account exemption and zero-prior-peak guard rules accurately trace to decisions `D-4` and `D-5` — [`plans/active_milestones/account-health-scoring/plan.md:96-97`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md#L96-L97)

## Actions Taken
- [x] Documented first domino (`empty-csv-header-validation-order`) and confirmed findings in review artifact.
- [x] Updated [`plans/active_milestones/account-health-scoring/plan.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md) Task 2.A to specify `if not csv_text.strip(): return {}` early exit (`empty-csv-header-validation-order`).
- [x] Updated [`plans/active_milestones/account-health-scoring/plan.md`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/plans/active_milestones/account-health-scoring/plan.md) Task 1.A citation for empty CSV handling to Rule 8 / Section 3 (`spec-decision-mis-citation-empty-csv`).
- [x] Clarified `test_score_flooring_at_zero` in Task 1.B as a domain safety invariant test (`unreachable-zero-score-flooring`).
- [x] Re-run panel on revision -> not needed (minor refinement to guard and citations).
