# Technical Plan: CI/CD Agent Modularization & Reusable Helper Architecture

## 🔍 Analysis & Context
*   **Objective:** Refactor `.github/scripts/pr_reviewer_agent.py` and `.github/scripts/quality_gate_agent.py` by extracting all shared GitHub REST API, report serialization, environment resolution, and agent response streaming logic into a reusable `.github/scripts/helper.py` module, reducing agent files to minimal declarative prompt & config wrappers with 100% test compatibility.
*   **Affected Files:**
    *   `.github/scripts/helper.py` (New reusable utility module)
    *   `.github/scripts/pr_reviewer_agent.py` (Streamlined PR Reviewer agent script with re-exports)
    *   `.github/scripts/quality_gate_agent.py` (Streamlined Quality Gate agent script with re-exports)
    *   `.github/scripts/tests/test_helper.py` (New unit test suite for helper module)
    *   `.github/scripts/tests/test_pr_reviewer_agent.py` (Verification of PR reviewer tests)
    *   `.github/scripts/tests/test_quality_gate_agent.py` (Verification of quality gate tests)
    *   `.github/tests/test_pr_reviewer_acceptance.py` (Verification of PR reviewer acceptance tests)
    *   `.github/tests/test_quality_gate_acceptance.py` (Verification of quality gate acceptance tests)
*   **Key Dependencies:**
    *   `google-antigravity` (`Agent`, `LocalAgentConfig`, `types`)
    *   `pydantic` (`BaseModel`, `Field`, `model_validator`)
    *   Python standard library (`urllib.request`, `urllib.error`, `json`, `os`, `sys`, `re`, `pathlib`, `enum`, `typing`)
*   **Risks/Edge Cases:**
    *   *Test Import Regressions:* Existing tests directly import functions like `_sanitize_and_validate_repo`, `fetch_pr_modified_lines`, `fetch_pr_comments`, `_is_duplicate_comment`, `validate_and_sanitize_findings`, `format_pr_review_text`, `_send_github_review_sync`, `_send_github_issue_comment_sync`, `post_github_pr_review`, and `format_text_decision` from `pr_reviewer_agent` and `quality_gate_agent`. Both agent modules MUST re-export all extracted symbols (citing Decision `D-3` and `D-10`).
    *   *Fail-Closed Guardrails:* `quality_gate_agent.py` MUST preserve deterministic fail-closed safety checks for missing DLP scans and missing PR reviews prior to invoking the LLM (citing Decision `D-9`).
    *   *Pydantic Invariant Validation:* Invariant validation on `PRReviewReport` (`BLOCKER`/`pii_leak` -> `REQUEST_CHANGES`) and `QualityGateDecision` (`passed=True` -> `len(failures)==0`) must remain strictly intact.

---

## 📋 Task Execution (Parallel Groups)

### Group 1 (Foundation & Helper Test Harness)
- [x] Task 1.A: Implement Reusable Helper Module (`.github/scripts/helper.py`) and Unit Test Harness (`.github/scripts/tests/test_helper.py`).

### Group 2 (Parallel Execution - Agent Refactoring, Depends on Group 1)
- [x] Task 2.A: Modularize PR Reviewer Agent (`.github/scripts/pr_reviewer_agent.py`) to minimal footprint with helper delegation and re-exports.
- [x] Task 2.B: Modularize Quality Gate Agent (`.github/scripts/quality_gate_agent.py`) to minimal footprint with helper delegation and re-exports.

### Group 3 (Sequential Execution - Full Workspace Verification, Depends on Group 2)
- [x] Task 3.A: Execute full test suite regression across unit and acceptance tests.

---

## 📝 Step-by-Step Implementation Details

