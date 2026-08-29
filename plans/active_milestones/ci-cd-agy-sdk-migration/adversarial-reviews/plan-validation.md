# Plan Adversarial Review — CI/CD Antigravity Python SDK Migration

> `plan-validator` · 3 independent skeptics, no shared scratchpad · default-to-reject · skeptics READ the codebase · 2-of-3 majority gate

| Field | Value |
|---|---|
| Milestone | `ci-cd-agy-sdk-migration` |
| Artifact | `plans/active_milestones/ci-cd-agy-sdk-migration/plan.md` |
| Date | 2026-08-28 |
| Gate | 2-of-3 majority gate |
| Result | **6 confirmed · 2 unconfirmed** — highest severity **🔴 high** |
| 🁢 First domino | `missing-dependencies-in-pyproject-toml` — Task 1.A Step 3 / Task 1.B Step 3 cannot run `uv run pytest` due to missing `google-antigravity` and `pydantic` in `pyproject.toml` |

## Verdict
The plan has sound architectural foundations (keyless WIF authentication, Pydantic invariant modeling, and clean separation between agent execution and CI gate halting), but it will **fail on step 1 of execution**. The first domino topples immediately because `pyproject.toml` lacks the required dependencies (`google-antigravity`, `pydantic`, `pytest-asyncio`) and restricts `pythonpath` strictly to `scorer`, preventing local test harness execution and imports. Furthermore, Task 1.B Step 2 omits the comment mutation execution logic. Applying the confirmed fixes to `pyproject.toml` and Task 1.B Step 2 will make the plan fully executable.

## Confirmed Findings (≥ 2 votes)

### 🔴 `missing-dependencies-in-pyproject-toml` — Missing project dependencies in `pyproject.toml` · ordering / false-assumption · 3/3 votes · confidence high
- **Step:** Task 1.A Step 3, Task 1.B Step 3, Task 2.A Step 2, and Global Testing Strategy
- **Failure:** Executing test verification via `uv run pytest .github/scripts/tests/...` fails immediately with `ModuleNotFoundError` because `google-antigravity`, `pydantic>=2.0.0,<3.0.0`, and `pytest-asyncio` are not declared in `pyproject.toml` or locked in `uv.lock`. The plan defers package installation to CI via `pip install` in Task 2.A, breaking local development and test-first harness verification.
- **Evidence:** `pyproject.toml:6-9` (`dependencies = []`, `dev = ["pytest>=8"]`); `plan.md:15-19,155,234,250`
- **Fix:** Add `pyproject.toml` to Affected Files, declare `google-antigravity`, `pydantic>=2.0.0,<3.0.0`, and `pytest-asyncio` in `pyproject.toml` (under `[dependency-groups] dev` or a dedicated dependency group), and execute `uv sync` prior to Group 1 execution.

### 🔴 `pytest-pythonpath-missing-workspace-root` — Pytest pythonpath and testpaths exclusion · false-assumption · 3/3 votes · confidence high
- **Step:** Task 1.A Step 1 & 3, Task 1.B Step 1 & 3, Task 2.A Step 2, and Global Testing Strategy
- **Failure:** In `pyproject.toml`, pytest options are configured as `pythonpath = ["scorer"]` and `testpaths = ["scorer/tests"]`. The repository root `.` and `.github/scripts` are not on `sys.path`, causing imports like `from .github.scripts.quality_gate_agent import ...` to fail with `ModuleNotFoundError`. Additionally, bare `pytest` runs ignore `.github/scripts/tests/`.
- **Evidence:** `pyproject.toml:11-14` (`pythonpath = ["scorer"]`, `testpaths = ["scorer/tests"]`); `plan.md:290-292`
- **Fix:** Update `pyproject.toml` pytest settings to `pythonpath = [".", "scorer"]` and expand `testpaths = ["scorer/tests", ".github/scripts/tests"]`.

### 🔴 `pr-reviewer-missing-comment-mutation-execution` — Missing PR review comment mutation execution logic · false-assumption · 3/3 votes · confidence high
- **Step:** Task 1.B: PR Reviewer Agent — Step 2 (The Implementation)
- **Failure:** Task 1.B Step 1 references tests for helper `validate_and_sanitize_findings()` (Decision D-12) and spec Scenario 5/7 mandates posting inline and top-level review comments to the PR. However, Task 1.B Step 2 implementation sub-steps 1–7 terminate after writing local report files (`reports/pr-review.json` and `reports/pr-review.txt`) and return 0, completely omitting the invocation of `validate_and_sanitize_findings()` and GitHub MCP / REST comment submission calls.
- **Evidence:** `plan.md:170-171` vs `plan.md:213-231`; `spec.md:117,139-140`
- **Fix:** Explicitly define the post-processing and comment mutation flow in Task 1.B Step 2: pass generated findings through `validate_and_sanitize_findings()` to separate inline findings from top-level summary comments, and dispatch the comments via GitHub MCP tools or GitHub API before exiting.

### 🟠 `enum-naming-discrepancy-pr-finding-severity` — Discrepancy in finding severity enum name · false-assumption · 3/3 votes · confidence high
- **Step:** Task 1.B: PR Reviewer Agent — Step 1 & Step 2
- **Failure:** Task 1.B Step 2 defines `class ReviewSeverity(str, Enum):` whereas `spec.md:133` and Decision `D-4` explicitly define `PRFindingSeverity(str, Enum)`. Contract tests importing or referencing `PRFindingSeverity` against `.github/scripts/pr_reviewer_agent.py` will fail with `ImportError`.
- **Evidence:** `spec.md:133` (`PRFindingSeverity(str, Enum)`); `plan.md:163,183,303`
- **Fix:** Standardize the enum name to `PRFindingSeverity` (or provide `ReviewSeverity = PRFindingSeverity` as an alias) in `.github/scripts/pr_reviewer_agent.py`.

