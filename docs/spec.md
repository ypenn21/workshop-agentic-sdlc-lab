# Automated GitHub PR Review & Positive Comment Posting

**Status:** Approved

## What this does

Enhances the Automated PR Reviewer Agent (`.github/scripts/pr_reviewer_agent.py`) to submit formal GitHub Pull Request Reviews (`POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`). It delivers deterministic positive, encouraging approval comments acknowledging clean diffs and zero DLP findings when PRs are clean, posts structured inline and summary comments when defects or security findings exist, and provides bounded 422 fallback resilience and non-fatal network error handling.

## Input

### 1. Function & Execution Parameters
- `report`: `PRReviewReport` Pydantic model instance containing `overall_status`, `summary`, and `findings` list.
- `pr_number`: String or integer representing the active pull request number (e.g. `"42"` or `42`).
- `repo`: String representing the repository in `owner/repo` format (e.g. `"octocat/Hello-World"`). Sanitized to strip whitespace, quotes, and `.git` suffix.
- `token`: GitHub Personal Access Token or GitHub Actions token (`GH_TOKEN`, `GITHUB_TOKEN`, or `GITHUB_PERSONAL_ACCESS_TOKEN`) with `pull-requests: write` permission.
- `modified_files_diff`: Optional dictionary mapping modified file paths to lists of modified line numbers (`dict[str, list[int]] | None`) representing diff hunks.

### 2. Environment Variables & CLI Inputs
- Parameter resolution hierarchy: `sys.argv` (CLI argument) > Primary Environment Variable > Fallback Environment Variable.
  - PR Number: `sys.argv[1]` > `PULL_REQUEST_NUMBER` > `PR_NUMBER`
  - Repository: `sys.argv[2]` > `GITHUB_REPOSITORY` > `REPOSITORY`
  - Token: `sys.argv[3]` > `GH_TOKEN` > `GITHUB_TOKEN` > `GITHUB_PERSONAL_ACCESS_TOKEN`
- If `pr_number` is unset or empty, the review agent gracefully skips execution and exits with status `0`.

---

## The two halves

The interface contract specifies domain types, Pydantic schemas, function signatures, and GitHub REST API review payload schemas.

### 1. Domain Models & Pydantic Schemas

```python
from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field, model_validator


class PRFindingSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    SUGGESTION = "SUGGESTION"
    INFO = "INFO"


# Backward compatibility alias
ReviewSeverity = PRFindingSeverity


class ReviewStatus(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class InlineFinding(BaseModel):
    file_path: str
    line_number: Optional[int] = None
    severity: PRFindingSeverity
    title: str
    details: str
    suggestion: str = ""
    pii_leak: bool = False


class PRReviewReport(BaseModel):
    overall_status: ReviewStatus
    summary: str
    findings: list[InlineFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_blocker_status(self) -> "PRReviewReport":
        """Enforces REQUEST_CHANGES if any finding has BLOCKER severity or pii_leak is True."""
        has_blocker = any(
            f.severity == PRFindingSeverity.BLOCKER or f.pii_leak
            for f in self.findings
        )
        if has_blocker and self.overall_status != ReviewStatus.REQUEST_CHANGES:
            self.overall_status = ReviewStatus.REQUEST_CHANGES
        return self
```

### 2. Function Signatures

