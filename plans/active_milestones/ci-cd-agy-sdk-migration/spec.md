# Product Specification: CI/CD Antigravity Python SDK Migration

**Status:** Approved  
**Milestone:** `ci-cd-agy-sdk-migration`  
**Target Release:** `v1.0.0`  

---

## 🎯 Executive Summary
* **Goal:** Migrate the CI/CD Quality Gate and PR Code Review pipeline ([`.github/workflows/source-code-pii-review.yml`](file:///Users/yannipeng/git-projects/workshop-agentic-sdlc-lab/.github/workflows/source-code-pii-review.yml)) from the standalone `agy` CLI to the **Google Antigravity Python SDK** (`google-antigravity`), utilizing GCP Workload Identity Federation (WIF), Vertex AI Application Default Credentials (ADC), and strict Pydantic model validation.
* **Target User:** DevOps Engineers, Release Managers, Security Engineers, and Software Engineers submitting PRs to the repository.
* **Business Value:** Eliminates brittle shell/grep text parsing in CI gates, enforces zero-trust keyless authentication (no stored API keys or long-lived service account secrets), delivers deterministic Pydantic-typed quality gate decisions, and provides automated, line-level code and PII review comments via GitHub MCP.

---

## 🛠️ User Stories & Workflows

### User Stories
- **Story 1 (Type-Safe Security Gatekeeper):** As a Security Engineer, I want the CI quality gate agent to evaluate Cloud DLP scan outputs and PR reviews against strict security criteria using a deterministic Pydantic schema so that any PII or credential leak immediately halts the pipeline with an actionable failure breakdown.
- **Story 2 (Automated PR Reviewer):** As a Developer submitting a Pull Request, I want an autonomous review agent to inspect diffs and DLP scan findings via GitHub MCP, posting structured inline findings with file paths, line numbers, and remediation guidance.
- **Story 3 (Keyless Cloud Authentication):** As a Cloud Infrastructure Engineer, I want the CI agent scripts to authenticate to Vertex AI using GitHub Actions Workload Identity Federation (WIF) and Application Default Credentials (`vertex=True`) so that no static `GEMINI_API_KEY` or long-lived credentials exist in repository secrets.
- **Story 4 (Traceable CI Execution & Telemetry):** As a Release Engineer, I want CI logs and step summaries to display structured JSON decision summaries and archive isolated session telemetry to Google Cloud Storage (GCS) so that every release evaluation is fully auditable.

### Operational Workflow
```mermaid
sequenceDiagram
    autonumber
    participant GHA as GitHub Actions Runner
    participant WIF as GCP Workload Identity Pool
    participant DLP as Google Cloud DLP
    participant PRA as PR Reviewer Agent (SDK)
    participant QGA as Quality Gate Agent (SDK)
    participant VTX as Vertex AI (ADC Standard Mode)
    participant GCS as Google Cloud Storage

    GHA->>WIF: Authenticate via OIDC (google-github-actions/auth@v2)
    WIF-->>GHA: Export ADC (GOOGLE_APPLICATION_CREDENTIALS)
    GHA->>DLP: Inspect workspace files (reports/pii-scan.txt)
    
    alt Pull Request Event
        GHA->>PRA: Run .github/scripts/pr_reviewer_agent.py
        PRA->>VTX: Evaluate diff + DLP findings via GitHub MCP
        VTX-->>PRA: Structured PRReviewReport (Pydantic)
        PRA->>GHA: Emit reports/pr-review.json & reports/pr-review.txt
    else Push Event (Non-PR)
        GHA->>PRA: Skip review (PULL_REQUEST_NUMBER unset)
    end

    GHA->>QGA: Run .github/scripts/quality_gate_agent.py
    QGA->>VTX: Evaluate combined DLP & review reports
    VTX-->>QGA: Structured QualityGateDecision (Pydantic)
    QGA->>GHA: Emit reports/gate-decision.json & reports/decision.txt
    GHA->>GCS: Archive reports/ & telemetry
    GHA->>GHA: Enforce gate (passed == true -> exit 0; passed == false -> exit 1)
```

---

## 📋 Acceptance Criteria

### Component 1: Quality Gate Decision Agent (`.github/scripts/quality_gate_agent.py`)

- **Scenario 1: Clean Release Evaluation (All Criteria Pass)**
  - **Given** `reports/pii-scan.txt` with zero DLP findings and `reports/pr-review.txt` (or `reports/pr-review.json`) with no blocking security issues
  - **When** `evaluate_quality_gate()` executes with `response_schema=QualityGateDecision`
  - **Then** the returned `QualityGateDecision.passed` MUST be `True`
  - **And** `QualityGateDecision.failures` MUST be empty (`[]`)
  - **And** `reports/gate-decision.json` MUST be written with valid JSON matching `QualityGateDecision`
  - **And** `reports/decision.txt` MUST begin with header `"GATE_PASSED"` followed by the summary
  - **And** the script process MUST exit with return code `0`

- **Scenario 2: Security or PII Leak Failure Detection**
  - **Given** `reports/pii-scan.txt` containing detected sensitive data (e.g. `AUTH_TOKEN`, `API_KEY`, `EMAIL_ADDRESS`) or `reports/pr-review.txt` / `reports/pr-review.json` containing critical security blockers (`BLOCKER` severity or `pii_leak == True`)
  - **When** `evaluate_quality_gate()` executes
  - **Then** the returned `QualityGateDecision.passed` MUST be `False`
  - **And** `QualityGateDecision.failures` MUST contain at least one `FailureDetail` with `category` matching `PII_LEAK`, `CREDENTIAL_LEAK`, or `SECURITY_VULNERABILITY` and `severity` matching `CRITICAL` or `HIGH`
  - **And** `reports/gate-decision.json` MUST contain the populated `failures` array with `severity`, `component`, `reason`, and `remediation`
  - **And** `reports/decision.txt` MUST begin with header `"GATE_FAILED"` and enumerate all detected failures
  - **And** the script process MUST exit with return code `0` upon successfully generating report artifacts (delegating pipeline halting to the dedicated CI enforcement step, unless `--enforce` flag is explicitly provided)

- **Scenario 3: Missing Input Report Fallbacks & Fail-Closed Security Policy**
  - **Given** missing, unreadable, or empty `reports/pii-scan.txt` or `reports/pr-review.txt` files on the filesystem
  - **When** `evaluate_quality_gate()` executes
  - **Then** the agent MUST NOT crash with `FileNotFoundError`
  - **And** if `reports/pii-scan.txt` is missing, unreadable, or empty (0 bytes), the agent MUST evaluate the release as failing with `QualityGateDecision.passed = False` and populate `QualityGateDecision.failures` with:
    - `category`: `ViolationCategory.SECURITY_VULNERABILITY`
    - `severity`: `SeverityLevel.CRITICAL`
    - `component`: `"Cloud DLP"`
    - `reason`: `"Required Cloud DLP scan report (reports/pii-scan.txt) is missing, unreadable, or empty"`
    - `remediation`: `"Ensure Cloud DLP scan step executes successfully before quality gate evaluation"`
  - **And** if `reports/pr-review.txt` is missing during a push event (non-PR), default fallback text (`"No PR review report available (push event or non-PR)."`) MUST be supplied to the prompt context without causing a gate failure
  - **And** if `reports/pr-review.txt` / `reports/pr-review.json` is missing during an active pull request event (`PULL_REQUEST_NUMBER` is set), the agent MUST evaluate `QualityGateDecision.passed = False` with `category="SECURITY_VULNERABILITY"`, `severity="HIGH"`, and reason explaining missing PR review

- **Scenario 4: Strict Pydantic Model Schema & Invariant Enforcement**
  - **Given** the response from `agent.chat()`
  - **When** `response.structured_output()` is resolved
  - **Then** data MUST be validated via `QualityGateDecision.model_validate(raw_output)` conforming strictly to:
    - `SeverityLevel(str, Enum)`: `CRITICAL = "CRITICAL"`, `HIGH = "HIGH"`, `MEDIUM = "MEDIUM"`, `LOW = "LOW"`
    - `ViolationCategory(str, Enum)`: `PII_LEAK = "PII_LEAK"`, `CREDENTIAL_LEAK = "CREDENTIAL_LEAK"`, `SECURITY_VULNERABILITY = "SECURITY_VULNERABILITY"`, `ARCHITECTURAL_DEFECT = "ARCHITECTURAL_DEFECT"`
    - `FailureDetail(BaseModel)`: `category: ViolationCategory`, `component: str`, `severity: SeverityLevel`, `reason: str`, `remediation: str`
    - `QualityGateDecision(BaseModel)`: `passed: bool`, `summary: str`, `failures: list[FailureDetail]`
  - **And** `QualityGateDecision` MUST implement a Pydantic `@model_validator(mode="after")` enforcing invariant consistency:
    - If `passed is True`, `len(failures)` MUST equal `0` (otherwise raise `ValueError("QualityGateDecision cannot be passed=True with non-empty failures")`)
    - If `passed is False`, `len(failures)` MUST be `>= 1` (otherwise raise `ValueError("QualityGateDecision cannot be passed=False with empty failures")`)

---

### Component 2: PR Reviewer Agent (`.github/scripts/pr_reviewer_agent.py`)

- **Scenario 5: PR Review Execution & Comment Mutation via GitHub MCP**
  - **Given** an active pull request event where `PULL_REQUEST_NUMBER` is populated, `GH_TOKEN` is present, and `GITHUB_REPOSITORY` is provided
  - **When** `run_pr_review()` is executed
  - **Then** the agent MUST configure `types.McpStdioServer` launching container `ghcr.io/github/github-mcp-server:v0.27.0` with:
    - `command="docker"`
    - `args=["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_REPOSITORY", "ghcr.io/github/github-mcp-server:v0.27.0"]`
    - `env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GH_TOKEN"], "GITHUB_REPOSITORY": os.environ.get("GITHUB_REPOSITORY", "")}`
  - **And** the agent MUST invoke GitHub MCP tools using `GH_TOKEN` to submit a pull request review (`APPROVE`, `REQUEST_CHANGES`, or `COMMENT`) and publish comments on the target pull request
  - **And** the agent MUST validate output against `PRReviewReport`
  - **And** `reports/pr-review.json` MUST be written with the structured report matching `PRReviewReport`
  - **And** `reports/pr-review.txt` MUST be written with overall status, summary, and formatted list of findings
  - **And** the script MUST exit with return code `0`

- **Scenario 6: Graceful Skip on Push / Non-PR Events**
  - **Given** a push event where `PULL_REQUEST_NUMBER` environment variable is unset or empty
  - **When** `run_pr_review()` is executed
  - **Then** the script MUST print `"No pull request number provided; skipping PR review."`
  - **And** the script MUST exit immediately with return code `0` without invoking LLM or MCP servers

- **Scenario 7: Line-Level Finding Attribution & Diff Coordinate Validation**
  - **Given** code issues or PII detected in specific modified files
  - **When** `InlineFinding` and `PRReviewReport` models are generated conforming strictly to:
    - `ReviewStatus(str, Enum)`: `APPROVE = "APPROVE"`, `REQUEST_CHANGES = "REQUEST_CHANGES"`, `COMMENT = "COMMENT"`
    - `PRFindingSeverity(str, Enum)`: `BLOCKER = "BLOCKER"`, `WARNING = "WARNING"`, `SUGGESTION = "SUGGESTION"`, `INFO = "INFO"`
    - `InlineFinding(BaseModel)`: `file_path: str`, `line_number: Optional[int] = None`, `severity: PRFindingSeverity`, `title: str`, `details: str`, `suggestion: str`, `pii_leak: bool = False`
    - `PRReviewReport(BaseModel)`: `overall_status: ReviewStatus`, `summary: str`, `findings: list[InlineFinding]`
  - **Then** if any finding contains `severity == PRFindingSeverity.BLOCKER` or `pii_leak == True`:
    - `PRReviewReport.overall_status` MUST be `ReviewStatus.REQUEST_CHANGES`
    - In Quality Gate evaluation, the finding MUST map to `SeverityLevel.CRITICAL` and force `QualityGateDecision.passed = False`
  - **And** `pr_reviewer_agent.py` MUST validate that `file_path` exists in the modified files of the PR diff and `line_number` falls within modified diff hunk ranges
  - **And** if `line_number` is missing, `None`, or outside modified diff hunks, the agent MUST NOT attempt an inline review comment with invalid coordinates (preventing GitHub API 422 errors) and MUST instead append the finding to the top-level PR review comment body

---

### Component 3: GitHub Actions Workflow (`.github/workflows/source-code-pii-review.yml`)

- **Scenario 8: Keyless WIF & Vertex AI ADC Authentication**
  - **Given** the workflow execution triggered on `push` to `main` or `pull_request`
  - **When** step `Authenticate to Google Cloud (WIF)` runs
  - **Then** it MUST use `google-github-actions/auth@v2` with `workload_identity_provider` and `service_account`
  - **And** all Python agent steps MUST execute with `vertex=True` and environment variables `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` (defaulting to model `gemini-3.7-flash` with medium thinking budget, strictly requiring no model less than Gemini 3.5 Flash)
  - **And** the workflow MUST NOT require or reference any `GEMINI_API_KEY`

- **Scenario 9: Standard Python Dependency Lifecycle**
  - **Given** runner initialization
  - **When** setting up the environment
  - **Then** the workflow MUST use `actions/setup-python@v5` with Python `3.11`
  - **And** dependencies MUST be installed via `pip install google-antigravity "pydantic>=2.0.0,<3.0.0"`
  - **And** the legacy `curl | bash` installation of `agy` CLI MUST be completely removed

- **Scenario 10: Rich Step Summary & Telemetry Archival**
  - **Given** completion of the scan and evaluation steps
  - **When** `Generate GitHub Actions Job Summary` and `Upload Audit Reports & Telemetry to GCS` execute
  - **Then** `$GITHUB_STEP_SUMMARY` MUST display `GATE PASSED` or `GATE FAILED` along with the JSON decision summary
  - **And** all artifacts under `reports/` (including `reports/telemetry/`) MUST be uploaded to `gs://${GOOGLE_CLOUD_PROJECT}-scan-reports/${RUN_ID}_${RUN_ATTEMPT}`

- **Scenario 11: Deterministic Quality Gate Enforcement**
  - **Given** `reports/gate-decision.json` generated by `quality_gate_agent.py` (which completed and exited `0`)
  - **When** the downstream `Enforce Quality Gate` step evaluates `reports/gate-decision.json`
  - **Then** if `passed == true`, the step MUST succeed (exit code 0)
  - **And** if `passed == false` or the file is missing/corrupted, the step MUST fail with exit code 1 and halt the pipeline after summaries and telemetry have been captured

---

## 🚨 Constraints & Architecture

1. **Authentication Mode:**
   - Must use standard Vertex AI mode with `vertex=True` in `LocalAgentConfig`.
   - Never initialize `LocalAgentConfig` with `api_key` or depend on `GEMINI_API_KEY`.
2. **Deterministic Pydantic Validation & Invariants:**
   - Both agents must configure `response_schema` in `LocalAgentConfig`.
   - Output must be deserialized and validated using `.model_validate(raw_output)` to prevent any unstructured text output from bypassing validation.
   - `QualityGateDecision` must enforce consistency invariants via `@model_validator(mode="after")`: `passed is True` requires `len(failures) == 0`, and `passed is False` requires `len(failures) >= 1`.
3. **Isolated Telemetry Directories & Directory Initialization:**
   - `quality_gate_agent.py` must use `app_data_dir=os.path.abspath("reports/telemetry/quality_gate_agent")`.
   - `pr_reviewer_agent.py` must use `app_data_dir=os.path.abspath("reports/telemetry/pr_review_agent")`.
   - Both agent scripts must execute `os.makedirs("reports", exist_ok=True)` and ensure parent directories exist before writing report artifacts.
4. **Backward Compatibility & Dual-Output:**
   - Quality Gate agent must emit both typed JSON (`reports/gate-decision.json`) and formatted text (`reports/decision.txt`).
   - PR Reviewer agent must emit both typed JSON (`reports/pr-review.json`) and formatted text (`reports/pr-review.txt`).
5. **Zero Source Code Pollution:**
   - CI scripts reside strictly in `.github/scripts/`.
   - Core scoring service under `scorer/` remains pure Python with zero CI or cloud dependencies.
6. **GitHub MCP Container Launch & Auth Contract:**
   - PR Reviewer agent initializes `types.McpStdioServer` with `command="docker"`, `args=["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_REPOSITORY", "ghcr.io/github/github-mcp-server:v0.27.0"]`, and `env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GH_TOKEN"], "GITHUB_REPOSITORY": os.environ.get("GITHUB_REPOSITORY", "")}`.
   - Container requires `-i` for interactive stdio JSON-RPC streaming.
7. **Diff Coordinate Resilience:**
   - PR Reviewer agent must validate line coordinates against the PR diff before issuing inline comment tool calls, falling back to top-level PR comments on missing/out-of-hunk lines to avoid GitHub API 422 errors.

---

## 📖 Decisions & Rule Matrix

| ID | Rule | Description & Rationale | Traceability Reference |
|---|---|---|---|
| **D-1** | WIF Keyless Auth | Authenticate to GCP exclusively via Workload Identity Federation OIDC token exchange (`auth@v2`). Zero API keys. | Scenario 8 |
| **D-2** | Vertex AI Standard Mode | Set `vertex=True`, `project=GOOGLE_CLOUD_PROJECT`, `location=GOOGLE_CLOUD_LOCATION` in `LocalAgentConfig`. Default model `gemini-3.7-flash` with medium thinking budget (minimum Gemini 3.5 Flash). | Scenario 1, 5, 8 |
| **D-3** | Pydantic Schema Quality Gate | `QualityGateDecision` defines boolean `passed`, `summary`, and `failures: list[FailureDetail]`, with `@model_validator(mode="after")` invariant enforcing `passed == (len(failures) == 0)`. | Scenario 1, 2, 4 |
| **D-4** | Pydantic Schema PR Review & Severity Mapping | `PRReviewReport` defines `overall_status: ReviewStatus`, `summary: str`, and `findings: list[InlineFinding]`. Findings with `BLOCKER` or `pii_leak=True` mandate `ReviewStatus.REQUEST_CHANGES` and map to `SeverityLevel.CRITICAL` in Quality Gate (`passed=False`). | Scenario 5, 7 |
| **D-5** | Non-PR Event Graceful Exit | `pr_reviewer_agent.py` exits with status `0` immediately when `PULL_REQUEST_NUMBER` is unset or empty without invoking LLM or MCP containers. | Scenario 6 |
| **D-6** | Dual-Output Contract | Both scripts emit structured `.json` for machine validation and formatted `.txt` for human-readable summaries and legacy step compatibility. | Scenario 1, 2, 5 |
| **D-7** | Missing Report Safety & Fail-Closed Policy | Missing or empty `reports/pii-scan.txt` fails closed (`passed=False`, CRITICAL severity). Missing PR review report is permitted only on push/non-PR events; missing PR review on active PR events fails the gate. Scripts never crash with `FileNotFoundError`. | Scenario 3 |
| **D-8** | Python CI Runner Standardization | Use `actions/setup-python@v5` with `pip install google-antigravity "pydantic>=2.0.0,<3.0.0"`. Remove all CLI curl/bash scripts and settings JSON templates. | Scenario 9 |
| **D-9** | Exit Code & Enforcement Separation | `quality_gate_agent.py` exits with status `0` upon successfully writing report artifacts, allowing telemetry and job summaries to be archived; downstream CI step `Enforce Quality Gate` evaluates `reports/gate-decision.json` and halts the pipeline with status `1` if `passed != true` or file missing. | Scenario 2, 11 |
| **D-10** | Telemetry Archival Isolation | Agent session logs written to `reports/telemetry/{agent_name}` and archived to GCS bucket `gs://${PROJECT}-scan-reports/...`. | Scenario 10 |
| **D-11** | GitHub MCP Container Launch Configuration | Launch `ghcr.io/github/github-mcp-server:v0.27.0` via `docker run -i --rm` injecting `GITHUB_PERSONAL_ACCESS_TOKEN` and `GITHUB_REPOSITORY` via environment bindings. | Scenario 5 |
| **D-12** | Diff Coordinate Validation & Fallback | Validate diff coordinates before calling inline comment tools; fallback to top-level review body if line coordinates are invalid or outside modified hunks. | Scenario 7 |

---

## 📂 Deliverables & File Layout

```
.github/workflows/
└── source-code-pii-review.yml     # Transformed GitHub Actions workflow using Python SDK & WIF
scripts/
└── ci/
    ├── quality_gate_agent.py      # Quality Gate Agent with QualityGateDecision schema
    └── pr_reviewer_agent.py       # PR Reviewer Agent with GitHub MCP and PRReviewReport schema
plans/
├── 00-ROADMAP.md                  # Updated roadmap with active milestone
└── active_milestones/
    └── ci-cd-agy-sdk-migration/
        ├── context.md             # Research context report
        └── spec.md                # This formal Gherkin specification
```
