---
trigger: always_on
description: Mandatory lifecycle and orchestration protocol for feature implementation, specification creation, bug fixing, and refactoring via the Supervisor and agent swarm.
---

# Feature Implementation & Supervisor Workflow Protocol

## 1. Scope & Mandatory Entry Point

This protocol applies whenever any of the following is requested:
- New feature implementation or enhancement
- Specification creation (PRDs, specs, user stories, requirements drafting)
- Architectural refactor or structural migration
- Non-trivial bug fixing or defect remediation

**Mandatory Rule:** All lifecycle operations MUST originate under the orchestration of the **Supervisor** (`.agents/agents/supervisor/agent.md`). Ad-hoc code writing, unapproved planning, or standalone un-architected specs are strictly prohibited.

> [!IMPORTANT]
> CRITICAL ORCHESTRATION RULE:
> When orchestrating custom subagents you MUST use the Direct Injection Proxy Method:
> 1. Read the custom agent's exact markdown instruction file from the workspace (e.g., `.agents/agents/{agent_name}/agent.md`).
> 2. **ALWAYS set `TypeName: "self"`** when calling `invoke_subagent` (e.g., for Technical Architect and Software Engineer). Using `TypeName: "self"` ensures the subagent inherits the full parent agent capabilities—including write tools (`replace_file_content`, `write_to_file`) and command execution tools (`run_command`)—enabling subagents to create files, write code, and run test suites directly without delegating edits back to the parent.
> 3. Set the `Role` parameter to the descriptive role name (e.g. `Role: "Technical Architect"` or `Role: "Software Engineer"`).
> 4. Inject the entire verbatim contents of the custom agent's markdown file into the `Prompt` argument, appended with the user's specific task instructions.

---

## 2. Lifecycle Phase Matrix

| Phase | Name | Lead Role / Subagent | Subagent Invocation (`invoke_subagent`) | Input Artifact | Output Artifact | Mandatory Gate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | **Strategic Research** | `supervisor` | Handled directly by `supervisor` (`.agents/agents/supervisor/agent.md`) | User prompt / request | `plans/research/{topic}_context.md` | Context Report generated |
| **1** | **Product Discovery** | `product-owner` / `visual-product-owner` | `invoke_subagent(TypeName: "self", Role: "Product Owner", Prompt: "<injected agent.md> + task instructions")` | Context Report | `plans/active_milestones/{moniker}/spec.md`, `plans/00-ROADMAP.md` | Grill Loop complete; Gherkin ACs defined |
| **2** | **Tactical Planning** | `architect` / `visual-architect` | `invoke_subagent(TypeName: "self", Role: "Technical Architect", Prompt: "<injected agent.md> + task instructions")` | Milestone `spec.md` | `plans/active_milestones/{moniker}/plan.md` | Execution groups & test harness structured |
| **3** | **Human Review Gate** | **User / Human Gate** | *None (Execution paused for human review)* | Milestone `spec.md` & `plan.md` | Explicit Approval ("approve" / "proceed") | 🛑 **STOP & WAIT FOR USER APPROVAL** |
| **4** | **Construction Loop** | `engineer` ⇄ `auditor` | Parallel `invoke_subagent(TypeName: "self", Role: "Software Engineer", ...)` (up to 4) ⇄ `invoke_subagent(TypeName: "self", Role: "Quality Auditor", ...)` | Execution Groups in `plan.md` | Working source code + unit/contract tests | Green audit verdict per execution group |
| **5** | **Release & Tagging** | `supervisor` | Handled directly by `supervisor` (`.agents/agents/supervisor/agent.md`) (or `invoke_subagent(TypeName: "self", Role: "Product Owner", ...)` for roadmap update) | Completed Milestone(s) | Git tag + Shipped status in `plans/00-ROADMAP.md` | Explicit human release approval |

---

## 3. Detailed Execution Protocols

### Phase 0: Strategic Research (`supervisor`)
- **Trigger:** Initial user request.
- **Action:** Handled directly by the `supervisor` (`.agents/agents/supervisor/agent.md`).
- **Directives:**
  - Survey codebase structure, existing domain logic, fixtures, and constraints.
  - Compile findings into a Context Report at `plans/research/{topic}_context.md`.
  - Pass the artifact path to the next phase.

