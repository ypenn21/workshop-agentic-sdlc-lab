"""Acceptance and Contract Tests for PR Reviewer Agent.

Cites Decisions from docs/spec.md (D-2, D-4, D-5, D-6, D-10, D-11, D-12).
"""

import os
import sys
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

# Ensure .github/scripts is on sys.path for direct module import
_scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import pr_reviewer_agent
from pr_reviewer_agent import (
    PRFindingSeverity,
    ReviewSeverity,
    ReviewStatus,
    InlineFinding,
    PRReviewReport,
    validate_and_sanitize_findings,
    format_pr_review_text,
    run_pr_review,
)


def test_pr_finding_severity_alias_compatibility():
    """Validates that ReviewSeverity is an alias of PRFindingSeverity."""
    assert ReviewSeverity is PRFindingSeverity  # D-4
    assert PRFindingSeverity.BLOCKER.value == "BLOCKER"  # D-4
    assert PRFindingSeverity.WARNING.value == "WARNING"  # D-4
    assert PRFindingSeverity.SUGGESTION.value == "SUGGESTION"  # D-4
    assert PRFindingSeverity.INFO.value == "INFO"  # D-4


def test_review_status_enum_values():
    """Validates that ReviewStatus enum contains expected values."""
    assert ReviewStatus.APPROVE.value == "APPROVE"  # D-4
    assert ReviewStatus.REQUEST_CHANGES.value == "REQUEST_CHANGES"  # D-4
    assert ReviewStatus.COMMENT.value == "COMMENT"  # D-4


def test_inline_finding_schema_and_defaults():
    """Validates InlineFinding instantiation and default field values."""
    finding = InlineFinding(
        file_path="scorer/usage.py",  # D-4
        line_number=15,  # D-4
        severity=PRFindingSeverity.WARNING,  # D-4
        title="Missing type annotation",  # D-4
        details="Function parameter lacks type hint.",  # D-4
    )
    assert finding.file_path == "scorer/usage.py"  # D-4
    assert finding.line_number == 15  # D-4
    assert finding.severity == PRFindingSeverity.WARNING  # D-4
    assert finding.suggestion == ""  # D-4: default empty string
    assert finding.pii_leak is False  # D-4: default False


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


def test_pr_review_report_invariant_blocker_enforces_request_changes():
    """Invariant: if any finding has BLOCKER severity, overall_status is coerced to REQUEST_CHANGES."""
    finding = InlineFinding(
        file_path="scorer/usage.py",
        line_number=10,
        severity=PRFindingSeverity.BLOCKER,  # D-4
        title="Fatal issue",
        details="Critical error.",
    )
    report = PRReviewReport(
        overall_status=ReviewStatus.APPROVE,  # D-4: initially passed APPROVE
        summary="Initial review summary",
        findings=[finding],
    )
    assert report.overall_status == ReviewStatus.REQUEST_CHANGES  # D-4: enforced


def test_pr_review_report_invariant_pii_leak_enforces_request_changes():
    """Invariant: if any finding has pii_leak=True, overall_status is coerced to REQUEST_CHANGES."""
    finding = InlineFinding(
        file_path="config/keys.py",
        line_number=1,
        severity=PRFindingSeverity.WARNING,
        title="Key leak",
        details="Secret exposed.",
        pii_leak=True,  # D-4
    )
    report = PRReviewReport(
        overall_status=ReviewStatus.APPROVE,  # D-4: initially passed APPROVE
        summary="Initial review summary",
        findings=[finding],
    )
    assert report.overall_status == ReviewStatus.REQUEST_CHANGES  # D-4: enforced


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


