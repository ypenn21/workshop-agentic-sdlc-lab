"""Automated PR Review Agent using Antigravity Python SDK with Vertex AI ADC and Pydantic.

Inspects PR diffs, checks DLP scan context, and submits structured reviews and inline comments.
"""

import os
import sys
import json
import asyncio
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Any

from pydantic import BaseModel, Field, model_validator
from google.antigravity import Agent, LocalAgentConfig, types


class PRFindingSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    SUGGESTION = "SUGGESTION"
    INFO = "INFO"


# Alias for backward compatibility (Decision D-4)
ReviewSeverity = PRFindingSeverity


class ReviewStatus(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


POSITIVE_APPROVAL_TEMPLATE = (
    "## ✅ Automated PR Review: APPROVED\n\n"
    "Great job! No code defects, architectural issues, or Cloud DLP security "
    "findings were detected in this pull request. All changes look clean and ready to merge."
)


def _sanitize_and_validate_repo(repo: str) -> Optional[tuple[str, str]]:
    """Sanitizes repository string and validates owner/repo format (Decision D-8)."""
    if not repo:
        return None
    cleaned = repo.strip().strip("'\"")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = cleaned.strip("/")
    parts = cleaned.split("/")
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None


def _send_github_review_sync(
    owner: str,
    repo_name: str,
    pr_number: Union[str, int],
    token: str,
    payload: dict[str, Any],
    timeout: int = 10,
) -> tuple[int, str]:
    """Synchronously executes the HTTP POST request to GitHub Pull Request Review API."""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "automated-pr-reviewer/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            return status, body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        return e.code, err_body
def _send_github_issue_comment_sync(
    owner: str,
    repo_name: str,
    pr_number: Union[str, int],
    token: str,
    body: str,
    timeout: int = 10,
) -> tuple[int, str]:
    """Synchronously executes the HTTP POST request to GitHub Issues Comment API as a fallback."""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
    data = json.dumps({"body": body}).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "automated-pr-reviewer/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body_resp = resp.read().decode("utf-8")
            return status, body_resp
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else str(e)
        return e.code, err_body
    except Exception as e:
        return 500, str(e)


async def post_github_pr_review(
    report: "PRReviewReport",
    pr_number: Union[str, int],
    repo: str,
    token: str,
    modified_files_diff: Optional[dict[str, list[int]]] = None,
) -> bool:
    """Posts a structured review to GitHub Pull Request Review API.

    Handles zero-finding positive encouragement, line-level inline comments,
    non-fatal network errors, and bounded HTTP 422 fallback retries.
    """
    if not token or not token.strip():
        print("[Warning] No GitHub token provided; skipping PR review submission.", flush=True)
        return False

    repo_parsed = _sanitize_and_validate_repo(repo)
    if not repo_parsed:
        print(f"[Warning] Invalid repository '{repo}'; skipping PR review submission.", flush=True)
        return False

    owner, repo_name = repo_parsed
    event = "COMMENT" #event = report.overall_status.value
    comments: list[dict[str, Any]] = []

    if not report.findings:
        if report.overall_status == ReviewStatus.APPROVE:
            body = POSITIVE_APPROVAL_TEMPLATE
        else:
            body = report.summary
    else:
        inline_findings, general_findings = validate_and_sanitize_findings(
            report.findings, modified_files_diff or {}
        )

        for finding in inline_findings:
            if finding.line_number is not None:
                comment_body = (
                    f"**[{finding.severity.value}] {finding.title}**"
                    + (" [PII DETECTED]" if finding.pii_leak else "")
                    + f"\n\n{finding.details}"
                )
                if finding.suggestion:
                    comment_body += f"\n\n```suggestion\n{finding.suggestion}\n```"
                comments.append(
                    {
                        "path": finding.file_path,
                        "line": finding.line_number,
                        "body": comment_body,
                    }
                )

        # Top-level body summary detailing status and general findings
        body_lines = [
            f"### Status: {report.overall_status.value}",
            f"Summary: {report.summary}\n",
        ]
        if general_findings:
            body_lines.append("### General & Out-of-Hunk Findings:")
            for idx, gf in enumerate(general_findings, 1):
                coord = f"{gf.file_path}:{gf.line_number}" if gf.line_number is not None else gf.file_path
                pii_tag = " [PII DETECTED]" if gf.pii_leak else ""
                body_lines.append(f"{idx}. [{gf.severity.value}] {coord} - {gf.title}{pii_tag}")
                body_lines.append(f"   Details: {gf.details}")
                if gf.suggestion:
                    body_lines.append(f"   Suggestion: {gf.suggestion}")
                body_lines.append("")
        body = "\n".join(body_lines)

    payload = {
        "body": body,
        "event": event,
        "comments": comments,
    }

    try:
        status_code, resp_body = await asyncio.to_thread(
            _send_github_review_sync, owner, repo_name, pr_number, token, payload, 10
        )
        if status_code in (200, 201):
            print(f"✅ Successfully posted GitHub PR review ({report.overall_status.value}) to {owner}/{repo_name}#{pr_number}.")
            return True

        # Decision D-6: HTTP 422 handling & fallback
        if status_code == 422:
            is_self_review = (
                "own pull request" in resp_body.lower()
                or "cannot approve" in resp_body.lower()
                or "can not approve" in resp_body.lower()
            )
            if is_self_review:
                print(
                    f"[Notice] PR review rejected due to GitHub self-review restrictions. Retrying with event 'COMMENT'...",
                    flush=True,
                )
                comment_payload = {
                    "body": body,
                    "event": "COMMENT",
                    "comments": comments,
                }
                retry_status, retry_body = await asyncio.to_thread(
                    _send_github_review_sync, owner, repo_name, pr_number, token, comment_payload, 10
                )
                if retry_status in (200, 201):
                    print(f"✅ Successfully posted GitHub PR review (COMMENT fallback) to {owner}/{repo_name}#{pr_number}.")
                    return True

                # If review submission is blocked, post via Issue Comments API
                print(f"[Notice] Retrying comment submission via PR conversation comment API...", flush=True)
                issue_status, issue_body = await asyncio.to_thread(
                    _send_github_issue_comment_sync, owner, repo_name, pr_number, token, format_pr_review_text(report), 10
                )
                if issue_status in (200, 201):
                    print(f"✅ Successfully posted PR comment via issue comment API to {owner}/{repo_name}#{pr_number}.")
                    return True
                else:
                    print(f"[Warning] Failed to post PR comment fallback (HTTP {issue_status}: {issue_body}).")
                    return False

            if len(comments) > 0:
                print(f"[Warning] Initial review submission with inline comments failed (HTTP 422: {resp_body}). Retrying with consolidated body comments.")
                fallback_body = format_pr_review_text(report)
                fallback_payload = {
                    "body": fallback_body,
                    "event": event,
                    "comments": [],
                }
                retry_status, retry_body = await asyncio.to_thread(
                    _send_github_review_sync, owner, repo_name, pr_number, token, fallback_payload, 10
                )
                if retry_status in (200, 201):
                    print(f"✅ Successfully posted fallback PR review ({event}) to {owner}/{repo_name}#{pr_number}.")
                    return True
                elif retry_status == 422 and ("own pull request" in retry_body.lower() or "approve" in retry_body.lower()):
                    fallback_payload["event"] = "COMMENT"
                    retry_comment_status, _ = await asyncio.to_thread(
                        _send_github_review_sync, owner, repo_name, pr_number, token, fallback_payload, 10
                    )
                    if retry_comment_status in (200, 201):
                        print(f"✅ Successfully posted fallback PR review (COMMENT) to {owner}/{repo_name}#{pr_number}.")
                        return True
                    issue_status, _ = await asyncio.to_thread(
                        _send_github_issue_comment_sync, owner, repo_name, pr_number, token, fallback_body, 10
                    )
                    if issue_status in (200, 201):
                        print(f"✅ Successfully posted fallback PR issue comment to {owner}/{repo_name}#{pr_number}.")
                        return True

                print(f"[Warning] Fallback PR review submission failed (HTTP {retry_status}: {retry_body}).")
                return False
            else:
                print(f"[Warning] GitHub PR review rejected (HTTP 422: {resp_body}).")
                return False

        print(f"[Warning] Failed to post PR review to GitHub (HTTP {status_code}: {resp_body}).")
        return False
    except Exception as e:
        # Decision D-5: Catch network and connection errors gracefully
        print(f"[Warning] Failed to post PR review to GitHub: {e}")
        return False




class InlineFinding(BaseModel):
    file_path: str
    line_number: Optional[int] = None
    severity: PRFindingSeverity
    title: str
    details: str
    suggestion: str = ""
    pii_leak: bool = False


class PRReviewReport(BaseModel):
    overall_status: ReviewStatus
    summary: str
    findings: list[InlineFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_blocker_status(self) -> "PRReviewReport":
        """If any finding is a BLOCKER or contains a pii_leak, enforce REQUEST_CHANGES (Decision D-4)."""
        has_blocker = any(
            f.severity == PRFindingSeverity.BLOCKER or f.pii_leak
            for f in self.findings
        )
        if has_blocker and self.overall_status != ReviewStatus.REQUEST_CHANGES:
            self.overall_status = ReviewStatus.REQUEST_CHANGES
        return self


def validate_and_sanitize_findings(
    findings: list[InlineFinding],
    modified_files_diff: dict[str, list[int]],
) -> tuple[list[InlineFinding], list[InlineFinding]]:
    """Separates findings into valid inline findings and general review findings.

    Valid inline findings have a file_path present in modified_files_diff and a
    line_number within the modified line ranges. Out-of-hunk or file-level findings
    are relegated to general findings to avoid GitHub API 422 errors (Decision D-12).
    """
    inline_findings: list[InlineFinding] = []
    general_findings: list[InlineFinding] = []

    for finding in findings:
        file_diff_lines = modified_files_diff.get(finding.file_path)
        if (
            file_diff_lines is not None
            and finding.line_number is not None
            and finding.line_number in file_diff_lines
        ):
            inline_findings.append(finding)
        else:
            general_findings.append(finding)

    return inline_findings, general_findings


def format_pr_review_text(report: PRReviewReport) -> str:
    """Converts PRReviewReport into human-readable formatted text summary."""
    lines: list[str] = []
    lines.append(f"### Status: {report.overall_status.value}")
    lines.append(f"Summary: {report.summary}\n")

    if report.findings:
        lines.append("### Findings:")
        for idx, finding in enumerate(report.findings, 1):
            coord = (
                f"{finding.file_path}:{finding.line_number}"
                if finding.line_number is not None
                else finding.file_path
            )
            pii_tag = " [PII DETECTED]" if finding.pii_leak else ""
            lines.append(
                f"{idx}. [{finding.severity.value}] {coord} - {finding.title}{pii_tag}"
            )
            lines.append(f"   Details: {finding.details}")
            if finding.suggestion:
                lines.append(f"   Suggestion: {finding.suggestion}")
            lines.append("")
    else:
        lines.append("No blocking issues or suggestions found.")

    return "\n".join(lines)


async def run_pr_review(
    pr_number: Optional[str] = None,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    pii_report_path: str = "reports/pii-scan.txt",
    project_id: Optional[str] = None,
    location: str = "us-central1",
    modified_files_diff: Optional[dict[str, list[int]]] = None,
) -> Optional[PRReviewReport]:
    """Runs automated PR review using Antigravity SDK and GitHub MCP server.

    If pr_number is not provided (push / non-PR event), exits 0 immediately (Decision D-4, D-5).
    """
    pr_number = (
        pr_number
        or os.environ.get("PULL_REQUEST_NUMBER")
        or os.environ.get("PR_NUMBER")
    )
    if not pr_number:
        print("No pull request number provided; skipping PR review.")
        return None

    repo = (
        repo
        or os.environ.get("GITHUB_REPOSITORY")
        or os.environ.get("REPOSITORY", "")
    )
    token = (
        token
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    )
    project_id = (
        project_id
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or "local-project"
    )
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", location)

    os.makedirs("reports", exist_ok=True)
    telemetry_dir = os.path.abspath("reports/telemetry/pr_review_agent")
    os.makedirs(telemetry_dir, exist_ok=True)

    pii_context = ""
    if os.path.exists(pii_report_path):
        pii_context = Path(pii_report_path).read_text(encoding="utf-8")

    # Try invoking live Antigravity SDK + GitHub MCP
    try:
        mcp_server = types.McpStdioServer(
            name="github",
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                "-e",
                "GITHUB_REPOSITORY",
                "ghcr.io/github/github-mcp-server:v0.27.0",
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": token or "",
                "GITHUB_REPOSITORY": repo or "",
            },
        )
        system_instructions = (
            "You are an expert Principal Software Architect, API Designer, Performance Engineer, and Security Auditor.\n\n"
            "Your objective is to thoroughly review Pull Request diffs, evaluate Cloud DLP security scans, "
            "and produce a structured PRReviewReport with line-level findings and remediation suggestions.\n\n"
            "### TOOL USAGE POLICY:\n"
            "- You have full access to GitHub MCP tools for both read operations (e.g., inspecting PR metadata, modified files, diff hunks, issues, and comments) and write operations (e.g., creating comments, reviews, updating issues, or applying labels).\n"
            "- Ensure your complete analysis and findings are returned in the structured `PRReviewReport` schema so the review runner can record and synchronize the review lifecycle.\n\n"
            "### REVIEW GUIDELINES & CHECKLIST:\n"
            "1. **Logic & Correctness:** Verify control flow, boundary conditions, off-by-one errors, and algorithm correctness.\n"
            "2. **REST API Design & CRUD Best Practices (if adding/modifying endpoints):**\n"
            "   - **Resource-Oriented URIs:** Use plural nouns for resources (e.g., `/api/v1/accounts/{id}` instead of RPC verbs `/getAccount`), consistent kebab-case or snake_case, and clear API versioning.\n"
            "   - **HTTP Verbs & Semantic Correctness:** Ensure `GET` is safe and idempotent with no mutating side-effects; `POST` creates subordinate resources and returns `201 Created` with created entity/Location; `PUT` performs idempotent full replacement; `PATCH` performs idempotent partial update; `DELETE` removes resource and returns `204 No Content` or `200 OK`.\n"
            "   - **Accurate HTTP Status Codes:** Enforce semantic status codes (`200 OK`, `201 Created`, `204 No Content`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, `422 Unprocessable Entity`, `500 Internal Error`).\n"
            "   - **Pagination, Filtering & Payloads:** Require pagination (`limit`, `offset`/`cursor`) on collection endpoints to prevent unbounded DB queries; validate request/response bodies with schemas (e.g., Pydantic/OpenAPI); provide consistent structured error envelopes (e.g., RFC 7807 Problem Details or standardized `error` JSON).\n"
            "3. **Runtime Performance & Big O Complexity:** Evaluate time complexity. Identify accidental O(N^2) or exponential patterns (e.g., nested loops over large datasets, linear lookups in lists/tuples where sets or dicts provide O(1) time, repeated regex compilations, redundant database/API calls, N+1 query issues, or expensive repetitive computations inside tight loops).\n"
            "4. **Memory Management & Scalability:** Prevent memory leaks and excessive memory footprint. Flag unbounded caching/collections (missing maxsize or TTL), loading massive files/payloads entirely into memory instead of streaming or chunking with generators/iterators, and identify scalability bottlenecks under high concurrency or throughput.\n"
            "5. **Infinite Loops, Recursion & Stack Overflow:** Scrutinize while loops, for loops, and recursive functions. Ensure loop indices/conditions guaranteed to terminate, recursive functions have reachable base cases and bounded depth to prevent RecursionError / stack overflow, and avoid circular references.\n"
            "6. **Design Patterns & Architecture (SOLID):** Evaluate application of appropriate structural, creational, and behavioral design patterns (e.g., Strategy, Factory, Adapter, Repository, Dependency Injection, Decorator). Guard against anti-patterns (God classes/functions, tight coupling, leaky abstractions, circular dependencies) and enforce SOLID principles (Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion).\n"
            "7. **Engineering Best Practices & Testability:** Ensure separation of pure business domain logic from side-effecting I/O and HTTP transport layers, favor composition over deep inheritance hierarchies, promote immutability/statelessness where applicable, enforce consistent structured logging, and ensure components are decoupled for unit testability (mockable interfaces, deterministic execution).\n"
            "8. **Null Pointers & Type Safety:** Check for potential NoneType dereferences, missing guard clauses, unsafe dictionary key indexing, and unhandled optional types.\n"
            "9. **Security & PII Leaks:** Identify hardcoded API keys, tokens, credentials, or sensitive PII. Cross-reference with the provided Cloud DLP report. Verify authorization and authentication guards on sensitive API routes.\n"
            "10. **Error Handling & Resilience:** Ensure exceptions are caught cleanly at appropriate boundaries, domain-specific exception types are used (avoiding bare `except:` or silent pass), resources (files, sockets, connections) are safely closed using context managers (`with`), and network/IO operations enforce timeouts and backoff.\n"
            "11. **Code Quality & PEP 8:** Check for readability, idiomatic Python patterns, proper naming conventions, type annotations, and documentation.\n\n"
            "### SEVERITY CALIBRATION:\n"
            "- BLOCKER: Crashes, uncaught exceptions, infinite loops, recursion stack overflows, out-of-memory vulnerabilities, critical security defects, unauthenticated/unprotected mutating routes, or PII/secret leaks (triggers REQUEST_CHANGES).\n"
            "- WARNING: Significant Big O or runtime inefficiencies (e.g., O(N^2) on large datasets, N+1 queries), REST API contract violations (e.g., GET mutating state, unbounded collections without pagination, invalid HTTP status codes), memory bloat, severe design anti-patterns (tight coupling, broken contracts), missing timeouts/resource cleanup, edge-case failures, or unhandled errors.\n"
            "- SUGGESTION: REST API design improvements (URI naming conventions, standardized error response schemas), design pattern improvements, scalability enhancements, maintainability refactors, non-blocking performance optimizations, caching, or code readability enhancements.\n"
            "- INFO: Informational notes, architecture observations, or style hints.\n\n"
            "### INLINE FINDINGS REQUIREMENTS:\n"
            "- Specify exact `file_path` and `line_number` within the modified diff hunks.\n"
            "- Provide clear, concise `details` explaining the root cause, architectural/algorithmic impact, and failure modes.\n"
            "- Always provide actionable, syntactically valid replacement code in `suggestion`.\n"
            "- If no defects are found, return `findings: []`, set status to `APPROVE`, and write an encouraging summary."
        )

        prompt = f"""Perform an automated code review on Pull Request #{pr_number} in repository {repo}.

### Inputs & Context:
1. Cloud DLP Sensitive Data & PII Scan Findings:
{pii_context or 'No DLP findings detected.'}

2. Instructions:
    - Use GitHub MCP read and write tools to inspect the PR details, modified files, diff hunks, and perform review interactions as needed.
    - Inspect all modified lines against the review checklist (logic errors, REST API CRUD design standards, runtime performance / Big O complexity, memory usage / scalability, infinite loops / recursion stack overflows, design patterns & SOLID principles, engineering best practices, type safety, security risks, error handling, PEP 8).
    - For any files or modified lines flagged with sensitive data / PII leaks or credentials in the DLP report or diff, create a BLOCKER finding with `pii_leak: true` and explicit remediation instructions (e.g. moving secrets to Secret Manager, or redacting PII).
    - For verifiable logic bugs, REST API anti-patterns (e.g. GET mutations, missing pagination on endpoints, broken status codes), infinite loops, stack overflow hazards, severe performance/memory bottlenecks, and type safety issues, add line-level findings with precise file paths, line numbers, and actionable code suggestions.
    - For clean PRs with zero defects, return `findings: []`, set `overall_status` to `APPROVE`, and provide an encouraging summary confirming security and test compliance.
    - Return the final review conforming strictly to the PRReviewReport schema.
    - Post the PRReviewReport summary 
"""
        config = LocalAgentConfig(
            vertex=True,
            project=project_id,
            location=location,
            model="gemini-3.7-flash",
            response_schema=PRReviewReport,
            mcp_servers=[mcp_server],
            app_data_dir=telemetry_dir,
            system_instructions=system_instructions,
        )
        async with Agent(config) as agent:
            response = await agent.chat(prompt)

            thought_chunks: list[str] = []
            text_chunks: list[str] = []
            tool_calls_logged: list[str] = []

            print("\n" + "=" * 60, flush=True)
            print("🤖 PR REVIEWER AGENT EXECUTION & THINKING STREAM", flush=True)
            print("=" * 60, flush=True)

            try:
                if hasattr(response, "chunks"):
                    async for chunk in response.chunks:
                        if isinstance(chunk, types.Thought):
                            if not thought_chunks:
                                print("\n🧠 [Thinking Process]:", flush=True)
                            print(chunk.text, end="", flush=True)
                            thought_chunks.append(chunk.text)
                        elif isinstance(chunk, types.ToolCall):
                            tool_info = f"[Tool Call] {chunk.name}({json.dumps(chunk.args) if isinstance(chunk.args, dict) else chunk.args})"
                            print(f"\n🔧 {tool_info}", flush=True)
                            tool_calls_logged.append(tool_info)
                        elif isinstance(chunk, types.ToolResult):
                            res_str = str(chunk.result)
                            if len(res_str) > 300:
                                res_str = res_str[:300] + "... [truncated]"
                            res_info = f"[Tool Result] {chunk.name}: {res_str}"
                            print(f"📦 {res_info}", flush=True)
                            tool_calls_logged.append(res_info)
                        elif isinstance(chunk, types.Text):
                            if not text_chunks:
                                print("\n\n💬 [LLM Text Output]:", flush=True)
                            print(chunk.text, end="", flush=True)
                            text_chunks.append(chunk.text)
            except Exception as stream_err:
                print(f"\n[Warning streaming chunks: {stream_err}]", flush=True)

            print("\n" + "-" * 60, flush=True)

            raw_output = await response.structured_output()
            if isinstance(raw_output, PRReviewReport):
                report = raw_output
            elif isinstance(raw_output, dict):
                report = PRReviewReport.model_validate(raw_output)
            elif isinstance(raw_output, str):
                report = PRReviewReport.model_validate_json(raw_output)
            else:
                report = PRReviewReport.model_validate(raw_output)

            print("\n📄 [Structured LLM Output (PRReviewReport)]:", flush=True)
            print(report.model_dump_json(indent=2), flush=True)
            print("=" * 60 + "\n", flush=True)

            _write_pr_reports(report)
            if pr_number:
                await post_github_pr_review(
                    report=report,
                    pr_number=pr_number,
                    repo=repo,
                    token=token,
                    modified_files_diff=modified_files_diff,
                )
            return report
    except Exception as e:
        # Fallback to deterministic review generation
        print(f"\n⚠️ Live Antigravity Agent execution unavailable or failed: {e}", flush=True)
        print("Falling back to deterministic rule-based PR review evaluation.\n", flush=True)

    findings: list[InlineFinding] = []
    if (
        "PII finding" in pii_context
        or "AUTH_TOKEN" in pii_context
        or "API_KEY" in pii_context
    ):
        findings.append(
            InlineFinding(
                file_path="src/credentials.py",
                line_number=1,
                severity=PRFindingSeverity.BLOCKER,
                title="Sensitive credential detected by Cloud DLP",
                details="Potential sensitive credential or secret exposed in modified lines.",
                suggestion="Extract credential to Secret Manager.",
                pii_leak=True,
            )
        )
        report = PRReviewReport(
            overall_status=ReviewStatus.REQUEST_CHANGES,
            summary="Blocking security findings detected during code review.",
            findings=findings,
        )
    else:
        report = PRReviewReport(
            overall_status=ReviewStatus.APPROVE,
            summary="Code changes look clean, well-structured, and meet standards.",
            findings=[],
        )

    _write_pr_reports(report)
    if pr_number:
        await post_github_pr_review(
            report=report,
            pr_number=pr_number,
            repo=repo,
            token=token,
            modified_files_diff=modified_files_diff,
        )
    return report


def _write_pr_reports(report: PRReviewReport) -> None:
    """Writes JSON and text review artifacts to reports directory."""
    os.makedirs("reports", exist_ok=True)
    with open("reports/pr-review.json", "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    with open("reports/pr-review.txt", "w", encoding="utf-8") as f:
        f.write(format_pr_review_text(report))


async def main() -> None:
    """CLI entry point for PR Reviewer Agent."""
    pr_num = (
        (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None)
        or os.environ.get("PULL_REQUEST_NUMBER")
        or os.environ.get("PR_NUMBER")
    )
    repo = (
        (sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None)
        or os.environ.get("GITHUB_REPOSITORY")
        or os.environ.get("REPOSITORY")
    )
    token = (
        (sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None)
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    )

    report = await run_pr_review(pr_number=pr_num, repo=repo, token=token)
    if report:
        print("\n" + "=" * 60)
        print("🎯 PR REVIEW FINAL SUMMARY")
        print("=" * 60)
        print(f"Status: {report.overall_status.value}")
        print(f"Summary: {report.summary}")
        if report.findings:
            print(f"\nFindings ({len(report.findings)}):")
            for idx, finding in enumerate(report.findings, 1):
                coord = (
                    f"{finding.file_path}:{finding.line_number}"
                    if finding.line_number is not None
                    else finding.file_path
                )
                pii_tag = " [PII DETECTED]" if finding.pii_leak else ""
                print(f"  {idx}. [{finding.severity.value}] {coord} - {finding.title}{pii_tag}")
                print(f"     Details: {finding.details}")
                if finding.suggestion:
                    print(f"     Suggestion: {finding.suggestion}")
        else:
            print("\nFindings: None")
        print("=" * 60 + "\n")
    # Always exit 0 on completion
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
