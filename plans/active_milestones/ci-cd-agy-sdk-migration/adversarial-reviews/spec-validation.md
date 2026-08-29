# Spec Adversarial Review — CI/CD Antigravity Python SDK Migration

> `spec-validator` · 3 independent skeptics, no shared scratchpad · default-to-reject · 2-of-3 majority gate

| Field | Value |
|---|---|
| Milestone | `ci-cd-agy-sdk-migration` |
| Artifact | `plans/active_milestones/ci-cd-agy-sdk-migration/spec.md` |
| Date | 2026-08-28 |
| Gate | 2-of-3 majority gate |
| Result | **7 confirmed · 10 unconfirmed** — highest severity **🔴 high** |

## Verdict
The specification has solid structural foundations and clear intent, but contains **critical gaps and contradictions** that block immediate implementation planning. Specifically, conflicting exit-code responsibilities between the Python agent and GitHub Actions, a fail-open security hole when scan reports are missing, lack of explicit GitHub comment mutation criteria in acceptance tests, and unmapped PR review enums must be tightened before tactical planning begins.

---

## Confirmed Findings (≥ 2 votes)

### 🔴 `workflow-gate-exit-code-contradiction` — Conflicting Exit Code & Enforcement Lifecycle · 3/3 votes
- **Clause:** Scenario 2: *"And the script process MUST exit with return code 1"* vs Scenario 11: *"When the Enforce Quality Gate step evaluates reports/gate-decision.json Then if passed == false or the file is missing, the step MUST fail with exit code 1"*
- **Malicious reading:** If `quality_gate_agent.py` exits with return code 1 on failure, GitHub Actions aborts execution immediately at that step. The dedicated `Enforce Quality Gate` step (Scenario 11 / Decision D-9) is skipped as dead code, and telemetry/summary upload steps are skipped unless configured with `if: always()`.
- **Harm:** Pipeline telemetry and Step Summaries fail to upload on gate failures, creating brittle workflow step interactions and dead enforcement code.
- **Tightening:** Disambiguate exit code contracts: `quality_gate_agent.py` MUST always exit with return code `0` after successfully generating `reports/gate-decision.json` and `reports/decision.txt` (even when `passed == False`), delegating pipeline termination exclusively to the downstream `Enforce Quality Gate` step following telemetry archival.

---

### 🔴 `missing-dlp-scan-fails-open` — Missing DLP Scan Report Fails Open · 3/3 votes
- **Clause:** Scenario 3: *"Then the agent MUST NOT crash with FileNotFoundError And default fallback text (\"No DLP scan report available.\" / \"No PR review report available (push event or non-PR).\") MUST be supplied to the prompt context"*
- **Malicious reading:** If the Cloud DLP scan step crashes, times out, or fails to execute, `reports/pii-scan.txt` will be missing. Supplying fallback text containing zero detected findings causes the LLM to evaluate the release as clean, setting `QualityGateDecision.passed = True` and passing the gate without any security inspection.
- **Harm:** Critical security bypass: upstream DLP failures or omissions permit uninspected source code containing sensitive PII or credentials to be approved for deployment.
- **Tightening:** In Scenario 3 and Decision D-7, mandate that missing or empty `reports/pii-scan.txt` MUST evaluate to `QualityGateDecision.passed = False` with a `FailureDetail(category="SECURITY_VULNERABILITY", severity="CRITICAL", component="Cloud DLP", reason="Required DLP scan report missing or empty", remediation="Ensure Cloud DLP scan step executes successfully before quality gate evaluation")`.

---

### 🔴 `pr-reviewer-no-comment-mutation` — Missing Explicit GitHub MCP Comment Mutation Requirement · 3/3 votes
- **Clause:** Scenario 5: *"Then the agent MUST configure types.McpStdioServer launching container ghcr.io/github/github-mcp-server:v0.27.0 And the agent MUST validate output against PRReviewReport And reports/pr-review.json MUST be written with the structured report And reports/pr-review.txt MUST be written with overall status, summary, and formatted list of findings And the script MUST exit with return code 0"*
- **Malicious reading:** A minimal implementation can configure the `McpStdioServer` object, evaluate the diff purely in memory, write local report files, and exit `0` without ever instructing the LLM to invoke GitHub MCP tools (`create_pull_request_review` or `create_issue_comment`).
- **Harm:** Developers submitting pull requests never receive automated inline review comments or status reviews on GitHub (violating Story 2), while automated tests pass 100%.
- **Tightening:** Add an explicit acceptance requirement to Scenario 5: *"The PR Reviewer Agent MUST invoke GitHub MCP tools using `GH_TOKEN` to submit an official PR review and publish inline review comments on the target pull request for all findings containing a valid `file_path` and `line_number`."*

