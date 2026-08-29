# Spec Adversarial Review — Automated GitHub PR Review & Positive Comment Posting

> `spec-validator` · 3 independent skeptics, no shared scratchpad · default-to-reject · 2-of-3 majority gate

| Field | Value |
|---|---|
| Milestone | `pr-review-comment-posting` |
| Artifact | `plans/active_milestones/pr-review-comment-posting/spec.md` |
| Date | 2026-08-28 |
| Gate | 2-of-3 majority gate |
| Result | **7 confirmed · 9 unconfirmed** — highest severity **🔴 high** |

## Verdict
The specification provides a strong foundation for PR review automation and positive feedback posting, but contains **critical gaps and ambiguities** that must be tightened before tactical planning begins. Specifically, the source of diff hunks for inline comment sanitization is unstated, review behavior when `findings == []` with non-APPROVE status is undefined, review event mapping contradicts overall status on suggestions/warnings, the approval body lacks a deterministic testable template, and HTTP 422 fallback logic lacks bounds and empty-comment guards.

---

## Confirmed Findings (≥ 2 votes)

### 🔴 `missing-diff-source-for-sanitization` — Unspecified Diff Hunks Source for Inline Comment Sanitization · 3/3 votes
- **Clause:** Scenario 2 & Decision D-3: *"Then the agent MUST separate findings into valid inline comments (file path and line number within modified diff hunks) and general/out-of-hunk findings using validate_and_sanitize_findings()"*
- **Malicious reading:** The spec mandates calling `validate_and_sanitize_findings(findings, modified_files_diff)`, but never defines how or from where `modified_files_diff` (`dict[str, list[int]]`) is constructed or passed. An implementation can pass `{}` as `modified_files_diff`, categorizing 100% of findings as out-of-hunk and never posting inline comments to diff lines.
- **Harm:** Inline review comments are never submitted to GitHub PR diff lines, violating Scenario 2 and User Story 2 while technically fulfilling the letter of the spec.
- **Tightening:** Explicitly specify that `post_github_pr_review()` accepts `modified_files_diff: dict[str, list[int]] | None = None` (or retrieves modified lines from GitHub API `GET /repos/{owner}/{repo}/pulls/{pull_number}/files` / local git diff), and parses modified line ranges to construct the hunk map before invoking `validate_and_sanitize_findings()`.

---

### 🔴 `empty-findings-non-approve-unhandled` — Unhandled Zero-Findings State with Non-APPROVE Status · 3/3 votes
- **Clause:** Scenario 1: *"And the review evaluation produces PRReviewReport with overall_status == ReviewStatus.APPROVE and findings == []"* vs Scenario 2: *"And the review evaluation produces PRReviewReport containing one or more InlineFinding items"*
- **Malicious reading:** Scenario 1 only specifies behavior when `findings == []` AND `overall_status == ReviewStatus.APPROVE`. Scenario 2 only specifies behavior when `len(findings) >= 1`. If an evaluation produces `findings == []` but `overall_status` is `REQUEST_CHANGES` or `COMMENT` (e.g. general architecture rejection or PR summary feedback with no line-specific finding), neither scenario applies. An implementation could crash, silently drop the review, or mistakenly post an approval with positive encouragement.
- **Harm:** Defective pull requests with zero line-specific findings but an overall `REQUEST_CHANGES` or `COMMENT` status fail to post or erroneously receive an `APPROVE` review.
- **Tightening:** Add an explicit Acceptance Scenario and Decision: When `findings == []` and `overall_status != ReviewStatus.APPROVE`, the agent MUST submit a GitHub PR Review with `event: report.overall_status.value`, `body: report.summary`, and `comments: []` (without positive approval phrasing).

---

