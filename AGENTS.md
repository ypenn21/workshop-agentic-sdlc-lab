# Account Health Scorer & Agentic SDLC

## Overview

This repository is a reference demonstrating an end-to-end **Agentic Software Development Life Cycle (SDLC)**. The project implements a pure-Python account health scoring service driven by two core software engineering methodologies:
1. **Spec-Driven Development (SDD)**: Interrogating vague requirements, eliminating ambiguities, and formalizing decisions before writing code.
2. **Test-Driven Development (TDD)**: Emitting strict acceptance contract tests and stubbed interfaces derived directly from approved specification decisions before implementation.

The repository also includes a deployable remote coding agent (`coder-agent`) built with the Google Agent Development Kit (ADK) and Antigravity SDK, deployed to Vertex AI Reasoning Engine / Gemini Enterprise Agent Platform (GEAP) under its own Agent Identity.

---

## Repository Architecture & Layout

```
workshop-agentic-sdlc-lab/
├── AGENTS.md                  # Startup context and operational rules for agy CLI
├── README.md                  # Repository introduction
├── pyproject.toml             # Python project configuration and pytest settings
├── uv.lock                    # Dependency lockfile
├── fixtures/                  # Test data fixtures
│   └── usage.csv              # Monthly account usage export (account_id, month, seats, logins, tickets)
├── scorer/                    # Core Python application
│   ├── main.py                # CLI entry point; handles file I/O and terminal reporting
│   ├── usage.py               # Pure domain models (MonthSnapshot, Result) & scoring interface
│   └── tests/                 # Test suite
│       ├── test_starter.py    # Baseline smoke tests for fixtures and CSV structure
│       ├── test_parse_contract.py # Contract tests for parse_usage()
│       ├── test_score_contract.py # Contract tests for score()
│       └── test_integration.py    # End-to-end composition tests
├── coder-agent/               # Remote ADK / Vertex AI Agent Engine application
│   ├── Dockerfile             # Container definition for Agent Runtime
│   ├── GEMINI.md              # Agent development guide for coder-agent
│   ├── pyproject.toml         # Dependencies for the remote agent service
│   ├── app/                   # ADK agent application and FastAPI backend
│   │   ├── agent.py           # CoderAgent (BaseAgent yielding session events)
│   │   ├── coder_client.py    # Async subprocess client running coder harness
│   │   └── fast_api_app.py    # HTTP / Reasoning Engine API adapter
│   ├── coder_runtime/         # Antigravity SDK harness inside the container
│   │   ├── coder.py           # Autonomous TDD loop (reads spec/tests, edits usage.py, pushes)
│   │   └── workspace.py       # Git clone and deployment key manager
│   └── deployment/terraform/  # Infrastructure-as-code for Agent Platform and IAM
├── scripts/                   # Operational and lifecycle automation scripts
│   ├── setup-deploy-key.sh    # Provisions SSH deploy key into Secret Manager for remote agent
│   ├── agent-identity.sh      # Validates SPIFFE Agent Identity on Vertex AI
│   ├── dispatch.sh            # Dispatches pinned commit to remote coder-agent & monitors branch
│   ├── trajectory.py          # Formats and renders remote agent trajectory stream
│   └── teardown.sh            # Cleans up deployed engines, secrets, and deploy keys
└── .agents/                   # Workspace customizations for Antigravity CLI (agy)
    ├── agents/                # Custom subagents (e.g. contract-writer)
    ├── hooks/                 # Lifecycle hooks (auto-allow rules for pytest and writes)
    ├── hooks.json             # Hook declarations
    ├── rules/                 # Hierarchical workspace behavior rules (behavior.md)
    └── skills/                # On-demand skills (spec-adversary, coder-dispatch, jira-plan-cli)
```

---

## Domain Logic & Interface Contracts

The scoring system is split into two pure functions in `scorer/usage.py`. Neither touches the filesystem.

### Data Structures
- **`MonthSnapshot`**:
  - `account_id`: `str`
  - `month`: `str` (format `YYYY-MM`)
  - `seats_active`: `int` (blank in CSV is parsed as `0`)
  - `logins`: `int`
  - `tickets_open`: `int`
- **`Result`**:
  - `score`: `int` (floored at 0, starting at 10)
  - `tier`: `str` (`"HEALTHY"`: 8–10, `"MEDIUM"`: 5–7, `"AT RISK"`: 0–4)
  - `reasons`: `list[str]` (ordered list of reasons for deductions that fired)

### Scoring Rules
1. **Seat Decline (−4 points, reason: `seats down sharply`)**: Latest month's seats fallen by 40% or more compared to the peak seat count across all prior recorded months. Single-month accounts do not trigger this rule.
2. **Low Engagement (−3 points, reason: `low engagement`)**: Fewer than 3 logins in the latest month.
3. **Unresolved Support Load (−2 points, reason: `unresolved support load`)**: 2 or more tickets open in the latest month.

---

## Standard Development & Agentic SDLC Workflow

### 1. Requirements & Spec Interrogation
- Work from `docs/request.md` and `docs/spec.md`.
- Activate the `spec-adversary` skill to interrogate the specification for ambiguities one at a time.
- All resolutions must be recorded as explicit rules in the **Decisions** table (`D-1`, `D-2`, etc.) in `docs/spec.md`.

