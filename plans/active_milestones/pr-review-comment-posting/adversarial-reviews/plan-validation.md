# Plan Adversarial Review — Automated GitHub PR Review & Positive Comment Posting

> `plan-validator` · 3 independent skeptics, no shared scratchpad · default-to-reject · skeptics READ the codebase · 2-of-3 majority gate

| Field | Value |
|---|---|
| Milestone | `pr-review-comment-posting` |
| Artifact | `plans/active_milestones/pr-review-comment-posting/plan.md` |
| Date | 2026-08-28 |
| Gate | 2-of-3 majority gate |
| Result | **4 confirmed · 4 unconfirmed** — highest severity **🔴 high** |
| 🁢 First domino | `ordering-missing-stubs-import-error` — Test collection crashes in Group 1 due to missing symbol stubs before Group 2 implementation runs |

## Verdict

The implementation plan has strong architectural alignment with `docs/spec.md`, but it will **fail on step 1 (First Domino)** unless amended: Group 1 test authoring imports `post_github_pr_review`, `POSITIVE_APPROVAL_TEMPLATE`, and helper functions before Group 2 implements them, causing `ImportError` crashes during Group 1 test collection. Additionally, `run_pr_review()` omits the `modified_files_diff` parameter (silently dropping all inline PR comments), has dual un-unified return blocks bypassing review posting on fallbacks, and unmocked network calls in existing unit tests will trigger socket timeouts.

## Confirmed Findings (≥ 2 votes)

### 🔴 `ordering-missing-stubs-import-error` — Missing Interface Stubs Cause Group 1 Test Collection Failure · ordering · 3/3 · confidence high
- **Step:** Group 1, Task 1.A & Task 1.B (Contract & Unit Test Harnesses)
- **Failure:** Task 1.A and Task 1.B author unit and acceptance tests that import `post_github_pr_review`, `_sanitize_and_validate_repo`, and `POSITIVE_APPROVAL_TEMPLATE` directly from `pr_reviewer_agent`. Because Group 2 implements these symbols after Group 1, running `uv run pytest` in Group 1 Step 2 crashes during test collection with `ImportError: cannot import name 'post_github_pr_review' from 'pr_reviewer_agent'`, failing the Group 1 verification gate before Group 2 implementation can start.
- **Evidence:** `.github/scripts/pr_reviewer_agent.py:1-348` (symbols do not exist yet); `plans/active_milestones/pr-review-comment-posting/plan.md:73-79, 152-154, 172-174`.
- **Fix:** Add a prerequisite Task 1.0 (or stub declaration in Group 1) to declare stub interfaces in `.github/scripts/pr_reviewer_agent.py` (`async def post_github_pr_review(...) -> bool: raise NotImplementedError` and `POSITIVE_APPROVAL_TEMPLATE = ""`) so test files import cleanly and fail with standard assertion/not-implemented errors during the TDD Red phase.

### 🔴 `hidden-coupling-missing-diff-param-drops-inline-comments` — `run_pr_review` Omission of `modified_files_diff` Drops All Inline Comments · hidden-coupling · 3/3 · confidence high
- **Step:** Group 2, Task 2.A & Group 1, Task 1.B (Structured Inline Comments via `run_pr_review`)
- **Failure:** `post_github_pr_review()` relies on `modified_files_diff: dict[str, list[int]]` to separate inline findings from general findings via `validate_and_sanitize_findings()`. The plan's integration snippet in `run_pr_review()` calls `post_github_pr_review(report=report, pr_number=pr_number, repo=repo, token=token)` without passing `modified_files_diff`. When `modified_files_diff` defaults to `None` / `{}`, `validate_and_sanitize_findings()` places 100% of findings into `general_findings`, leaving `comments: []`. As a result, the agent will never post inline review comments on GitHub PRs during end-to-end execution or acceptance tests.
- **Evidence:** `.github/scripts/pr_reviewer_agent.py:75-84`; `plans/active_milestones/pr-review-comment-posting/plan.md:355-361`.
- **Fix:** Update `run_pr_review()` signature to accept `modified_files_diff: Optional[dict[str, list[int]]] = None`, and forward `modified_files_diff=modified_files_diff` to `post_github_pr_review()`.

### 🔴 `false-assumption-dual-exit-bypasses-posting` — Dual Exit Points in `run_pr_review` Bypass Review Posting on Fallbacks · false-assumption · 2/3 · confidence high
- **Step:** Group 2, Task 2.A (Implement Review Posting in `pr_reviewer_agent.py`)
- **Failure:** `run_pr_review()` in `.github/scripts/pr_reviewer_agent.py` contains two independent return points calling `_write_pr_reports(report)` (line 264 inside the live agent `try` block and line 300 in the deterministic fallback block). The plan specifies inserting `post_github_pr_review()` at a single location. If only placed in one block, the alternate execution path (e.g., deterministic fallback used during offline CI or test runs) returns early without posting the review to GitHub.
- **Evidence:** `.github/scripts/pr_reviewer_agent.py:264-265, 300-301`; `plans/active_milestones/pr-review-comment-posting/plan.md:352-363`.
- **Fix:** Refactor `run_pr_review()` to unify report persistence, review posting, and return statements into a single, consolidated exit block at the end of the function.

