# Research Context Report: PR Reviewer Agent Comment Deduplication Across Pipeline Runs

**Jira Ticket:** [OPS-16] PR Reviewer Agent: Deduplicate PR review comments across pipeline runs  
**Date:** 2026-08-31  

---

## 1. Background & Problem Statement

The repository's automated CI/CD pipeline (`.github/workflows/source-code-pii-review.yml`) triggers on pull request events (`opened`, `synchronize`) to perform Cloud DLP sensitive data scanning and automated code review via `.github/scripts/pr_reviewer_agent.py`.

### Problem:
When developers push subsequent commits to an open pull request (`pull_request: synchronize`) or when workflows are re-run, `.github/scripts/pr_reviewer_agent.py` generates and posts new review comments without querying previously posted comments from earlier runs. 

This causes:
1. **Redundant Duplicate Comments:** Identical inline comments are repeatedly posted on the same file paths and line numbers across runs.
2. **Conversation Clutter:** PR discussions become noisy and harder to navigate.
3. **Review State Inconsistency:** Obsolete or already-commented findings trigger repeated notification alerts.

---

## 2. Codebase Investigation & Existing Architecture

### Relevant Source Files:
- `.github/workflows/source-code-pii-review.yml`:
  - Triggers on `pull_request` types `opened` and `synchronize`.
  - Permissions: `pull-requests: write`, `contents: read`, `id-token: write`.
  - Injects environment variables: `GH_TOKEN`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `PULL_REQUEST_NUMBER`.
- `.github/scripts/pr_reviewer_agent.py`:
  - Pydantic models: `PRFindingSeverity`, `ReviewStatus`, `InlineFinding`, `PRReviewReport`.
  - Helper functions: `_sanitize_and_validate_repo()`, `fetch_pr_modified_lines()`, `_send_github_review_sync()`, `_send_github_issue_comment_sync()`, `validate_and_sanitize_findings()`, `format_pr_review_text()`.
  - Review runner: `run_pr_review()` and `post_github_pr_review()`.
  - GitHub MCP Server integration: `ghcr.io/github/github-mcp-server:v0.27.0`.
- Existing Test Suites:
  - `.github/scripts/tests/test_pr_reviewer_agent.py`
  - `.github/tests/test_pr_reviewer_acceptance.py`
  - `.github/tests/test_workflow_acceptance.py`

---

## 3. Technical Strategy & Integration Points

### 1. Fetching Prior PR Review Comments
- **GitHub REST API Endpoint:**
  `GET https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/comments?per_page=100`
- **MCP Server Alternative / Capability:**
  Querying existing comments and review discussion threads via GitHub MCP tool.
- **Comment Metadata Available:**
  - `id`: Comment ID
  - `path`: File path
  - `line` / `original_line`: Diff line number
  - `body`: Text content of the comment
  - `user`: Author metadata

### 2. Finding Fingerprinting & Deduplication
- Construct a deterministic fingerprint/signature for candidate findings based on:
  - `file_path`
  - `line_number`
  - Normalized title / core message text / severity tag
- Compare candidate findings against fetched prior comments:
  - If a prior comment matching `(file_path, line_number)` and title/signature already exists on the PR, mark as duplicate and omit from new inline comments payload.
  - If a finding is new or modified, retain for posting.

### 3. Idempotent Submission Handling
- **Partial New Findings:** Post only the newly discovered inline findings; update the top-level review summary noting existing findings remain open.
- **Zero New Findings (All duplicates already posted):** If all findings are already posted on the PR and no new issues exist, avoid posting duplicate inline comments; post or update top-level summary.
- **Clean Diff (Zero Findings):** Continue posting positive approval review.

---

## 4. Constraints & Risk Assessment

1. **Network & Rate Limits:** Pagination support for PRs with large comment counts; graceful timeout handling.
2. **Graceful Fallbacks:** If comment retrieval fails due to network/token issues, log warning and gracefully proceed without breaking the CI build.
3. **Compatibility:** Must preserve existing Pydantic validation contracts and backward compatibility with `ReviewSeverity` / `PRReviewReport`.

---

## 5. Next Steps
Pass this report to Phase 1 (`product-owner`) to initiate the Grill Loop, formalize Gherkin acceptance criteria in `spec.md`, and update `plans/00-ROADMAP.md`.
