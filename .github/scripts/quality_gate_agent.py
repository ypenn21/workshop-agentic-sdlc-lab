"""Quality Gate Decision Agent using Antigravity Python SDK with Vertex AI ADC and Pydantic.

Evaluates security scans (Cloud DLP) and automated PR reviews to determine whether
a build meets production release criteria.
"""

import os
import sys
import json
import asyncio
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Any

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


def format_text_decision(decision: QualityGateDecision) -> str:
    """Converts QualityGateDecision into deterministic formatted text."""
    lines: list[str] = []
    if decision.passed:
        lines.append("GATE_PASSED\n")
        lines.append(f"Summary: {decision.summary}")
    else:
        lines.append("GATE_FAILED\n")
        lines.append(f"Summary: {decision.summary}\n")
        lines.append("Violations:")
        for idx, failure in enumerate(decision.failures, 1):
            lines.append(
                f"{idx}. [{failure.severity.value}] {failure.category.value} in {failure.component}"
            )
            lines.append(f"   Reason: {failure.reason}")
            lines.append(f"   Remediation: {failure.remediation}")
    return "\n".join(lines)


async def evaluate_quality_gate(
    pii_report_path: str = "reports/pii-scan.txt",
    pr_review_path: str = "reports/pr-review.txt",
    project_id: Optional[str] = None,
    location: str = "us-central1",
    pr_number: Optional[str] = None,
) -> QualityGateDecision:
    """Evaluates combined scan and review reports against release criteria.

    Enforces fail-closed evaluation on missing DLP scans and outputs both
    reports/gate-decision.json and reports/decision.txt.
    """
    project_id = (
        project_id
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or "local-project"
    )
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", location)
    if pr_number is None:
        pr_number = os.environ.get("PULL_REQUEST_NUMBER") or os.environ.get("PR_NUMBER")

    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/telemetry/quality_gate_agent", exist_ok=True)

    # 1. Fail-Closed Check on Cloud DLP Scan Report (Decision D-7)
    if not os.path.exists(pii_report_path) or os.path.getsize(pii_report_path) == 0:
        decision = QualityGateDecision(
            passed=False,
            summary="Quality gate failed: Required Cloud DLP scan report (reports/pii-scan.txt) is missing, unreadable, or empty.",
            failures=[
                FailureDetail(
                    category=ViolationCategory.SECURITY_VULNERABILITY,
                    component="Cloud DLP",
                    severity=SeverityLevel.CRITICAL,
                    reason="Required Cloud DLP scan report (reports/pii-scan.txt) is missing, unreadable, or empty",
                    remediation="Ensure Cloud DLP scan step executes successfully before quality gate evaluation",
                )
            ],
        )
        _write_reports(decision)
        return decision

    pii_content = Path(pii_report_path).read_text(encoding="utf-8")

    # 2. Check PR Review Report (Decision D-7)
    if not os.path.exists(pr_review_path):
        if not pr_number:
            # Push / non-PR event: pr-review is optional
            pr_review_content = "No PR review report available (push event or non-PR)."
        else:
            # Active PR event: missing review is a failure
            decision = QualityGateDecision(
                passed=False,
                summary="Quality gate failed: PR review report is missing on an active pull request.",
                failures=[
                    FailureDetail(
                        category=ViolationCategory.SECURITY_VULNERABILITY,
                        component="PR Reviewer",
                        severity=SeverityLevel.HIGH,
                        reason="PR review report (reports/pr-review.txt) was not generated for pull request.",
                        remediation="Ensure PR Reviewer Agent runs before Quality Gate on pull requests.",
                    )
                ],
            )
            _write_reports(decision)
            return decision
    else:
        pr_review_content = Path(pr_review_path).read_text(encoding="utf-8")

    # 3. Analyze contents for violations
    # Check for PII / Credential leaks or blocker findings
    pii_has_violations = (
        "PII finding" in pii_content
        or "AUTH_TOKEN" in pii_content
        or "API_KEY" in pii_content
        or "SECRET" in pii_content.upper()
        or "EMAIL_ADDRESS" in pii_content
        or "Violations detected" in pii_content
        or ("0 findings" not in pii_content and "No sensitive data" not in pii_content and "clean" not in pii_content.lower())
    )

    pr_has_blockers = (
        "REQUEST_CHANGES" in pr_review_content
        or "[BLOCKER]" in pr_review_content
    )

    failures: list[FailureDetail] = []

    if pii_has_violations and "No sensitive data" not in pii_content:
        failures.append(
            FailureDetail(
                category=ViolationCategory.PII_LEAK,
                component="Cloud DLP Scan",
                severity=SeverityLevel.CRITICAL,
                reason="Sensitive data or credential findings detected in repository files.",
                remediation="Remove sensitive data, rotate exposed secrets, and store credentials in Secret Manager.",
            )
        )

    if pr_has_blockers:
        failures.append(
            FailureDetail(
                category=ViolationCategory.ARCHITECTURAL_DEFECT,
                component="PR Code Review",
                severity=SeverityLevel.CRITICAL,
                reason="Automated PR code review requested changes with blocking findings.",
                remediation="Address line-level PR code review comments before merge.",
            )
        )

    # Attempt to invoke Antigravity SDK if available and live credentials exist
    try:
        from google import antigravity  # type: ignore
        from google.antigravity import LocalAgentConfig  # type: ignore

        prompt = f"""You are the Quality Gate Decision Agent.
Evaluate the following security scans and PR code review outputs:

=== CLOUD DLP SCAN REPORT ===
{pii_content}

=== PR CODE REVIEW REPORT ===
{pr_review_content}

Evaluate if the build passes or fails release criteria.
Fail the gate if any sensitive data, credentials, or blocker review items exist.
Return a structured QualityGateDecision response.
"""
        config = LocalAgentConfig(
            vertex=True,
            project=project_id,
            location=location,
            model="gemini-2.5-flash",
            response_schema=QualityGateDecision,
            app_data_dir="reports/telemetry/quality_gate_agent",
        )
        agent = antigravity.Agent(config=config)
        response = await agent.chat(prompt)
        raw_output = await response.structured_output()
        if raw_output:
            decision = QualityGateDecision.model_validate(raw_output)
            _write_reports(decision)
            return decision
    except Exception:
        # Fallback to deterministic static evaluation
        pass

    if failures:
        decision = QualityGateDecision(
            passed=False,
            summary=f"Quality gate failed with {len(failures)} blocking violation(s).",
            failures=failures,
        )
    else:
        decision = QualityGateDecision(
            passed=True,
            summary="All quality and security checks passed cleanly.",
            failures=[],
        )

    _write_reports(decision)
    return decision


def _write_reports(decision: QualityGateDecision) -> None:
    """Writes JSON and text decision artifacts to reports directory."""
    os.makedirs("reports", exist_ok=True)
    with open("reports/gate-decision.json", "w", encoding="utf-8") as f:
        f.write(decision.model_dump_json(indent=2))
    with open("reports/decision.txt", "w", encoding="utf-8") as f:
        f.write(format_text_decision(decision))


async def main() -> None:
    """CLI entry point for Quality Gate Agent."""
    pii_report = sys.argv[1] if len(sys.argv) > 1 else "reports/pii-scan.txt"
    pr_review = sys.argv[2] if len(sys.argv) > 2 else "reports/pr-review.txt"
    pr_num = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("PULL_REQUEST_NUMBER")

    decision = await evaluate_quality_gate(
        pii_report_path=pii_report,
        pr_review_path=pr_review,
        pr_number=pr_num,
    )

    print(f"Quality Gate Status: {'PASSED' if decision.passed else 'FAILED'}")
    print(f"Summary: {decision.summary}")
    # Always exit 0 so workflow can upload telemetry (Decision D-9)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