### 2. Contract Generation (Acceptance Tests)
- Invoke the `contract-writer` subagent to convert resolved decisions into tests under `scorer/tests/` and stub interfaces in `scorer/usage.py` (which raise `NotImplementedError`).
- Every test assertion must cite its corresponding decision ID (`# D-1`).
- Verify contract failure: `uv run pytest -q` (acceptance tests must fail, starter tests must pass).

### 3. Remote Dispatch or Local Implementation
- **Remote Coder Agent**:
  - Provision deploy key: `bash scripts/setup-deploy-key.sh`
  - Push contract commit to GitHub fork.
  - Dispatch via `coder-dispatch` skill using `geap` MCP tools or `bash scripts/dispatch.sh`.
- **Local Implementation**:
  - Implement `parse_usage()` and `score()` in `scorer/usage.py`.
  - Validate: `uv run pytest -q`.

### 4. Verification & Review
- Test locally: `uv run pytest -q`.
- Run CLI application: `uv run python scorer/main.py`.
- Merge branch and close associated issue.

---

## Essential Commands & Tooling

| Task | Command |
| :--- | :--- |
| **Run All Tests** | `uv run pytest -q` |
| **Run Specific Test File** | `uv run pytest scorer/tests/test_score_contract.py` |
| **Execute Scorer CLI** | `uv run python scorer/main.py` |
| **Inspect Git Status** | `git status --short` |
| **Deploy Remote Coder Agent** | `(cd coder-agent && agents-cli deploy --project $(gcloud config get-value project) --region $AGENT_ENGINE_LOCATION --agent-identity --update-env-vars GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true,MODEL_LOCATION=global --no-wait)` |
| **Check Agent Deployment Status** | `(cd coder-agent && agents-cli deploy --status)` |
| **Verify Agent SPIFFE Identity** | `bash scripts/agent-identity.sh` |
| **Setup Deploy Key** | `bash scripts/setup-deploy-key.sh` |
| **Dispatch Coding Job** | `bash scripts/dispatch.sh --branch agent/parse --issue 1` |
| **Teardown Workshop Cloud Resources** | `bash scripts/teardown.sh` |

---

## Agent & Skill Ecosystem

### Available Custom Skills
- **`spec-adversary`** (`.agents/skills/spec-adversary/SKILL.md`): Adversarial interrogator for `docs/spec.md`. Discovers ambiguities, asks one choice at a time via `ask_question`, and records decisions in the spec.
- **`coder-dispatch`** (`.agents/skills/coder-dispatch/SKILL.md`): Dispatches pinned commits to the remote `coder-agent` on Vertex AI / GEAP via `geap` MCP tools, streams trajectories, and manages GitHub/Jira ticket lifecycles.
- **`jira-plan-cli`** (`.agents/skills/jira-plan-cli/SKILL.md`): Integrates with Jira/Confluence via `acli` and generates implementation plans in `plans/`.
- **`jira-get-ticket`** (`.agents/skills/jira-get-ticket/SKILL.md`): Retrieves and inspects Jira tickets/workitems using `acli`.

### Available Subagents
- **`contract-writer`** (`.agents/agents/contract-writer/agent.md`): Authors acceptance contract tests (`test_parse_contract.py`, `test_score_contract.py`, `test_integration.py`) and stubbed `scorer/usage.py` directly from spec decisions without implementing behavior.
- **`research`**: Read-only exploration agent for analyzing large files and codebase areas.
- **`self`**: General-purpose isolated subagent inheriting the full environment.

### MCP Servers
- **`geap`**: Tools (`list_agents`, `start_query`, `read_query`, `cancel_query`) to communicate with deployed Gemini Enterprise Agent Platform agents.
- **`atlassian-mcp-server`**: Tools for Jira issues and Confluence spaces.
- **`google-cloud-resource-manager`**: GCP project discovery.
- **`google-developer-knowledge`**: Google Cloud & Vertex AI technical documentation lookups.
- **`context7`**: Documentation indexing and search.

---

## Critical Rules & Guardrails

1. **Pure Function Discipline**: `scorer/usage.py` must NEVER import `os`, `pathlib`, `open`, or perform file/network I/O. File reading belongs strictly in `scorer/main.py`.
2. **Contract Immutability**: NEVER modify contract tests in `scorer/tests/` to make an implementation pass. If code fails a contract test, the implementation is incorrect.
3. **Spec Decision Traceability**: Every assertion in contract tests must link to an explicit decision ID (`D-N`) in `docs/spec.md`.
4. **Model Location Constraints**: Gemini 3 models on Vertex AI / Agent Engine must use `MODEL_LOCATION=global`. The reasoning engine region is set by `AGENT_ENGINE_LOCATION` (e.g., `us-central1`).
5. **No Blind Test Runs**: Always execute commands with intent and understand failure causes before modifying code.


👉 **supervisor-workflow Rules**

Please read and follow the instructions in `.agents/rules/supervisor-workflow.md` whenever designing, chunking, implementing, or testing new features.