#### Task 1.A: Helper Module (`.github/scripts/helper.py`) & Unit Test Suite (`.github/scripts/tests/test_helper.py`)
1.  **Step 1 (The Unit Test Harness):** Author comprehensive unit tests in `.github/scripts/tests/test_helper.py` testing:
    *   `sanitize_and_validate_repo` / `_sanitize_and_validate_repo`: whitespace stripping, quotes removal, `.git` suffix removal, invalid format rejection.
    *   `fetch_pr_modified_lines`: empty token handling, diff patch parsing, network error handling.
    *   `fetch_pr_comments`: empty token handling, URL construction, authorization header, error fallback to `[]`.
    *   `is_duplicate_comment` / `_is_duplicate_comment`: matching by file, line/original_line, title/severity, whitespace & casing tolerance.
    *   `validate_and_sanitize_findings`: splitting findings into valid inline diff hunk findings vs out-of-hunk general findings.
    *   `send_github_review_sync` & `send_github_issue_comment_sync`: HTTP payload serialization, Bearer auth, HTTP 200/422 status handling.
    *   `post_github_pr_review`: deduplication skipping, positive approval posting, HTTP 422 fallback to issue comment.
    *   `format_pr_review_text` & `format_text_decision`: deterministic text formatting for review and gate decisions.
    *   `write_json_and_text_reports`, `write_pr_reports`, `write_gate_reports`: report persistence in `reports/`.
    *   `resolve_env_config`: priority resolution between CLI arguments, environment variables, and default values.
    *   `create_github_mcp_server`: `types.McpStdioServer` configuration with Docker params.
    *   `parse_agent_structured_output`: model coercion from BaseModel, dict, and JSON string.
    *   *Target File:* `.github/scripts/tests/test_helper.py`
2.  **Step 2 (The Implementation):** Create `.github/scripts/helper.py` implementing all shared functions with both modern and backward-compatible alias names:
    *   *Target File:* `.github/scripts/helper.py`
    *   *Functions to implement:*
        - `sanitize_and_validate_repo(repo: str) -> Optional[tuple[str, str]]` & `_sanitize_and_validate_repo`
        - `fetch_pr_modified_lines(owner: str, repo_name: str, pr_number: Union[str, int], token: str, timeout: int = 10) -> dict[str, list[int]]`
        - `fetch_pr_comments(owner: str, repo_name: str, pr_number: Union[str, int], token: str, timeout: int = 10) -> list[dict[str, Any]]`
        - `is_duplicate_comment(finding: Any, existing_comments: list[dict[str, Any]]) -> bool` & `_is_duplicate_comment`
        - `validate_and_sanitize_findings(findings: list[Any], modified_files_diff: dict[str, list[int]]) -> tuple[list[Any], list[Any]]`
        - `send_github_review_sync(owner: str, repo_name: str, pr_number: Union[str, int], token: str, payload: dict[str, Any], timeout: int = 10) -> tuple[int, str]` & `_send_github_review_sync`
        - `send_github_issue_comment_sync(owner: str, repo_name: str, pr_number: Union[str, int], token: str, body: str, timeout: int = 10) -> tuple[int, str]` & `_send_github_issue_comment_sync`
        - `post_github_pr_review(report: Any, pr_number: Union[str, int], repo: str, token: str, modified_files_diff: Optional[dict[str, list[int]]] = None, existing_comments: Optional[list[dict[str, Any]]] = None) -> bool`
        - `format_pr_review_text(report: Any) -> str`
        - `format_text_decision(decision: Any) -> str`
        - `write_json_and_text_reports(json_path: str, json_data: Any, text_path: str, text_content: str) -> None`
        - `write_pr_reports(report: Any) -> None` & `_write_pr_reports`
        - `write_gate_reports(decision: Any) -> None` & `_write_reports`
        - `resolve_env_config(pr_number: Optional[str] = None, repo: Optional[str] = None, token: Optional[str] = None, project_id: Optional[str] = None, location: str = "us-central1", model: Optional[str] = None) -> dict[str, Any]`
        - `create_github_mcp_server(token: str, repo: str) -> types.McpStdioServer`
        - `stream_agent_response(response: Any, header_title: str = "AGENT EXECUTION & THINKING STREAM") -> tuple[list[str], list[str], list[str], list[str]]`
        - `parse_agent_structured_output(raw_output: Any, schema_cls: type[T]) -> T`
        - `read_text_file(path: str, default: str = "") -> str`
        - `ensure_directory(path: str) -> str`
3.  **Step 3 (The Verification):** Run `pytest .github/scripts/tests/test_helper.py -v` and ensure all test cases pass cleanly.

---

#### Task 2.A: Modularize PR Reviewer Agent (`.github/scripts/pr_reviewer_agent.py`)
1.  **Step 1 (The Unit Test Harness):** Verify existing test coverage in `.github/scripts/tests/test_pr_reviewer_agent.py` and `.github/tests/test_pr_reviewer_acceptance.py`.
    *   *Target Files:* `.github/scripts/tests/test_pr_reviewer_agent.py`, `.github/tests/test_pr_reviewer_acceptance.py`