### 🔴 `review-event-status-mapping-contradiction` — Review Event Mapping Contradicts Report Overall Status · 2/3 votes
- **Clause:** Scenario 2 & Decision D-2: *"The agent MUST determine the review event: 'REQUEST_CHANGES' if any finding has severity == PRFindingSeverity.BLOCKER or pii_leak == True; 'COMMENT' if findings contain only 'WARNING', 'SUGGESTION', or 'INFO' without blockers or PII leaks"*
- **Malicious reading:** Decision D-2 determines the GitHub review event strictly based on individual finding severities rather than `report.overall_status`. If `report.overall_status` is `ReviewStatus.APPROVE` with an informational finding (e.g. `SUGGESTION`), D-2 forces the review event to `"COMMENT"`, preventing the clean PR from being approved. Conversely, if `report.overall_status` is `ReviewStatus.REQUEST_CHANGES` due to aggregate issues without a single `BLOCKER` item, D-2 forces the event to `"COMMENT"`.
- **Harm:** PRs approved with suggestions are downgraded to non-approving comments, while PRs requested for changes without blockers are submitted as non-blocking comments, defeating GitHub branch protection rules.
- **Tightening:** Align the review event mapping directly to `report.overall_status`: `ReviewStatus.APPROVE` -> `"APPROVE"`, `ReviewStatus.REQUEST_CHANGES` -> `"REQUEST_CHANGES"`, and `ReviewStatus.COMMENT` -> `"COMMENT"`. The Pydantic model validator for `PRReviewReport` already guarantees that any `BLOCKER` or `pii_leak=True` coerces `overall_status` to `ReviewStatus.REQUEST_CHANGES`.

---

### 🟠 `untestable-positive-approval-template` — Vague Positive Approval Message Lacks Deterministic Template · 3/3 votes
- **Clause:** Scenario 1 & Constraint 1: *"body: A positive, encouraging markdown message acknowledging clean diffs, zero PII/DLP findings, and compliance with project quality standards"*
- **Malicious reading:** The requirement relies on subjective prose descriptions ("positive, encouraging markdown message"). A minimal implementation can supply `"LGTM"` or `"good"` or generate non-deterministic text, preventing contract and unit tests from deterministically asserting review body content.
- **Harm:** Untestable acceptance criteria, brittle tests, and inconsistent feedback quality in automated reviews.
- **Tightening:** Fix a canonical, deterministic markdown template for the approval body:
  `"## ✅ Automated PR Review: APPROVED\n\nGreat job! No code defects, architectural issues, or Cloud DLP security findings were detected in this pull request. All changes look clean and ready to merge."`

---

### 🟠 `http-422-fallback-guard-and-bounds` — Unbounded 422 Retry and Redundant Retries on Empty Comments · 3/3 votes
- **Clause:** Scenario 5 & Decision D-6: *"When post_github_pr_review() detects HTTP 422 Then the agent MUST log a warning indicating inline comment placement failure And the agent MUST immediately retry the review submission with all findings consolidated into the top-level body and comments set to []"*
- **Malicious reading:** If the initial request already had `comments == []` (such as an `APPROVE` review that failed HTTP 422 because the bot cannot approve its own PR), or if the fallback request also encounters HTTP 422, an unbound implementation either retries uselessly with identical payloads or risks infinite retry loops.
- **Harm:** Doomed API retries, log pollution claiming inline comments failed when none were submitted, and potential infinite retry recursion on persistent 422 errors.
- **Tightening:** Explicitly mandate that HTTP 422 fallback retry is attempted at most once (max 1 retry), only when the initial request had `len(comments) > 0`. If `comments` was already empty or the fallback request fails, the agent MUST log a warning and proceed without retrying.

---

### 🟠 `review-function-signature-and-caller-hierarchy` — Review Function Signature and Caller Hierarchy Ambiguity · 2/3 votes
- **Clause:** Scenario 1 & Scenario 2: *"When post_github_pr_review() (or review submission lifecycle) executes"*
- **Malicious reading:** The spec does not fix the function signature, sync/async nature, or orchestration point. If called only in `main()`, calling `run_pr_review()` in tests or scripts bypasses posting. If called inside `run_pr_review()` unconditionally, unit tests importing `run_pr_review()` will perform real network calls.
- **Harm:** Interface friction between CLI, test suites, and programmatic callers.
- **Tightening:** Explicitly define the signature `async def post_github_pr_review(report: PRReviewReport, pr_number: str | int, repo: str, token: str, modified_files_diff: dict[str, list[int]] | None = None) -> bool` and specify that `run_pr_review()` orchestrates `post_github_pr_review()` following report generation when credentials and PR number are provided.

---