@pytest.mark.asyncio
async def test_run_pr_review_mock_agent_approve(tmp_path, monkeypatch):
    """Scenario: Mocked Antigravity Agent returns clean APPROVE PR review."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    pii_scan = reports_dir / "pii-scan.txt"
    pii_scan.write_text("No findings", encoding="utf-8")

    expected_report = PRReviewReport(
        overall_status=ReviewStatus.APPROVE,
        summary="All PR changes look clean and well-structured.",
        findings=[],
    )

    mock_response = MagicMock()
    mock_response.structured_output = AsyncMock(return_value=expected_report)
    mock_agent_instance = MagicMock()
    mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
    mock_agent_instance.__aexit__ = AsyncMock(return_value=None)
    mock_agent_instance.chat = AsyncMock(return_value=mock_response)

    with patch.object(pr_reviewer_agent, "Agent", return_value=mock_agent_instance):
        report = await run_pr_review(
            pr_number="123",  # D-5
            repo="owner/repo",
            token="ghp_testtoken",
            pii_report_path=str(pii_scan),
            project_id="test-project",
            location="us-central1",
        )

    assert report is not None  # D-5
    assert report.overall_status == ReviewStatus.APPROVE  # D-4
    assert os.path.exists("reports/pr-review.json")  # D-6
    assert os.path.exists("reports/pr-review.txt")  # D-6
    with open("reports/pr-review.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["overall_status"] == "APPROVE"  # D-4, D-6


@pytest.mark.asyncio
async def test_run_pr_review_mock_agent_config_and_telemetry(tmp_path, monkeypatch):
    """Validates LocalAgentConfig parameters, MCP server setup, and telemetry dir."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    expected_report = PRReviewReport(
        overall_status=ReviewStatus.APPROVE,
        summary="PR approved.",
        findings=[],
    )

    mock_response = MagicMock()
    mock_response.structured_output = AsyncMock(return_value=expected_report)
    mock_agent_instance = MagicMock()
    mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
    mock_agent_instance.__aexit__ = AsyncMock(return_value=None)
    mock_agent_instance.chat = AsyncMock(return_value=mock_response)

    with patch.object(pr_reviewer_agent, "Agent", return_value=mock_agent_instance) as mock_agent_cls:
        await run_pr_review(
            pr_number="99",
            repo="my-org/my-repo",
            token="test-token",
            pii_report_path=str(reports_dir / "pii-scan.txt"),
            project_id="test-proj",
            location="us-central1",
        )

        mock_agent_cls.assert_called_once()
        captured_config = mock_agent_cls.call_args[0][0]

    assert captured_config is not None
    assert captured_config.model == "gemini-3.7-flash"  # D-2
    assert captured_config.vertex is True  # D-2
    assert captured_config.project == "test-proj"  # D-2
    assert len(captured_config.mcp_servers) == 1  # D-11
    mcp = captured_config.mcp_servers[0]
    assert mcp.command == "docker"  # D-11
    assert "ghcr.io/github/github-mcp-server:v0.27.0" in mcp.args  # D-11
    assert os.path.isdir("reports/telemetry/pr_review_agent")  # D-10


@pytest.mark.asyncio
async def test_run_pr_review_streams_thinking_and_output(tmp_path, monkeypatch, capsys):
    """Scenario: Validates streaming of Thought, ToolCall, ToolResult, and Text chunks."""
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    expected_report = PRReviewReport(
        overall_status=ReviewStatus.APPROVE,
        summary="PR approved with streaming logs.",
        findings=[],
    )

    from google.antigravity import types

    async def mock_chunks_gen():
        yield types.Thought(step_index=0, text="Deep thinking about PR #42 security posture...")
        yield types.ToolCall(name="get_pull_request", args={"pr": 42})
        yield types.ToolResult(name="get_pull_request", result={"title": "Fix bug"})
        yield types.Text(step_index=0, text="PR analysis complete.")

    mock_response = MagicMock()
    mock_response.chunks = mock_chunks_gen()
    mock_response.structured_output = AsyncMock(return_value=expected_report)

    mock_agent_instance = MagicMock()
    mock_agent_instance.__aenter__ = AsyncMock(return_value=mock_agent_instance)
    mock_agent_instance.__aexit__ = AsyncMock(return_value=None)
    mock_agent_instance.chat = AsyncMock(return_value=mock_response)

    with patch.object(pr_reviewer_agent, "Agent", return_value=mock_agent_instance):
        report = await run_pr_review(
            pr_number="42",
            repo="owner/repo",
            token="ghp_token",
            pii_report_path=str(reports_dir / "pii-scan.txt"),
            project_id="test-proj",
            location="us-central1",
        )

    assert report is not None
    assert report.overall_status == ReviewStatus.APPROVE
    captured = capsys.readouterr()
    assert "Deep thinking about PR #42 security posture..." in captured.out
    assert "get_pull_request" in captured.out
    assert "Structured LLM Output" in captured.out

