# CI/CD Antigravity Python SDK Migration

**Status:** Approved

## What this does

Migrates the CI/CD Quality Gate and PR Code Review pipeline from shell-based `agy` CLI one-shot execution to the type-safe `google-antigravity` Python SDK (`google-antigravity`) using GCP Workload Identity Federation (WIF) and Vertex AI Application Default Credentials (ADC). It eliminates brittle text/grep parsing in CI pipelines by enforcing deterministic Pydantic structured output models for security quality gates and automated line-level PR code reviews.

## Input

### 1. Quality Gate Agent Inputs (`.github/scripts/quality_gate_agent.py`)
- `reports/pii-scan.txt`: Output text report from the Google Cloud DLP scan step containing detected sensitive data (`EMAIL_ADDRESS`, `AUTH_TOKEN`, `API_KEY`, etc.), finding counts, and inspected file paths.
  - *Guarantees:* File may be missing or 0 bytes if DLP scan failed or was skipped (handled fail-closed).
- `reports/pr-review.txt` / `reports/pr-review.json`: Text and structured JSON review reports emitted by the PR Reviewer Agent.
  - *Guarantees:* Present during pull request events; absent or placeholder text during push (non-PR) events.
- Environment variables:
  - `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID for Vertex AI initialization.
  - `GOOGLE_CLOUD_LOCATION`: Vertex AI region (defaults to `"us-central1"`).
  - `PULL_REQUEST_NUMBER`: String representing the pull request number if executing in a PR context (optional / unset on push events).

### 2. PR Reviewer Agent Inputs (`.github/scripts/pr_reviewer_agent.py`)
- Environment variables:
  - `PULL_REQUEST_NUMBER` / `PR_NUMBER`: Active pull request number. If unset or empty, the script skips execution immediately.
  - `GH_TOKEN` / `GITHUB_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN`: GitHub authentication token with pull request read and comment/review submission permissions.
  - `GITHUB_REPOSITORY` / `REPOSITORY`: Target repository in `owner/repo` format.
  - `GOOGLE_CLOUD_PROJECT`: Google Cloud project ID for Vertex AI initialization.
  - `GOOGLE_CLOUD_LOCATION`: Vertex AI region (defaults to `"us-central1"`).
- `reports/pii-scan.txt`: Cloud DLP scan output provided as context to detect sensitive information in modified PR files.
- PR Git Diff: Changed files, diff hunks, and line additions fetched via GitHub MCP tools.

## The two halves

The interface contract defines data structures, enums, Pydantic schemas, and pure helper signatures implemented in `.github/scripts/quality_gate_agent.py` and `.github/scripts/pr_reviewer_agent.py`.

### 1. Domain Models and Schemas

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ViolationCategory(str, Enum):
    PII_LEAK = "PII_LEAK"
    CREDENTIAL_LEAK = "CREDENTIAL_LEAK"
    SECURITY_VULNERABILITY = "SECURITY_VULNERABILITY"
    ARCHITECTURAL_DEFECT = "ARCHITECTURAL_DEFECT"


class PRFindingSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    SUGGESTION = "SUGGESTION"
    INFO = "INFO"


class ReviewStatus(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class FailureDetail(BaseModel):
    category: ViolationCategory
    component: str
    severity: SeverityLevel
    reason: str
    remediation: str


class QualityGateDecision(BaseModel):
    passed: bool
    summary: str
    failures: list[FailureDetail] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_failures_consistency(self) -> "QualityGateDecision":
        if self.passed and len(self.failures) > 0:
            raise ValueError(
                "QualityGateDecision cannot be passed=True with non-empty failures"
            )
        if not self.passed and len(self.failures) == 0:
            raise ValueError(
                "QualityGateDecision cannot be passed=False with empty failures"
            )
        return self


class InlineFinding(BaseModel):
    file_path: str
    line_number: Optional[int] = None
    severity: PRFindingSeverity
    title: str
    details: str
    suggestion: str
    pii_leak: bool = False


class PRReviewReport(BaseModel):
    overall_status: ReviewStatus
    summary: str
    findings: list[InlineFinding] = Field(default_factory=list)
```

### 2. Pure Helper Signatures

```python
def validate_and_sanitize_findings(
    findings: list[InlineFinding],
    modified_files_diff: dict[str, list[int]],
) -> tuple[list[InlineFinding], list[InlineFinding]]:
    """Separates findings into valid inline findings (where file_path exists in diff and
    line_number is within modified hunks) and general review findings (invalid coordinates,
    missing lines, or out-of-hunk modifications).
    """
    ...


def format_text_decision(decision: QualityGateDecision) -> str:
    """Converts QualityGateDecision into deterministic formatted text starting with
    'GATE_PASSED' or 'GATE_FAILED' followed by summary and failure enumeration.
    """
    ...


def format_pr_review_text(report: PRReviewReport) -> str:
    """Converts PRReviewReport into human-readable text summary detailing review status,
    summary, and itemized findings with remediation suggestions.
    """
    ...
```

### 3. Agent Entry Point Signatures

