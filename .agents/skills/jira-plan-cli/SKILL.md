---
name: jira-plan-cli
description: Fetches, manages, and edits Jira issues and Confluence spaces/pages using the `acli` CLI tool, inspects the codebase, and generates a structured implementation plan in the plans/ directory.
---

# Jira & Confluence Plan CLI Skill

Use this skill to manage/retrieve Jira tickets and Confluence documents/pages using the Atlassian CLI (`acli`) and generate a comprehensive, read-only implementation plan for the requested feature.

## 🔗 Reference Documentation
- **Getting Started Guide**: [Atlassian CLI (acli) Guide](https://developer.atlassian.com/cloud/acli/guides/how-to-get-started/)
- **Installation Guide**: [Install Atlassian CLI Guide](https://developer.atlassian.com/cloud/acli/guides/install-acli/)
- **CLI Commands**: `acli jira workitem --help`, `acli confluence --help`, `man acli`

---

## Phase 0: Installation & Authentication

1. **Verify & Install `acli`**:
   Check if `acli` is installed:
   ```bash
   acli --version
   ```
   If `acli` is not installed, install it using your system's package manager or binary download (see the [Atlassian CLI Installation Guide](https://developer.atlassian.com/cloud/acli/guides/install-acli/)):
   - **macOS (Homebrew)**:
     ```bash
     brew tap atlassian/homebrew-acli
     brew install acli
     ```
   - **macOS / Linux (Curl Binary)**:
     ```bash
     # Apple Silicon macOS
     curl -LO "https://acli.atlassian.com/darwin/latest/acli_darwin_arm64/acli"
     # Intel macOS
     # curl -LO "https://acli.atlassian.com/darwin/latest/acli_darwin_amd64/acli"

     chmod +x ./acli
     sudo mv ./acli /usr/local/bin/acli
     ```
   - **Windows & Other OS**: Refer to the [Installation Guide](https://developer.atlassian.com/cloud/acli/guides/install-acli/) for platform-specific instructions.

2. **Mandatory Authentication**:
   Always ensure authentication first before executing any Jira or Confluence operations:

   ```bash
   acli auth login
   ```

---

## Phase 1: Jira Ticket Retrieval & Search via CLI (`acli`)

1. **Identify Target Ticket**:
   - Always scope searches to project `OPS` (`project = OPS`).
   - Search Jira issues using `acli jira workitem search`:
     - **With Priority**:
       ```bash
       acli jira workitem search --jql "project = OPS AND priority = '{{args}}' ORDER BY created DESC" --limit 5 --json
       ```
     - **Without Priority**:
       ```bash
       acli jira workitem search --jql "project = OPS ORDER BY created DESC" --limit 5 --json
       ```
     - **Formatted Output**:
       ```bash
       acli jira workitem search --jql "project = OPS AND priority = 'Medium' ORDER BY created DESC" --fields "key,issuetype,summary,priority,status,assignee"
       ```
   - If no issue key is provided or multiple candidate tickets are returned, use `ask_question` to let the user select the desired ticket from project `OPS`.

2. **Retrieve Full Ticket Details**:
   - If a specific Issue Key (e.g., `OPS-9`) is specified or selected:
     ```bash
     acli jira workitem view OPS-9 --json
     ```
   - Extract Issue Key, Summary, Priority, Status, Assignee, Type, and **Description**.
   - Announce the retrieved ticket details to the user and state that you are transitioning to **Planning Mode**.

---

## Phase 2: Confluence Spaces, Pages & Documents via CLI (`acli`)

Use `acli confluence` commands to search, list, view, and inspect Confluence documentation and requirements:

1. **List Spaces**:
   - List all accessible Confluence spaces:
     ```bash
     acli confluence space list
     ```
   - List spaces in JSON format to extract numeric Space IDs and Homepage IDs:
     ```bash
     acli confluence space list --json
     ```

2. **View Space Details**:
   - View metadata for a specific space by Space ID:
     ```bash
     acli confluence space view --id <SPACE_ID>
     ```

3. **View Confluence Pages & Retrieve Contents**:
   - View basic page details and check for direct child pages:
     ```bash
     acli confluence page view --id <PAGE_ID> --include-direct-children
     ```
   - Retrieve page body contents in storage (XHTML) or view format in JSON:
     ```bash
     acli confluence page view --id <PAGE_ID> --body-format storage --json
     ```
   - Extract raw page markup/value using `jq`:
     ```bash
     acli confluence page view --id <PAGE_ID> --body-format storage --json | jq -r '.body.storage.value'
     ```

4. **List Blog Posts**:
   - List Confluence blog posts in a space:
     ```bash
     acli confluence blog list --space-id <SPACE_ID>
     ```

---

## Phase 3: Jira Ticket Operations & Editing via CLI (`acli`)

Use `acli` commands when ticket updates, status transitions, or field edits are requested:

1. **Transition Ticket Status**:
   - Move ticket to a new status (e.g., `In Progress`, `To Do`, `Done`):
     ```bash
     acli jira workitem transition --key OPS-9 --status "In Progress" --yes
     ```
   - Transition via JQL:
     ```bash
     acli jira workitem transition --jql "project = OPS AND key = 'OPS-9'" --status "In Progress" --yes
     ```

2. **Edit Workitem Fields**:
   - Change Issue Type (e.g., Story to Task):
     ```bash
     acli jira workitem edit --key OPS-5 --type "Task" --yes
     ```
   - Assign Workitem:
     ```bash
     acli jira workitem edit --key OPS-9 --assignee "@me" --yes
     ```
   - Update Summary or Description:
     ```bash
     acli jira workitem edit --key OPS-9 --summary "New Summary Title" --yes
     acli jira workitem edit --key OPS-9 --description "Updated description text" --yes
     ```

---

## Phase 4: Codebase Investigation & Analysis

1. **READ-ONLY Mandate**:
   - Analyze the codebase strictly using read-only inspection tools (`list_dir`, `view_file`, `grep_search`).
   - Do **NOT** modify or create any implementation files or configurations during this phase. The **only file** permitted to write is the final plan file inside the `plans/` directory.
   - Do **NOT** execute shell commands that introduce side effects (e.g., `git commit`, `npm install`, `pip install`).

2. **Investigate Codebase**:
   - Locate relevant modules, components, routes, schemas, and configuration files.
   - Inspect existing architecture, data flows, and project coding conventions.
   - Identify precise files and line numbers that will require modification or creation.

---

## Phase 5: Plan Document Generation

1. **Write the Plan File**:
   - Name the file using a descriptive, lower-case slug: `plans/<feature-slug>.md`.
   - Ensure the `plans/` directory exists (create it automatically when writing).
   - Save the implementation plan using `write_to_file`.

2. **Plan Document Format**:

```markdown
# Feature Implementation Plan: [Feature Name]

## 📋 Todo Checklist
- [ ] [High-level milestone 1]
- [ ] [High-level milestone 2]
- [ ] Final Review and Testing

## 🔍 Analysis & Investigation

### Codebase Structure & Inspected Files
- [file_path](file:///absolute/path/to/file#L1-L50) - Description of relevance

### Current Architecture & Patterns
[Architecture analysis, state management, API patterns, and framework conventions]

### Dependencies & Integration Points
[External APIs, database schemas, or third-party libraries]

### Considerations & Challenges
[Potential edge cases, security implications, or performance bottlenecks]

## 📝 Implementation Plan

### Prerequisites
[Setup, environment variables, or dependencies required]

### Step-by-Step Implementation
1. **Step 1: [Step Title]**
   - Files to modify/create: [`path/to/file`](file:///absolute/path/to/file)
   - Changes needed: [Detailed actionable breakdown and logic]

2. **Step 2: [Step Title]**
   - Files to modify/create: [`path/to/file`](file:///absolute/path/to/file)
   - Changes needed: [Detailed actionable breakdown and logic]

### Testing & Verification Strategy
[Unit tests, integration tests, or manual test steps]

## 🎯 Success Criteria
[Measurable conditions to confirm completion]
```

---

## Final Steps

1. Confirm that `plans/<feature-slug>.md` has been saved.
2. Present a concise summary to the user with a clickable link to the plan file.
3. **DO NOT IMPLEMENT THE PLAN** unless explicitly requested in a follow-up prompt.

