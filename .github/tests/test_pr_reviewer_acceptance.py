"""Acceptance and Contract Tests for PR Reviewer Agent.

Cites Decisions from docs/spec.md (D-4, D-5, D-6, D-11, D-12).
"""

import os
import pytest
from pydantic import ValidationError
try:
    from .github.scripts.pr_reviewer_agent import (
        PRFindingSeverity,
        ReviewSeverity,
        ReviewStatus,
        InlineFinding,
        PRReviewReport,
        validate_and_sanitize_findings,
        format_pr_review_text,
        run_pr_review,
    )
except (ImportError, ModuleNotFoundError):
    import importlib.util
    import sys
    _spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "pr_reviewer_agent.py"))
    _spec = importlib.util.spec_from_file_location("pr_reviewer_agent", _spec_path)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["pr_reviewer_agent"] = _mod
    _spec.loader.exec_module(_mod)
    PRFindingSeverity = _mod.PRFindingSeverity
    ReviewSeverity = _mod.ReviewSeverity
    ReviewStatus = _mod.ReviewStatus
    InlineFinding = _mod.InlineFinding
    PRReviewReport = _mod.PRReviewReport
    validate_and_sanitize_findings = _mod.validate_and_sanitize_findings
    format_pr_review_text = _mod.format_pr_review_text
    run_pr_review = _mod.run_pr_review


def test_pr_finding_severity_alias_compatibility():
    """Validates that ReviewSeverity is an alias of PRFindingSeverity."""
    assert ReviewSeverity is PRFindingSeverity  # D-4
    assert PRFindingSeverity.BLOCKER.value == "BLOCKER"  # D-4
    assert PRFindingSeverity.WARNING.value == "WARNING"  # D-4
    assert PRFindingSeverity.SUGGESTION.value == "SUGGESTION"  # D-4
    assert PRFindingSeverity.INFO.value == "INFO"  # D-4


def test_pr_review_report_schema_approve():
    """Validates PRReviewReport with APPROVE status."""
    report = PRReviewReport(
        overall_status=ReviewStatus.APPROVE,  # D-4
        summary="Code looks clean, well-tested, and adheres to standards.",  # D-4
        findings=[],  # D-4
    )
    assert report.overall_status == ReviewStatus.APPROVE  # D-4
    assert len(report.findings) == 0  # D-4


def test_pr_review_report_schema_request_changes():
    """Validates PRReviewReport with REQUEST_CHANGES status and structured findings."""
    finding = InlineFinding(
        file_path="scorer/usage.py",  # D-4
        line_number=42,  # D-4
        severity=PRFindingSeverity.BLOCKER,  # D-4
        title="Uncaught ZeroDivisionError",  # D-4
        details="Division by zero occurs when active_months is 0.",  # D-4
        suggestion="Add guard condition: if active_months == 0: return 0.0",  # D-4
        pii_leak=False,  # D-4
    )
    report = PRReviewReport(
        overall_status=ReviewStatus.REQUEST_CHANGES,  # D-4
        summary="Blocking errors detected requiring remediation.",  # D-4
        findings=[finding],  # D-4
    )
    assert report.overall_status == ReviewStatus.REQUEST_CHANGES  # D-4
    assert len(report.findings) == 1  # D-4
    assert report.findings[0].severity == PRFindingSeverity.BLOCKER  # D-4


def test_validate_and_sanitize_findings_separates_inline_and_general():
    """Separates findings with valid diff line coordinates from invalid/out-of-hunk ones."""
    # Modified files diff mockup: scorer/usage.py has modified lines [10, 11, 12, 40, 41, 42]
    diff_hunks = {
        "scorer/usage.py": [10, 11, 12, 40, 41, 42],  # D-12
        "scripts/ci/agent.py": [1, 2, 3],  # D-12
    }

    valid_inline = InlineFinding(
        file_path="scorer/usage.py",  # D-12
        line_number=42,  # D-12: Line exists in diff hunks
        severity=PRFindingSeverity.WARNING,
        title="Type annotation warning",
        details="Missing return type annotation.",
        suggestion="def score() -> int:",
    )

    out_of_hunk_line = InlineFinding(
        file_path="scorer/usage.py",  # D-12
        line_number=999,  # D-12: Line does NOT exist in diff hunks
        severity=PRFindingSeverity.INFO,
        title="General observation",
        details="Consider refactoring helper function.",
        suggestion="",
    )

    unmodified_file = InlineFinding(
        file_path="README.md",  # D-12: File not in diff
        line_number=5,
        severity=PRFindingSeverity.SUGGESTION,
        title="Typo in documentation",
        details="Typo on line 5.",
        suggestion="",
    )

    none_line_finding = InlineFinding(
        file_path="scorer/usage.py",  # D-12
        line_number=None,  # D-12: No specific line
        severity=PRFindingSeverity.SUGGESTION,
        title="File-level architecture suggestion",
        details="Split module into two files.",
        suggestion="",
    )

    inline_findings, general_findings = validate_and_sanitize_findings(
        findings=[valid_inline, out_of_hunk_line, unmodified_file, none_line_finding],
        modified_files_diff=diff_hunks,
    )

    assert len(inline_findings) == 1  # D-12: Only valid_inline meets coordinates
    assert inline_findings[0].title == "Type annotation warning"  # D-12
    assert len(general_findings) == 3  # D-12: Fallback to top-level review comment body
    assert any(f.title == "General observation" for f in general_findings)  # D-12
    assert any(f.title == "Typo in documentation" for f in general_findings)  # D-12
    assert any(f.title == "File-level architecture suggestion" for f in general_findings)  # D-12


def test_format_pr_review_text():
    """Validates formatted markdown representation of PRReviewReport."""
    finding = InlineFinding(
        file_path="auth.py",  # D-6
        line_number=18,  # D-6
        severity=PRFindingSeverity.BLOCKER,  # D-6
        title="Exposed API secret key",  # D-6
        details="Hardcoded credential found.",  # D-6
        suggestion="os.environ['API_KEY']",  # D-6
        pii_leak=True,  # D-4, D-6
    )
    report = PRReviewReport(
        overall_status=ReviewStatus.REQUEST_CHANGES,  # D-4, D-6
        summary="Security blocker detected in auth.py.",  # D-6
        findings=[finding],  # D-6
    )
    text = format_pr_review_text(report)  # D-6
    assert "### Status: REQUEST_CHANGES" in text  # D-6
    assert "Security blocker detected in auth.py." in text  # D-6
    assert "[BLOCKER] auth.py:18 - Exposed API secret key" in text  # D-6
    assert "Suggestion: os.environ['API_KEY']" in text  # D-6


@pytest.mark.asyncio
async def test_run_pr_review_non_pr_event_early_exit():
    """When pr_number is None or empty, run_pr_review skips execution and returns None with exit 0."""
    result = await run_pr_review(
        pr_number=None,  # D-5: Non-PR / Push event
        repo="owner/repo",
        token="mock-token",
    )
    assert result is None  # D-5: Early exit without calling LLM or Docker