```python
async def evaluate_quality_gate(
    pii_report_path: str = "reports/pii-scan.txt",
    pr_review_path: str = "reports/pr-review.txt",
    project_id: Optional[str] = None,
    location: str = "us-central1",
    pr_number: Optional[str] = None,
) -> QualityGateDecision:
    """Executes Quality Gate Agent using LocalAgentConfig(vertex=True, response_schema=QualityGateDecision).
    Evaluates scan and review reports fail-closed, writing reports/gate-decision.json and
    reports/decision.txt, and isolated telemetry to reports/telemetry/quality_gate_agent.
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
    """Executes PR Reviewer Agent using LocalAgentConfig(vertex=True, response_schema=PRReviewReport)
    and GitHub MCP Server. Performs line-coordinate validation, submits review and comments,
    writes reports/pr-review.json and reports/pr-review.txt, and logs telemetry to
    reports/telemetry/pr_review_agent.
    """
    ...
```

## Rules

1. **Keyless Vertex AI Authentication (ADC / WIF):**
   - Agents instantiate `LocalAgentConfig` with `vertex=True`, `project=GOOGLE_CLOUD_PROJECT`, `location=GOOGLE_CLOUD_LOCATION` (default `"us-central1"`), and model `gemini-3.7-flash` configured with medium thinking budget (strictly prohibiting models below Gemini 3.5 Flash).
   - Never accept, require, or inspect `GEMINI_API_KEY` or static service account keys in environment or configurations.
2. **Deterministic Quality Gate Evaluation:**
   - Zero tolerance for sensitive data: Any finding in `reports/pii-scan.txt` (or PR review with `pii_leak=True` or `severity=BLOCKER`) mandates `passed=False` with `CRITICAL` or `HIGH` severity `FailureDetail`.
   - Invariant validation: Deserialized responses must pass `QualityGateDecision.model_validate(data)` enforcing `passed == (len(failures) == 0)`.
3. **Fail-Closed Missing Report Safety:**
   - If `reports/pii-scan.txt` is missing, unreadable, or 0 bytes, `evaluate_quality_gate()` evaluates `passed=False` with `category=ViolationCategory.SECURITY_VULNERABILITY`, `severity=SeverityLevel.CRITICAL`, `component="Cloud DLP"`, `reason="Required Cloud DLP scan report (reports/pii-scan.txt) is missing, unreadable, or empty"`, and `remediation="Ensure Cloud DLP scan step executes successfully before quality gate evaluation"`.
   - On push / non-PR events (`PULL_REQUEST_NUMBER` unset), missing `reports/pr-review.txt` defaults to `"No PR review report available (push event or non-PR)."` and does not fail the gate.
   - On active PR events (`PULL_REQUEST_NUMBER` set), missing `reports/pr-review.txt` evaluates `passed=False` with `HIGH` severity.
   - Scripts must never raise unhandled `FileNotFoundError`.
4. **PR Review Non-PR Early Exit:**
   - If `PULL_REQUEST_NUMBER` is unset or empty, `pr_reviewer_agent.py` prints `"No pull request number provided; skipping PR review."` and exits immediately with status `0` without initializing LLM or Docker MCP containers.
5. **GitHub MCP Container Execution & Coordinate Resilience:**
   - PR Reviewer configures `types.McpStdioServer(name="github", command="docker", args=["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_REPOSITORY", "ghcr.io/github/github-mcp-server:v0.27.0"], env={"GITHUB_PERSONAL_ACCESS_TOKEN": token, "GITHUB_REPOSITORY": repo})`.
   - Any finding with `severity == PRFindingSeverity.BLOCKER` or `pii_leak == True` forces `PRReviewReport.overall_status = ReviewStatus.REQUEST_CHANGES`.
   - Inline findings must have `file_path` and `line_number` validated against modified PR diff hunks before calling inline comment tools. Findings on unparseable, `None`, or out-of-hunk lines must fall back to the top-level PR review comment body to prevent GitHub API 422 errors.
6. **Dual-Output and Telemetry Isolation:**
   - Quality gate script writes `reports/gate-decision.json` and `reports/decision.txt`.
   - PR reviewer script writes `reports/pr-review.json` and `reports/pr-review.txt`.
   - Telemetry directories are configured via `app_data_dir` to `reports/telemetry/quality_gate_agent` and `reports/telemetry/pr_review_agent`.
   - All scripts execute `os.makedirs(..., exist_ok=True)` on parent directories before writing files.
7. **Exit Code & Enforcement Separation:**
   - `quality_gate_agent.py` and `pr_reviewer_agent.py` exit with return code `0` upon successfully writing report artifacts, ensuring telemetry collection and job summaries execute.
   - The dedicated CI workflow step `Enforce Quality Gate` evaluates `reports/gate-decision.json` and exits with return code `1` if `passed != true` or the file is missing/corrupt.

## Out of scope