```python
def validate_and_sanitize_findings(
    findings: list[InlineFinding],
    modified_files_diff: dict[str, list[int]],
) -> tuple[list[InlineFinding], list[InlineFinding]]:
    """Separates findings into valid inline findings (in diff hunks) and general findings (out of hunk / file level)."""
    ...


def format_pr_review_text(report: PRReviewReport) -> str:
    """Converts PRReviewReport into human-readable text summary detailing status, summary, and itemized findings."""
    ...


def _write_pr_reports(report: PRReviewReport) -> None:
    """Writes JSON and text review artifacts to reports/pr-review.json and reports/pr-review.txt."""
    ...


async def post_github_pr_review(
    report: PRReviewReport,
    pr_number: Union[str, int],
    repo: str,
    token: str,
    modified_files_diff: Optional[dict[str, list[int]]] = None,
) -> bool:
    """Submits a formal GitHub Pull Request Review via GitHub REST API.
    
    Handles positive approvals on clean PRs, inline comment posting, and bounded 422 fallbacks.
    Returns True if successfully posted, or False on non-fatal failure.
    """
    ...


async def run_pr_review(
    pr_number: Optional[str] = None,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    pii_report_path: str = "reports/pii-scan.txt",
    project_id: Optional[str] = None,
    location: str = "us-central1",
) -> Optional[PRReviewReport]:
    """Runs automated PR review evaluation, writes local reports, and posts GitHub review if credentials exist."""
    ...


async def main() -> None:
    """CLI entry point resolving arguments, executing run_pr_review, and exiting 0."""
    ...
```

### 3. Canonical Positive Approval Review Template

When `report.overall_status == ReviewStatus.APPROVE` and `report.findings == []`:
```markdown
## ✅ Automated PR Review: APPROVED

Great job! No code defects, architectural issues, or Cloud DLP security findings were detected in this pull request. All changes look clean and ready to merge.
```

### 4. GitHub REST API Review Contract