### 🟠 `workflow-step-env-repository-mismatch` — Inconsistent environment variable naming for repository · hidden-coupling · 2/3 votes · confidence medium
- **Step:** Task 2.A: Step 1 (The Workflow Transformation) & Task 1.B Step 2
- **Failure:** Task 2.A Step 1 passes `REPOSITORY: ${{ github.repository }}` while Task 1.B Step 2 and spec Scenario 5 inspect `GITHUB_REPOSITORY` to configure `types.McpStdioServer`. If `GITHUB_REPOSITORY` is unset, the GitHub MCP container receives an empty repository string.
- **Evidence:** `plan.md:220` (`repo = os.environ.get("GITHUB_REPOSITORY", "")`); `plan.md:254` (`env: pass GH_TOKEN, REPOSITORY...`); `.github/workflows/source-code-pii-review.yml:180`
- **Fix:** Update Task 2.A Step 1 to pass `GITHUB_REPOSITORY: ${{ github.repository }}`, and configure `.github/scripts/pr_reviewer_agent.py` to check both `GITHUB_REPOSITORY` and `REPOSITORY`.

### 🟡 `missing-package-init-creation-step` — Missing package `__init__.py` markers · ordering · 2/3 votes · confidence medium
- **Step:** Group 1 Parallel Execution & Affected Files
- **Failure:** `.github/__init__.py` and `.github/scripts/__init__.py` are not created, which can cause package import and test discovery inconsistencies across different Python environments during parallel execution of Task 1.A and Task 1.B.
- **Evidence:** `plan.md:10` (lists only `.github/scripts/tests/__init__.py`); `.github/` directory currently contains no `__init__.py`
- **Fix:** Add `.github/__init__.py` and `.github/scripts/__init__.py` to Affected Files and ensure they are initialized before executing Group 1 tasks.

## Unconfirmed (FYI · 1 vote)
| `id` | severity | step | note |
|---|---|---|---|
| `missing-dlp-fail-closed-nondeterminism` | 🟠 medium | Task 1.A Step 2 | Task 1.A Step 2 suggests injecting fallback prompt context instead of a deterministic local short-circuit when `reports/pii-scan.txt` is missing. |
| `vertex-model-location-mismatch` | 🔴 high | Task 1.A Step 2 & Task 1.B Step 2 | AGENTS.md Rule 4 mandates `MODEL_LOCATION=global` for Gemini 3 models on Vertex AI; ensure model is explicitly pinned to `gemini-3.7-flash` (with medium thinking budget; minimum Gemini 3.5 Flash) per spec D-2 when location is `us-central1`. |

## Checks That Passed
- **WIF Keyless Authentication:** `google-github-actions/auth@v2` configuration is valid, completely eliminating static `GEMINI_API_KEY` dependencies (`.github/workflows/source-code-pii-review.yml:48-54`).
- **Pydantic Model Invariants:** `QualityGateDecision` invariant validator (`@model_validator(mode="after")`) correctly enforces `passed == (len(failures) == 0)` (`plan.md:132-138`).
- **LocalAgentConfig Specification:** Config options (`vertex=True`, `project`, `location`, `response_schema`, `mcp_servers`, `app_data_dir`) match Google Antigravity SDK contracts.
- **Non-PR Push Event Skip:** Early return with exit code 0 when `PULL_REQUEST_NUMBER` is unset properly avoids unnecessary LLM/Docker execution on push events (`plan.md:168,214`).
- **Decoupled CI Gate Enforcement:** Decoupling `quality_gate_agent.py` exit code (0 on report emission) from the workflow's `Enforce Quality Gate` step (1 on failure) ensures telemetry archival and step summary generation run unconditionally via `if: always()` (`plan.md:27,260-270`).
- **Core Scorer Isolation:** Pure Python core scoring service under `scorer/` remains untouched and free of cloud/CI dependencies (`scorer/usage.py:1-40`).

## Actions Taken
- [x] Add `pyproject.toml`, `.github/__init__.py`, and `.github/scripts/__init__.py` to Affected Files (`missing-dependencies-in-pyproject-toml`, `missing-package-init-creation-step`)
- [x] Add `google-antigravity`, `pydantic>=2.0.0,<3.0.0`, and `pytest-asyncio` to `pyproject.toml` dev dependency group and configure `pythonpath = [".", "scorer"]` and `testpaths = ["scorer/tests", ".github/scripts/tests"]` (`missing-dependencies-in-pyproject-toml`, `pytest-pythonpath-missing-workspace-root`)
- [x] Update Task 1.B Step 2 to detail the post-processing execution of `validate_and_sanitize_findings()` and dispatch of GitHub MCP PR review comments (`pr-reviewer-missing-comment-mutation-execution`)
- [x] Standardize enum name to `PRFindingSeverity` in Task 1.B Step 2 (`enum-naming-discrepancy-pr-finding-severity`)
- [x] Set `GITHUB_REPOSITORY: ${{ github.repository }}` in Task 2.A workflow step and read both in `pr_reviewer_agent.py` (`workflow-step-env-repository-mismatch`)
- [x] Explicitly pin `model="gemini-3.7-flash"` (medium thinking budget) in `LocalAgentConfig` and specify immediate local fail-closed short-circuit on missing DLP scan (`vertex-model-location-mismatch`, `missing-dlp-fail-closed-nondeterminism`)