### 🔴 `hidden-coupling-unmocked-network-in-existing-tests` — Existing Unit Tests Lack Network Mocks Leading to Socket Timeouts · hidden-coupling · 2/3 · confidence high
- **Step:** Group 2, Task 2.A & Group 3, Task 3.A (Full Test Suite Execution)
- **Failure:** Existing tests (`test_run_pr_review_mock_agent_approve`, `test_run_pr_review_mock_agent_config_and_telemetry`, `test_run_pr_review_streams_thinking_and_output`) execute `run_pr_review()` with mock tokens and PR numbers (`pr_number="123"`, `repo="owner/repo"`, `token="ghp_testtoken"`). Once `post_github_pr_review()` is integrated into `run_pr_review()`, these existing tests will invoke real HTTP requests to `api.github.com` via `_send_github_review_sync()`, causing 10-second socket timeout delays or network failure errors during test execution.
- **Evidence:** `.github/scripts/tests/test_pr_reviewer_agent.py:245-253, 284-291, 338-346`; `plans/active_milestones/pr-review-comment-posting/plan.md:355-361`.
- **Fix:** Include a step in Task 1.A to update existing tests in `.github/scripts/tests/test_pr_reviewer_agent.py` to patch `post_github_pr_review` or mock `urllib.request.urlopen`.

## Unconfirmed (FYI · 1 vote)

| `id` | severity | step | note |
|---|---|---|---|
| `false-assumption-missing-token-warning-suppressed` | 🟠 medium | Group 2 Task 2.A | In `run_pr_review()`, checking `if pr_number and repo and token:` suppresses `post_github_pr_review()`'s internal check and warning log when `token` is missing. Guard with `if pr_number:` instead. |
| `false-assumption-httperror-read-attribute-error` | 🟠 medium | Group 2 Task 2.A (`_send_github_review_sync`) | In Python `urllib.error.HTTPError`, calling `e.read()` when mocked with `fp=None` raises `AttributeError`. Guard with `if getattr(e, "fp", None) is not None:`. |
| `hidden-coupling-acceptance-test-import-resolution` | 🟠 medium | Group 1 Task 1.B | `.github/tests/test_pr_reviewer_acceptance.py` contains a dynamic fallback loader that needs `sys.path.insert(0, os.path.abspath(".github/scripts"))` to import newly added symbols reliably. |
| `false-assumption-scorer-main-raises-not-implemented` | 🟠 medium | Group 3 Task 3.A Step 2 | Task 3.A Step 2 commands `uv run python scorer/main.py`, but `scorer/usage.py` raises `NotImplementedError` and is out of scope for this milestone. Omit `scorer/main.py` CLI execution from verification. |

## Checks That Passed
- Canonical positive approval template string matches `docs/spec.md` Decision D-1 verbatim — `plans/active_milestones/pr-review-comment-posting/plan.md:98-99, 184-189`
- Pydantic model schemas (`PRReviewReport`, `InlineFinding`, `ReviewStatus`, `PRFindingSeverity`) exist and match specifications — `.github/scripts/pr_reviewer_agent.py:18-60`
- `validate_and_sanitize_findings` and `format_pr_review_text` exist and function as expected — `.github/scripts/pr_reviewer_agent.py:62-114`
- Artifact paths (`reports/pr-review.json` and `reports/pr-review.txt`) align with workflow and spec requirements — `.github/workflows/source-code-pii-review.yml:148`
- Parameter priority (`sys.argv` > primary env > fallback env) and repository sanitization match Decision D-8 — `plans/active_milestones/pr-review-comment-posting/plan.md:192-203, 366-382`
- Bounded 422 fallback retry (max 1 retry, skipped on empty comments) matches Decision D-6 — `plans/active_milestones/pr-review-comment-posting/plan.md:323-344`
- Graceful exit on non-PR / push events (exit 0, no API calls) matches Decision D-4 and existing behavior — `.github/scripts/pr_reviewer_agent.py:129-136`
- Pytest configuration in `pyproject.toml` correctly discovers `.github/scripts/tests` and `.github/tests` with `asyncio_mode = "auto"` — `pyproject.toml:20-23`
- Clean separation of concerns is preserved with core `scorer/` domain remaining untouched — `AGENTS.md:208`

## Actions Taken
- [x] **Corrected Group 1 & Task 1.A / 1.B Prerequisites:** Added stub interfaces declaration (`post_github_pr_review` and `POSITIVE_APPROVAL_TEMPLATE`) in `.github/scripts/pr_reviewer_agent.py` so test suites import without collection errors (`ordering-missing-stubs-import-error`).
- [x] **Updated `run_pr_review` Signature & Call Site:** Added `modified_files_diff: Optional[dict[str, list[int]]] = None` to `run_pr_review()` and forwarded it to `post_github_pr_review()` (`hidden-coupling-missing-diff-param-drops-inline-comments`).
- [x] **Unified `run_pr_review` Exit Block:** Consolidated report persistence and `post_github_pr_review()` into a single exit block covering both live agent and deterministic fallback paths (`false-assumption-dual-exit-bypasses-posting`).
- [x] **Added Mocking to Existing Tests:** Updated Task 1.A to patch `post_github_pr_review` or mock `urlopen` in existing agent unit tests (`hidden-coupling-unmocked-network-in-existing-tests`).
- [x] **Hardened `_send_github_review_sync` HTTPError Reading:** Guarded `e.fp` before reading error bodies to prevent `AttributeError` on mocked exceptions (`false-assumption-httperror-read-attribute-error`).
- [x] **Adjusted CLI Verification in Task 3.A:** Removed out-of-scope `scorer/main.py` invocation and tightened validation strictly to `.github/` test suite and agent CLI (`false-assumption-scorer-main-raises-not-implemented`).