---

### 🟠 `pr-review-status-and-severity-unmapped` — Incomplete PRReviewReport Schema & Unmapped Severities · 3/3 votes
- **Clause:** Decision D-4: *"`PRReviewReport` defines `overall_status`, `summary`, and `findings: list[InlineFinding]`"* & Scenario 7: *"`severity` (`BLOCKER`, `WARNING`, `SUGGESTION`, `INFO`)"*
- **Malicious reading:** `overall_status` has no enum or defined string values (e.g. `APPROVED`, `CHANGES_REQUESTED`, `COMMENT`). Furthermore, PR review severities (`BLOCKER`, `WARNING`, `SUGGESTION`, `INFO`) have no defined mapping to Quality Gate severities (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), allowing implementations to treat `BLOCKER` as non-blocking.
- **Harm:** Arbitrary status strings break downstream automation, and critical PR security blockers are ignored by the Quality Gate agent.
- **Tightening:** Define explicit Pydantic enums for `ReviewStatus` (`APPROVED`, `CHANGES_REQUESTED`, `COMMENT`) and `PRFindingSeverity` (`BLOCKER`, `WARNING`, `SUGGESTION`, `INFO`). Specify that any PR finding with `severity == BLOCKER` or `pii_leak == True` MUST map to `SeverityLevel.CRITICAL` and trigger `QualityGateDecision.passed = False`.

---

### 🟠 `mcp-container-env-and-stdio-unspecified` — GitHub MCP Container Launch & Auth Parameters Undefined · 2/3 votes
- **Clause:** Scenario 5: *"Then the agent MUST configure types.McpStdioServer launching container ghcr.io/github/github-mcp-server:v0.27.0"*
- **Malicious reading:** The spec does not define container execution flags or environment mapping. Launching `docker run` without `-i` (interactive stdio) or without injecting `GITHUB_PERSONAL_ACCESS_TOKEN` from `GH_TOKEN` will cause the MCP server to terminate immediately on EOF or fail authentication.
- **Harm:** PR reviewer agent crashes immediately upon initialization in CI runners.
- **Tightening:** Specify exact `McpStdioServer` parameters: `command="docker"`, `args=["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server:v0.27.0"]`, and `env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GH_TOKEN"]}`.

---

### 🟠 `schema-passed-failures-consistency-invariant` — Missing Model Validation Invariant on Gate Decision · 2/3 votes
- **Clause:** Scenario 4 & Decision D-3: *"QualityGateDecision: passed: bool, summary: str, failures: list[FailureDetail]"*
- **Malicious reading:** The Pydantic model does not enforce invariant consistency between `passed` and `failures`. An LLM output returning `passed: true` with a populated list of critical vulnerabilities validates successfully.
- **Harm:** Contradictory LLM responses can bypass CI quality gate enforcement despite discovering critical security leaks.
- **Tightening:** Add a Pydantic `@model_validator(mode="after")` to `QualityGateDecision` enforcing that `passed` is `True` if and only if `len(failures) == 0`.

---

### 🟡 `unvalidated-diff-coordinates-api-failure` — Unvalidated Diff Line Coordinates Cause GitHub API Crashes · 2/3 votes
- **Clause:** Scenario 7: *"Then each finding MUST accurately provide file_path, optional line_number, severity..."*
- **Malicious reading:** "Accurately provide" is subjective and untestable. If the LLM generates a line number outside the pull request modified diff hunks, GitHub API calls will fail with `422 Unprocessable Entity`.
- **Harm:** LLM hallucinations on line numbers crash the PR reviewer agent and fail CI runs.
- **Tightening:** Mandate that `pr_reviewer_agent.py` validate that `file_path` exists in the PR diff and `line_number` falls within modified hunk ranges, falling back to top-level review comments if line coordinates are invalid.

---

## Unconfirmed (FYI · 1 vote)