### 🟡 `missing-repo-format-validation` — Unvalidated Repository Slug String Format · 3/3 votes
- **Clause:** Scenario 1 & Scenario 7: *"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/reviews"*
- **Malicious reading:** If `repo` is provided as an invalid string (e.g. missing `/`, containing whitespace or leading/trailing slashes, or `.git` suffix), URL string formatting produces invalid endpoints (e.g. 404 Not Found) or crashes on string splitting.
- **Harm:** Unhandled exception or unexpected 404 API errors when repository string format deviates from `owner/repo`.
- **Tightening:** Validate that `repo` is sanitized (strip whitespace, trailing `.git`), contains exactly one `/` separating `owner` and `repo`. If invalid, log a warning `"[Warning] Invalid repository format; skipping PR review submission."` and return gracefully without crashing.

---

## Unconfirmed (FYI · 1 vote)

| `id` | Severity | Clause | Note |
|---|---|---|---|
| `missing-user-agent-header` | 🔴 high | Scenario 1, Constraints 1 | GitHub REST API requires `User-Agent` header; omitting it causes HTTP 403 Forbidden. |
| `self-review-author-restriction-unhandled` | 🟠 medium | `<MISSING>` | GitHub returns 422 if bot attempts to approve or request changes on its own PR. Suggests logging warning or falling back to comment. |
| `unspecified-out-of-hunk-and-inline-body-format` | 🟠 medium | Scenario 2 | Inline comment body formatting template: `**[{severity}] {title}**\n\n{details}` + remediation suggestion. |
| `missing-commit-id-and-side-in-inline-comments` | 🟠 medium | Scenario 2 | Specifying `side: "RIGHT"` and commit SHA context in inline comment structures. |
| `missing-http-timeout` | 🟠 medium | `<MISSING>` | Explicit connection and read timeout of 10 seconds for all GitHub REST API requests. |
| `unbounded-payload-size-on-large-diffs` | 🟡 low | Scenario 5 | Truncation guard on review body exceeding GitHub's 65,536 char limit on huge diffs. |
| `blocking-io-in-async-context` | 🟡 low | Constraints 2 | Wrapping synchronous standard library `urllib.request` calls with `asyncio.to_thread` in async context. |
| `top-level-summary-body-composition-ambiguity` | 🟡 low | Scenario 2 | Clarifying total finding count vs out-of-hunk finding count in review body. |
| `cli-positional-empty-string-override` | 🟡 low | Scenario 7 | Ensuring empty string CLI positional arguments do not mask populated environment variables. |

---

## Attacks That Failed
- **Push Event Guard & Zero Exit:** Verified that Scenario 3 and Decision D-4 mandate printing `"No pull request number provided; skipping PR review."` and exiting 0 immediately without invoking LLM or GitHub API.
- **Dual Artifact Generation on Posting Failure:** Verified that Scenarios 4, 6, and Decision D-7 strictly enforce writing `reports/pr-review.json` and `reports/pr-review.txt` prior to review submission.
- **Blocker / PII Invariant Coercion:** Verified that Pydantic model validation and Constraint 3 strictly enforce that any finding with `pii_leak == True` or `severity == BLOCKER` coerces `overall_status` to `ReviewStatus.REQUEST_CHANGES`.
- **Parameter Precedence Order:** Verified that Scenario 7 and Decision D-8 explicitly enumerate the exact 3-tier precedence hierarchy (`sys.argv` > primary env var > fallback env var).

---

## Actions Taken
- [x] Folded `missing-diff-source-for-sanitization` tightening into spec Scenario 2, Scenario 8, and Decision D-3
- [x] Folded `empty-findings-non-approve-unhandled` tightening into spec Scenario 1b and Decision D-9
- [x] Folded `review-event-status-mapping-contradiction` tightening into spec Scenario 2 and Decision D-2
- [x] Folded `untestable-positive-approval-template` tightening into spec Scenario 1 and Constraint 1
- [x] Folded `http-422-fallback-guard-and-bounds` tightening into spec Scenario 5, Constraint 4, and Decision D-6
- [x] Folded `review-function-signature-and-caller-hierarchy` tightening into spec Scenario 8, Constraint 2, and Decision D-10
- [x] Folded `missing-repo-format-validation` tightening into spec Scenario 7 and Constraint 6
- [x] Surfaced unconfirmed findings (`User-Agent` header, 10s socket timeout, inline comment formatting template) into spec requirements
