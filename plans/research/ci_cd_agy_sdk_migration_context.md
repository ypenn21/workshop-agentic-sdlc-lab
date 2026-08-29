# Strategic Research Context Report: CI/CD Antigravity Python SDK Migration

## 1. Request Overview & Objectives
The user requested the creation and implementation of the Antigravity Python SDK (`google-antigravity`) migration specified in `plans/github-actions-sdk/migration-agy-sdk.md`.

### Primary Objectives
1. **Migrate from `agy` CLI to `google-antigravity` Python SDK**:
   - Replace one-shot CLI commands (`agy -p ...`) in CI with typed, maintainable Python scripts.
2. **Type-Safe Pydantic Quality Gate (`.github/scripts/quality_gate_agent.py`)**:
   - Parse Cloud DLP scan findings (`reports/pii-scan.txt`) and PR review reports (`reports/pr-review.txt`).
   - Use `LocalAgentConfig(vertex=True, project=..., location=..., model="gemini-3.7-flash", response_schema=QualityGateDecision)` (configured with medium thinking budget; minimum Gemini 3.5 Flash).
   - Output deterministic typed JSON (`reports/gate-decision.json`) and formatted summary (`reports/decision.txt`).
3. **Automated PR Reviewer Agent (`.github/scripts/pr_reviewer_agent.py`)**:
   - Integrate GitHub MCP server via `types.McpStdioServer` running `ghcr.io/github/github-mcp-server:v0.27.0`.
   - Configure `LocalAgentConfig` with `model="gemini-3.7-flash"` (medium thinking budget).
   - Enforce Pydantic schema `PRReviewReport` (with `InlineFinding`, `ReviewSeverity`).
   - Save `reports/pr-review.json` and `reports/pr-review.txt`.
4. **Keyless Google Cloud ADC Authentication**:
   - Leverage Workload Identity Federation (WIF) via `google-github-actions/auth@v2`.
   - Configure SDK with `vertex=True` without hardcoded API keys.
5. **Modernized GitHub Actions Workflow (`.github/workflows/source-code-pii-review.yml`)**:
   - Use `actions/setup-python@v5` and standard Python dependencies.
   - Deterministic gate enforcement by evaluating `reports/gate-decision.json`.
   - Telemetry and report archiving to GCS.

---

## 2. Existing Codebase Analysis & Findings

### A. Current CI Workflow (`.github/workflows/source-code-pii-review.yml`)
- Currently downloads `agy` CLI via `curl -fsSL https://antigravity.google/cli/install.sh | bash`.
- Configures `~/.gemini/antigravity-cli/settings.json` and `.agents/mcp_config.json`.
- Runs `agy -p ...` and pipes text output to `reports/pr-review.txt` and `reports/decision.txt`.
- Evaluates gate using brittle grep: `grep -q "GATE_FAILED" reports/decision.txt`.

### B. Project Structure & Dependency Context
- Root `pyproject.toml` manages `account-health` with Python `>=3.11` and `pytest>=8`.
- Coder agent has its own `coder-agent/pyproject.toml` for Vertex AI Reasoning Engine / GEAP deployment.
- CI agent scripts belong in `.github/scripts/` (`quality_gate_agent.py` and `pr_reviewer_agent.py`).
- Dependencies needed in CI: `google-antigravity>=0.1.0` (or latest), `pydantic>=2.0`.

### C. SDK Reference Patterns
- `LocalAgentConfig`:
  - `vertex=True`, `project=...`, `location=...` for Vertex AI ADC.
  - `response_schema=QualityGateDecision` / `response_schema=PRReviewReport` for structured JSON output.
  - `mcp_servers=[types.McpStdioServer(...)]` for GitHub MCP.
  - `app_data_dir=os.path.abspath("reports/telemetry/...")` for telemetry isolation.
- `Agent(config)` context manager:
  - `response = await agent.chat(prompt)`
  - `data = await response.structured_output()`
  - `model = ModelClass.model_validate(data)`

---

## 3. Potential Constraints & Edge Cases
1. **Non-PR / Push Events**: `pr_reviewer_agent.py` must gracefully skip execution or handle push events where `PULL_REQUEST_NUMBER` is unset without failing the pipeline.
2. **Missing DLP Reports**: If `reports/pii-scan.txt` does not exist or is empty, scripts should supply default fallback text ("No DLP scan report available") and evaluate accordingly.
3. **GitHub MCP Server Execution**: GitHub MCP container requires `GITHUB_PERSONAL_ACCESS_TOKEN` / `GH_TOKEN`. If running in environments without docker or tokens, error handling should be clear.
4. **Backward Compatibility**: `reports/decision.txt` should continue to be emitted alongside `reports/gate-decision.json` for backward compatibility with existing log display steps and human-readable summaries.

---

## 4. Next Lifecycle Phase
- **Phase 1: Product Discovery (`product-owner`)**:
  - Ingest this Context Report.
  - Register milestone `ci-cd-agy-sdk-migration` in `plans/00-ROADMAP.md`.
  - Author formal Gherkin specification at `plans/active_milestones/ci-cd-agy-sdk-migration/spec.md`.