- **Endpoint:** `POST https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/reviews`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Accept: application/vnd.github+json`
  - `User-Agent: automated-pr-reviewer/1.0`
  - `X-GitHub-Api-Version: 2022-11-28`
  - `Content-Type: application/json`
- **Timeout:** 10 seconds socket connection and read timeout.
- **Payload Schema:**
  ```json
  {
    "body": "Markdown review text",
    "event": "APPROVE | REQUEST_CHANGES | COMMENT",
    "comments": [
      {
        "path": "file_path",
        "line": 42,
        "body": "**[SEVERITY] Title**\n\nDetails\n\n```suggestion\nsuggestion_code\n```"
      }
    ]
  }
  ```

---

## Rules

1. **Deterministic Positive Approval on Clean PRs:** When `report.overall_status == ReviewStatus.APPROVE` and `len(report.findings) == 0`, submit review with `event: "APPROVE"`, canonical positive body template, and `comments: []`.
2. **Review Event Mapping:** Direct 1-to-1 mapping from `report.overall_status.value`: `APPROVE` -> `"APPROVE"`, `REQUEST_CHANGES` -> `"REQUEST_CHANGES"`, `COMMENT` -> `"COMMENT"`.
3. **Diff Coordinate Sanitization & Inline Findings:** When findings exist, separate into valid inline findings and general findings using `validate_and_sanitize_findings(findings, modified_files_diff)`. Valid inline findings are formatted as comment objects; general findings are appended to the top-level review `body`.
4. **Graceful Non-PR / Push Skip:** If `pr_number` is unset or empty, print `"No pull request number provided; skipping PR review."` and exit cleanly with code `0` without making network calls or invoking LLM.
5. **Network Resilience & Non-Fatal Warning:** Enforce a 10-second timeout on all HTTP requests. Catch network errors, auth failures (401/403), or unexpected exceptions, log `"[Warning] Failed to post PR review to GitHub: <error_message>"`, and exit `0` without crashing CI runner.
6. **Bounded HTTP 422 Fallback:** If initial submission containing `len(comments) > 0` returns HTTP 422, retry at most once with all findings consolidated into the top-level `body` and `comments: []`. If initial request had `comments: []` or retry fails, log warning and do not retry.
7. **Dual-Output Artifact Generation:** Always write `reports/pr-review.json` and `reports/pr-review.txt` to disk prior to attempting review posting.
8. **Parameter Resolution & Repository Sanitization:** Resolve parameters (`sys.argv` > primary env > fallback env), strip quotes/whitespace/`.git` from repo name, and validate `owner/repo` format (contains exactly one `/`).
9. **Zero Findings Non-APPROVE Reviews:** If `findings == []` but `overall_status != ReviewStatus.APPROVE`, submit with `event: report.overall_status.value`, `body: report.summary`, and `comments: []`.
10. **Async Non-Blocking Execution:** `post_github_pr_review` is an async function wrapping synchronous network requests via `asyncio.to_thread`.

---

## Out of scope

- Direct commit pushing or branch creation by the review agent.
- Modifying core application business logic in `scorer/usage.py` or `scorer/main.py`.
- Interactive prompts (`input()`) in CI/CD execution.
- Third-party webhook notifications outside GitHub Pull Request Reviews API.

---

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| --- | --- | --- | --- |
| **D-1** | When `overall_status == ReviewStatus.APPROVE` and `findings == []`, submit GitHub PR Review with `event: "APPROVE"` and canonical positive markdown body acknowledging clean diffs and zero DLP findings | How clean PRs with no findings are reviewed and approved | Submitting a generic comment, leaving no review, or failing to approve clean PRs |
| **D-2** | Map review event directly from `report.overall_status.value`: `APPROVE` -> `"APPROVE"`, `REQUEST_CHANGES` -> `"REQUEST_CHANGES"`, `COMMENT` -> `"COMMENT"`. BLOCKER or PII leak coerces `REQUEST_CHANGES` | How review status translates to GitHub Review API event | Posting COMMENT when BLOCKER or PII leak requires REQUEST_CHANGES |
| **D-3** | Pass `modified_files_diff: dict[str, list[int]]` into `validate_and_sanitize_findings()` to separate valid diff lines from out-of-hunk findings. Out-of-hunk findings are formatted in top-level `body` | How line coordinates are sanitized before sending inline review comments | GitHub API rejecting entire review payload with 422 due to out-of-hunk line coordinates |
| **D-4** | Exit `0` immediately when `PULL_REQUEST_NUMBER` is missing or empty without calling GitHub APIs or LLM | How push events and non-PR workflow runs are handled | Review script crashing or attempting API calls on push events |
| **D-5** | Catch HTTP and connection errors during GitHub review posting with 10s timeout, log non-fatal warnings, and do not fail the CI process | How network failures, token permission errors, or timeouts are handled | CI runner failing and halting deployment due to non-critical review posting errors |
| **D-6** | If review submission fails with HTTP 422 and `len(comments) > 0`, retry at most once with all findings in `body` and `comments: []`. If comments was already empty or retry fails, log warning and skip further retries | How GitHub API 422 Unprocessable Entity errors are handled | Review submission failing completely due to minor diff line number drift or author self-review |
| **D-7** | Ensure `reports/pr-review.json` and `reports/pr-review.txt` are always written to disk before submitting the review | Order of local report generation vs GitHub API call | Missing local artifacts if GitHub API call fails or times out |
| **D-8** | Resolve non-empty parameters (`sys.argv` > primary env var > fallback env var) and validate `owner/repo` format | Priority of CLI arguments vs environment variables and repository name validation | CLI overrides being ignored or malformed repo strings causing unhandled URL errors |
| **D-9** | When `findings == []` but `overall_status != ReviewStatus.APPROVE`, submit with `event: overall_status.value`, `body: report.summary`, and `comments: []` | How zero-finding reports with non-APPROVE status are formatted | Posting positive approval text on a rejected or commented review |
| **D-10** | Define `async def post_github_pr_review(...) -> bool` called within `run_pr_review()` following artifact persistence using `asyncio.to_thread` | How review posting is integrated into the async execution flow | Blocking async event loop with synchronous socket operations or uncalled review posting |

---

## Open questions

None.

---

## The gate

- **Status** is `Approved`
- **Open questions** is empty
- Every rule, in Rules and in Decisions, is directly implementable by a builder without assumptions
