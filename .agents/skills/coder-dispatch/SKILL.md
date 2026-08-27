---
name: coder-dispatch
description: Dispatch coding tasks to the remote coder-agent deployed on Gemini Enterprise Agent Platform (GEAP) and follow its execution live until completion. Use when the user requests dispatching work, implementing tasks via the remote coder agent, or running queries against the GEAP coder-agent.
---

# Coder Dispatch Skill

You dispatch coding jobs to the `coder-agent` deployed on Google Cloud Agent Platform (GEAP) using the `geap` MCP tools, and stream the agent's progress in real time.

## Required Tools

- `call_mcp_tool` (for `geap` MCP server tools: `list_agents`, `start_query`, `read_query`)
- `ask_question` (for clarifying ambiguous or missing parameters)
- `run_command` (for querying local git context)
- `view_file` & `list_dir` (for inspecting repository files)

## 1. Inspect and Clarify Parameters

Before dispatching, ensure all required parameters (`owner/repo`, `COMMIT_SHA`, `branch_name`, and `issue_number`) are clear and resolved. **If any parameter is ambiguous, missing, or has multiple possibilities, utilize the `ask_question` tool to clarify with the user before proceeding.**

1. **Repository (`owner/repo`)**:
   - Inspect `git remote get-url origin`.
   - Extract `<owner>/<repo>` (e.g., `ypenn21/workshop-agentic-sdlc-lab`, verifying it targets the expected repository ending in `-lab`).
   - If the repository cannot be determined automatically or is ambiguous, prompt the user using `ask_question`.

2. **Base Commit (`COMMIT_SHA`)**:
   - Determine the current active branch (e.g., `git branch --show-current`) and its latest commit (e.g., `git rev-parse HEAD` or `git rev-parse "origin/$(git branch --show-current)"`).
   - Ensure the commit has been pushed to the remote repository so the remote agent can clone and checkout the exact SHA.
   - If the target base branch or commit is ambiguous, clarify with `ask_question`.

3. **Target Branch (`branch_name`)**:
   - Identify the target branch name to push changes to (default: `agent/parse` unless specified otherwise).
   - If the branch name is ambiguous or unspecified and needs confirmation, confirm with the user using `ask_question`.

4. **Issue Number (`issue_number`)**:
   - Identify the issue number to address (default: `"1"` unless specified otherwise).
   - If the issue number or task scope is ambiguous or missing, use `ask_question` to confirm with the user.

## 2. Locate the Deployed Agent

1. Call the `list_agents` tool on the `geap` MCP server (passing `project` and `location` if necessary, e.g. `us-central1`).
2. Verify that `coder-agent` exists, `deployed` is `true`, and note its engine name / ID.

## 3. Dispatch the Job (`start_query`)

1. Construct the payload JSON string:
   ```json
   {"repo": "<owner>/<repo>", "sha": "<COMMIT_SHA>", "branch": "<branch_name>", "issue": "<issue_number>"}
   ```
2. Call the `start_query` tool on `geap` with:
   - `engine`: `"coder-agent"` (or the engine's resource name)
   - `message`: The JSON payload string above.
   - `location`: `"us-central1"` (or configured region)
   - `project`: The active project ID (e.g., from `gcloud config get-value project`)
3. Note the returned `run_id`.

## 4. Follow the Run Trajectory (`read_query`)

1. Initialize `cursor` to `0`.
2. In a loop, call `read_query` on `geap` with `run_id` and the current `cursor`.
3. For each call:
   - **Stream Output**: Print any newly returned `lines` immediately before the next call.
   - Update `cursor` to `next_cursor`.
   - Check `state`:
     - If `state` is `"running"`, continue the loop.
     - If `state` is `"done"` or any terminal status, exit the loop.

## 5. Report Summary & Next Steps

When the run finishes:
1. Print the final narration lines and tool call metrics if available.
2. Present a clear summary containing:
   - Repository and base commit SHA dispatched
   - Branch where changes were pushed
   - Associated issue number
   - GitHub compare link: `https://github.com/<owner>/<repo>/compare/<base_branch>...<branch>`
   - Next steps for testing and reviewing the branch:
     ```bash
     git fetch origin <branch> && git checkout -b review origin/<branch> && uv run pytest -q
     ```