2.  **Step 2 (The Implementation):** Refactor `.github/scripts/pr_reviewer_agent.py`:
    *   Import reusable utilities from `helper.py`.
    *   Retain schema definitions: `PRFindingSeverity`, `ReviewSeverity`, `ReviewStatus`, `POSITIVE_APPROVAL_TEMPLATE`, `InlineFinding`, `PRReviewReport`.
    *   Retain prompt definitions: `PR_REVIEWER_SYSTEM_INSTRUCTIONS`, prompt string construction.
    *   Refactor `run_pr_review()` to use helper functions (`resolve_env_config`, `fetch_pr_modified_lines`, `fetch_pr_comments`, `create_github_mcp_server`, `stream_agent_response`, `parse_agent_structured_output`, `write_pr_reports`, `post_github_pr_review`).
    *   Re-export all legacy helper symbols: `_sanitize_and_validate_repo`, `fetch_pr_modified_lines`, `fetch_pr_comments`, `_is_duplicate_comment`, `validate_and_sanitize_findings`, `format_pr_review_text`, `_send_github_review_sync`, `_send_github_issue_comment_sync`, `post_github_pr_review`, `_write_pr_reports`.
    *   *Target File:* `.github/scripts/pr_reviewer_agent.py`
3.  **Step 3 (The Verification):** Run `pytest .github/scripts/tests/test_pr_reviewer_agent.py .github/tests/test_pr_reviewer_acceptance.py -v` and ensure all test cases pass.

---

#### Task 2.B: Modularize Quality Gate Agent (`.github/scripts/quality_gate_agent.py`)
1.  **Step 1 (The Unit Test Harness):** Verify existing test coverage in `.github/scripts/tests/test_quality_gate_agent.py` and `.github/tests/test_quality_gate_acceptance.py`.
    *   *Target Files:* `.github/scripts/tests/test_quality_gate_agent.py`, `.github/tests/test_quality_gate_acceptance.py`
2.  **Step 2 (The Implementation):** Refactor `.github/scripts/quality_gate_agent.py`:
    *   Import reusable utilities from `helper.py`.
    *   Retain schema definitions: `SeverityLevel`, `ViolationCategory`, `FailureDetail`, `QualityGateDecision`.
    *   Retain prompt definitions: `QUALITY_GATE_SYSTEM_INSTRUCTIONS`, prompt construction.
    *   Refactor `evaluate_quality_gate()` to use helper functions (`resolve_env_config`, `read_text_file`, `parse_agent_structured_output`, `write_gate_reports`), while maintaining deterministic fail-closed validations.
    *   Re-export legacy symbols: `format_text_decision`, `_write_reports`.
    *   *Target File:* `.github/scripts/quality_gate_agent.py`
3.  **Step 3 (The Verification):** Run `pytest .github/scripts/tests/test_quality_gate_agent.py .github/tests/test_quality_gate_acceptance.py -v` and ensure all test cases pass.

---

#### Task 3.A: Full Workspace Regression Verification
1.  **Step 1 (The Verification):** Run all test suites across the workspace:
    *   `pytest .github/scripts/tests/ -v`
    *   `pytest .github/tests/ -v`
    *   `pytest scorer/tests/ -v`
2.  **Step 2 (Assertions):** Assert 0 failures, 0 errors across all test suites.

---

## 🧪 Global Testing Strategy
*   **Unit Tests (`.github/scripts/tests/test_helper.py`):** Test all pure functions and mocked HTTP integrations in `helper.py` in isolation.
*   **Agent Unit Tests (`.github/scripts/tests/test_pr_reviewer_agent.py`, `.github/scripts/tests/test_quality_gate_agent.py`):** Test agent configurations, fail-closed handling, model selection, prompt assembly, and response parsing.
*   **Acceptance Tests (`.github/tests/test_pr_reviewer_acceptance.py`, `.github/tests/test_quality_gate_acceptance.py`, `.github/tests/test_workflow_acceptance.py`):** End-to-end simulation of PR review cycles, duplicate comment skipping, quality gate enforcement, and GitHub Actions workflow configuration.

---

## 🎯 Success Criteria
*   `.github/scripts/helper.py` is implemented and exports all shared GitHub REST, report writing, formatting, environment resolution, and agent utilities.
*   `.github/scripts/pr_reviewer_agent.py` and `.github/scripts/quality_gate_agent.py` are streamlined to minimal files containing only schemas, prompts, and Gemini Agent calls.
*   `.github/scripts/tests/test_helper.py` is implemented with comprehensive isolated unit tests.
*   100% of tests pass across `pytest .github/scripts/tests/` and `pytest .github/tests/`.