| `id` | Severity | Clause | Note |
|---|---|---|---|
| `missing-repository-context-for-pr-reviewer` | 🔴 high | `<MISSING>` | Scenario 5 specifies `PULL_REQUEST_NUMBER` and `GH_TOKEN` but omits `GITHUB_REPOSITORY` (`owner/repo`), which is required for GitHub MCP API calls. |
| `missing-api-timeout-and-network-error-behavior` | 🟠 medium | `<MISSING>` | No timeout, retry, or exception handling specified for Vertex AI API / MCP calls during transient network outages. |
| `unstructured-text-input-to-quality-gate` | 🟠 medium | Scenario 1, Scenario 2 | Quality Gate ingests freeform text files instead of typed JSON (`reports/pr-review.json`), preserving prompt hallucination risks. |
| `severity-level-pass-fail-contradiction` | 🟠 medium | Scenario 1 | Non-blocking warnings (`MEDIUM`/`LOW`) cannot be recorded in `failures` without forcing `passed = False`; suggests a `warnings` field. |
| `model-name-and-api-error-handling-missing` | 🟠 medium | `<MISSING>` | Specification does not fix or parametrize the Gemini model name (e.g. `gemini-2.5-flash`). |
| `missing-gh-token-behavior-unspecified` | 🟠 medium | Scenario 5, Scenario 6 | Undefined behavior if `PULL_REQUEST_NUMBER` is set (e.g., fork PR) but `GH_TOKEN` is missing or empty. |
| `text-output-format-unspecified` | 🟡 low | Scenario 1, Scenario 5 | Exact line formatting and delimiters for `reports/decision.txt` and `reports/pr-review.txt` are not standardized in a template. |
| `reports-directory-creation-unspecified` | 🟡 low | Constraints 3 & 4 | Missing explicit requirement to call `os.makedirs("reports", exist_ok=True)` before opening report files. |
| `unpinned-dependencies-pydantic-v2-incompatibility` | 🟡 low | Scenario 9 | `pip install google-antigravity pydantic` unpinned in CI risks Pydantic v1 / breaking upstream changes. |
| `invalid-pr-number-handling-missing` | 🟡 low | Scenario 6 | Non-integer or malformed string values in `PULL_REQUEST_NUMBER` are not explicitly handled. |

---

## Attacks That Failed
- **WIF & Vertex AI ADC Keyless Authentication:** Verified that configuring `google-github-actions/auth@v2` with `vertex=True` in `LocalAgentConfig` provisions ADC securely without requiring `GEMINI_API_KEY`.
- **Core Scorer Isolation (`scorer/`):** Verified that Constraint 5 strictly prevents CI/SDK dependencies from polluting the pure-Python `scorer/` package.
- **Push Event Guard:** Verified that Scenario 6 and Decision D-5 mandate an immediate zero-exit when `PULL_REQUEST_NUMBER` is unset or empty without invoking LLMs or MCP containers.
- **GCS Telemetry Bucket Destination Collisions:** Verified that `${RUN_ID}_${RUN_ATTEMPT}` guarantees distinct, non-overlapping destination paths per execution attempt in GitHub Actions.

---

## Actions Taken
- [x] Folded `workflow-gate-exit-code-contradiction` tightening into spec Scenario 2, Scenario 11, and Decision D-9
- [x] Folded `missing-dlp-scan-fails-open` tightening into spec Scenario 3 and Decision D-7
- [x] Folded `pr-reviewer-no-comment-mutation` tightening into spec Scenario 5
- [x] Folded `pr-review-status-and-severity-unmapped` tightening into spec Scenario 4, Scenario 7, and Decision D-4
- [x] Folded `mcp-container-env-and-stdio-unspecified` tightening into spec Scenario 5, Constraint 6, and Decision D-11
- [x] Folded `schema-passed-failures-consistency-invariant` tightening into spec Scenario 4, Constraint 2, and Decision D-3
- [x] Folded `unvalidated-diff-coordinates-api-failure` tightening into spec Scenario 7, Constraint 7, and Decision D-12
- [x] Surfaced unconfirmed findings (e.g. `GITHUB_REPOSITORY` env var, API timeouts, reports directory creation, and pinned dependencies) into spec scenarios and constraints
- [ ] Re-ran panel on revision → `spec-validation-r2.md` _(or: not needed)_
