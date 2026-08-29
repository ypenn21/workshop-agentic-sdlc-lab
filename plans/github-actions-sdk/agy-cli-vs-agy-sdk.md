# When to Use `agy` CLI vs Python SDK

Here's the comprehensive decision framework comparing the standalone `agy` CLI against the **Google Antigravity Python SDK** (`google-antigravity`):

| Capability / Scenario | Standalone CLI (`agy`) | Python SDK (`google-antigravity`) | Critical Impact |
| :--- | :--- | :--- | :--- |
| **Output Type Safety** | Freeform streamed text / raw logs. Requires bash regex / grep matching. | Native **Pydantic models** (`response_schema`). Deterministic JSON validation. | **Critical**: Eliminates parsing ambiguity, schema drift, and false positives/negatives in CI gates. |
| **GCP Authentication** | Environment variables / API keys / CLI config files. | First-class **Vertex AI ADC (Standard Mode)** via Workload Identity Federation. | **Critical**: Zero API key management; keyless authentication directly against IAM. |
| **Programmatic Control Flow** | Static execution; cannot branch or retry dynamically based on output. | Native Python async control flow (`if/else`, loops, try/except). | **High**: Enables dynamic CI decisions, automated PR status updates, and fallback handling. |
| **PR & Code Review Integration** | Text piped to STDOUT or CLI output files. | Structured line-by-line comments posted via GitHub API or MCP. | **High**: Actionable inline PR comments targeting exact files and line numbers. |
| **Custom Tool Composition** | Fixed JSON configuration (`.agents/mcp_config.json`). | Native Python functions + MCP stdio/HTTP servers. | **Medium**: Easily integrate internal Python libraries and DB clients. |
| **Agent Lifecycle & Hooks** | Not supported in CLI one-shot prompts. | Intercept turn, tool, and error events via policy hooks. | **Medium**: Enforce safety rules and security policies at runtime. |
| **Telemetry & Observability** | Raw file dumps in `~/.gemini/antigravity-cli/`. | Direct programmatic routing via `app_data_dir`. | **Medium**: Clean archiving to Google Cloud Storage (GCS) buckets. |
| **One-Shot Terminal Tasks** | ✅ Fast, immediate execution in interactive shells. | ⚠️ Requires boilerplate Python script. | **Low**: CLI is ideal for quick prototyping and ad-hoc exploratory queries. |

---

## Workflow Recommendations & Code Comparison

### Step 1: PR Auto-Review

#### CLI Approach (Current)
```yaml
- name: 'Run PR Auto-Review via Antigravity Code Reviewer'
  run: |
    agy -p "Perform an automated code review on PR #${{ github.event.pull_request.number }}..." \
      --dangerously-skip-permissions \
      --output-format text | tee reports/pr-review.txt
```
*Downside:* Text output must be scraped or posted as a single unstructured comment; no machine-readable triage.

#### SDK + Pydantic Approach (Recommended)
```python
import os
import asyncio
from enum import Enum
from pydantic import BaseModel, Field
from google.antigravity import Agent, LocalAgentConfig


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    INFO = "INFO"


class PRFinding(BaseModel):
    file_path: str = Field(description="Path to the modified file")
    line_number: int | None = Field(default=None, description="Line number where issue occurs")
    severity: Severity = Field(description="Severity classification")
    title: str = Field(description="Brief issue summary")
    comment: str = Field(description="Actionable remediation advice")
    pii_detected: bool = Field(default=False, description="Whether PII was leaked here")


class PRReviewReport(BaseModel):
    overall_status: str = Field(description="'APPROVE' or 'REQUEST_CHANGES'")
    summary: str = Field(description="High level summary of the review")
    findings: list[PRFinding] = Field(default_factory=list)


async def main():
    config = LocalAgentConfig(
        vertex=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        response_schema=PRReviewReport,
    )

    async with Agent(config) as agent:
        response = await agent.chat("Review PR diff and DLP scan report...")
        report_data = await response.structured_output()
        report = PRReviewReport.model_validate(report_data)

        # Strongly typed traversal & programmatic PR comment posting
        for finding in report.findings:
            if finding.pii_detected or finding.severity == Severity.BLOCKER:
                print(f"🚨 Blocked: {finding.file_path}:{finding.line_number} - {finding.title}")
```

---

### Step 2: Quality Gate Decision

#### CLI Approach (Current)
```yaml
- name: 'Quality Gate Decision via Release Engineer Agent'
  run: |
    agy -p "Evaluate reports. If criteria pass output GATE_PASSED, else GATE_FAILED..." \
      --output-format text | tee reports/decision.txt
- name: 'Enforce Gate'
  run: |
    if grep -q "GATE_FAILED" reports/decision.txt; then
      exit 1
    fi
```
*Downside:* Highly brittle. If the agent prepends a conversational filler or formats markdown differently, `grep` easily yields false positives or false negatives.

#### SDK + Pydantic Approach (Recommended)
```python
import os
import sys
import json
import asyncio
from pydantic import BaseModel, Field
from google.antigravity import Agent, LocalAgentConfig


class FailureDetail(BaseModel):
    category: str = Field(description="PII_LEAK, SECURITY_VULNERABILITY, or ARCHITECTURAL_BLOCKER")
    component: str = Field(description="Impacted file, service, or step")
    reason: str = Field(description="Specific reason for the quality gate failure")


class QualityGateDecision(BaseModel):
    passed: bool = Field(description="Strict boolean: True only if ALL security & quality criteria pass")
    summary: str = Field(description="Evaluation summary")
    failures: list[FailureDetail] = Field(default_factory=list)


async def main():
    config = LocalAgentConfig(
        vertex=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        response_schema=QualityGateDecision,
    )

    async with Agent(config) as agent:
        response = await agent.chat("Evaluate DLP and code review reports against release criteria.")
        raw_output = await response.structured_output()
        decision = QualityGateDecision.model_validate(raw_output)

    # Deterministic JSON export
    with open("reports/gate-decision.json", "w") as f:
        f.write(decision.model_dump_json(indent=2))

    if not decision.passed:
        print("❌ Quality Gate Failed:")
        for failure in decision.failures:
            print(f"  - [{failure.category}] {failure.component}: {failure.reason}")
        sys.exit(1)

    print("✅ Quality Gate Passed!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Summary & Migration Verdict

1. **Use `agy` CLI for**:
   - Interactive terminal debugging, quick exploratory prompts, and local human-in-the-loop pair programming.
2. **Use Antigravity Python SDK for**:
   - CI/CD pipelines (GitHub Actions, Cloud Build).
   - Keyless GCP Vertex AI authentication via Application Default Credentials (ADC).
   - Type-safe Pydantic contracts and automated enforcement gates.
   - Programmatic PR review workflows and webhook event handlers.