### Phase 1: Product Discovery & Spec Creation (`product-owner`)
- **Trigger:** Context Report available in `plans/research/`.
- **Action:** Dispatch `product-owner` (or `visual-product-owner`).
- **Directives:**
  - Execute the **Grill Loop**: Ask up to 3 Socratic questions at a time to clarify edge cases, boundaries, and validation rules.
  - Create milestone folder `plans/active_milestones/{moniker}/`.
  - Move Context Report to `plans/active_milestones/{moniker}/context.md`.
  - Author formal Gherkin-compliant specification in `plans/active_milestones/{moniker}/spec.md`.
  - Register or update milestone status in `plans/00-ROADMAP.md`.

### Phase 2: Tactical Planning (`architect`)
- **Trigger:** Milestone `spec.md` finalized.
- **Action:** Dispatch `architect` (or `visual-architect`).
- **Directives:**
  - Inspect codebase and read `spec.md`.
  - Produce micro-stepped, machine-readable `plan.md` organized into parallelizable **Execution Groups**.
  - Define test-first safety harness and static verification targets.

### Phase 3: Human Review Gate (🛑 MANDATORY STOP)
- **Trigger:** `spec.md` and `plan.md` generated.
- **Action:** **STOP EXECUTION.** Present milestone artifacts to the user.
- **Requirement:** Do NOT dispatch any implementation roles or write code until the user explicitly responds with approval (e.g., "approve", "proceed").

### Phase 4: Construction Loop (`engineer` ⇄ `auditor` → `supervisor`)
- **Trigger:** User provides explicit approval on the milestone plan.
- **Loop per Execution Group:**
  1. **Parallel Implementation:** Dispatch up to 4 concurrent `engineer` subagents for pending group tasks.
  2. **Audit Verification:** Dispatch `auditor` to run static checks, linters, and tests against acceptance criteria.
     - *On Failure:* Dispatch `engineer` (code failure) or `architect` (plan mismatch) to resolve defects.
     - *On Green:* Proceed to Git Protocol.
  3. **Git Commit Protocol:** Supervisor reviews `git diff --stat`, formats conventional commit message, asks for user confirmation, and runs `git commit` upon approval.

### Phase 5: Release & Tag Protocol (`supervisor`)
- **Trigger:** All milestones under active target release in `plans/00-ROADMAP.md` are marked "Completed".
- **Action:** Request user sign-off to finalize release, apply semantic git tag (`git tag -a vX.Y.Z`), and update `00-ROADMAP.md` to "Shipped".

---

## 4. Artifact & Directory Hierarchy

```
plans/
├── 00-ROADMAP.md                     # Single source of truth for project milestones & releases
├── research/
│   └── {topic}_context.md            # Initial Phase 0 technical context scans
└── active_milestones/
    └── {moniker}/                    # Isolated workspace per active milestone
        ├── context.md                # Phase 0 context report relocated for the milestone
        ├── spec.md                   # Phase 1 Gherkin PRD & business rules
        ├── visual-spec.html          # (Optional) Rendered visual specification
        ├── plan.md                   # Phase 2 tactical step-by-step execution plan
        ├── visual-plan.html          # (Optional) Rendered visual execution architecture
        └── audit.md                  # Phase 4 verification report
```

---

## 5. Non-Negotiable Guardrails

1. **Strict Human Gate:** No code modifications or test implementations may begin without explicit human approval at Phase 3.
2. **Single Source of Truth:** `plans/00-ROADMAP.md` and milestone files in `plans/active_milestones/` govern state. Always pass file paths to subagents, never oral chat summaries.
3. **Separation of Concerns:**
   - `supervisor`: State machine management, Phase 0 strategic research, dispatching, and Git commits only. Never writes code.
   - `product-owner`: Product requirements, Grill Loop, and roadmap only. Never designs architecture or edits code.
   - `architect`: Technical breakdown, data models, and execution grouping. Never edits source code.
   - `engineer`: TDD implementation strictly within assigned execution tasks. Never commits.
   - `auditor`: Independent verification against spec and test suites. Never fixes code directly.
4. **Git Commit Exclusivity:** ONLY the Supervisor may run `git commit`, and strictly following a green audit and user confirmation.