- Interactive CLI prompts (`input()`) or interactive terminal sessions.
- Direct cloud resource provisioning or deployment triggers inside agent Python scripts (handled by GitHub Actions and Terraform).
- Web UI dashboard rendering or HTML report generation (handled natively via `$GITHUB_STEP_SUMMARY` and GCS report archiving).
- Direct Git commit execution by agent scripts.
- Modifying core application domain models or scoring logic in `scorer/usage.py` and `scorer/main.py`.

## Decisions

| ID | Rule a builder follows | Passage it resolves | Case that would differ |
| --- | --- | --- | --- |
| D-1 | Authenticate to GCP and Vertex AI using Workload Identity Federation (WIF) OIDC token exchange (`google-github-actions/auth@v2`) and `vertex=True` with `GOOGLE_APPLICATION_CREDENTIALS` | How agents authenticate without static credentials in CI | Attempting to pass `GEMINI_API_KEY` or static service account keys in environment or agent config |
| D-2 | Configure `LocalAgentConfig` with `vertex=True`, `project=GOOGLE_CLOUD_PROJECT`, `location=GOOGLE_CLOUD_LOCATION` (default `us-central1`), and model `gemini-3.7-flash` with medium thinking budget (minimum allowed model is Gemini 3.5 Flash) | What model provider, region settings, and thinking tier to instantiate SDK agents with | Attempting to use default local Gemini Developer API, unconfigured project ID, or legacy sub-3.5 models |
| D-3 | `QualityGateDecision` requires `passed: bool`, `summary: str`, and `failures: list[FailureDetail]`, with invariant validator enforcing `passed == (len(failures) == 0)` | What schema determines gate pass/fail and prevents inconsistent states | Returning `passed=True` with non-empty failures, or `passed=False` with empty failures |
| D-4 | `PRReviewReport` requires `overall_status: ReviewStatus`, `summary: str`, and `findings: list[InlineFinding]`. Any finding with `BLOCKER` or `pii_leak=True` mandates `ReviewStatus.REQUEST_CHANGES` and maps to `CRITICAL` severity in Quality Gate | How PR findings translate to PR review status and downstream quality gate failures | Returning `APPROVE` or `COMMENT` despite blocker findings or PII leaks |
| D-5 | If `PULL_REQUEST_NUMBER` is unset or empty, `pr_reviewer_agent.py` prints message and exits 0 immediately without invoking LLM or Docker MCP server | What happens when PR review script runs during a `push` event | Script failing or hanging trying to find a non-existent PR on push events |
| D-6 | Quality gate and PR reviewer scripts must emit both structured JSON (`reports/gate-decision.json`, `reports/pr-review.json`) and human-readable formatted text (`reports/decision.txt`, `reports/pr-review.txt`) | How output is formatted for both automated verification and log inspection | Emitting only JSON (breaking text display steps) or only text (breaking typed validation) |
| D-7 | If `reports/pii-scan.txt` is missing, unreadable, or 0 bytes, evaluate `passed=False` with CRITICAL severity. If `reports/pr-review.txt` is missing on push events, use fallback text; on active PR events, evaluate `passed=False`. Scripts never throw `FileNotFoundError` | How missing or corrupted input scan files are handled | Script crashing with `FileNotFoundError` or silently passing when DLP scan was skipped |
| D-8 | Standardize CI runner on `actions/setup-python@v5` (Python 3.11) with `pip install google-antigravity "pydantic>=2.0.0,<3.0.0"`, removing legacy `curl \| bash` `agy` CLI installation | How CI runner installs and manages agent dependencies | Downloading and caching binary `agy` CLI in workflow |
| D-9 | `quality_gate_agent.py` exits with status `0` upon generating reports; downstream step `Enforce Quality Gate` parses `reports/gate-decision.json` and exits `1` if `passed != true` | When and where CI pipeline halts on quality gate failure | Script exiting `1` prematurely, skipping GCS telemetry upload and job summary generation |
| D-10 | Isolate telemetry directories to `reports/telemetry/quality_gate_agent` and `reports/telemetry/pr_review_agent` via `app_data_dir` in `LocalAgentConfig`, archived to GCS bucket `gs://${PROJECT}-scan-reports/${RUN_ID}_${RUN_ATTEMPT}` | How agent telemetry and session logs are isolated and archived | Telemetry files overwriting each other in a shared directory or remaining unarchived |
| D-11 | Launch GitHub MCP container `ghcr.io/github/github-mcp-server:v0.27.0` via `docker run -i --rm` injecting `GITHUB_PERSONAL_ACCESS_TOKEN` from `GH_TOKEN` and `GITHUB_REPOSITORY` | How the PR reviewer agent connects to GitHub MCP server | Missing `-i` flag (breaking stdio JSON-RPC) or missing environment variables |
| D-12 | Validate `file_path` and `line_number` against PR diff hunks before calling inline comment tools; append findings with invalid coordinates to top-level review comment body | How findings on untouched lines or unparseable line numbers are commented | GitHub API throwing 422 Unprocessable Entity when creating review comments on invalid lines |

## Open questions

None.

## The gate

- **Status** is `Approved`
- **Open questions** is empty
- Every rule, in Rules and in Decisions, is directly implementable by a builder without assumptions
