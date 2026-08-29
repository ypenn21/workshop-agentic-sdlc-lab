what can i do to prevent Loss of Strict Behavioral Guardrails ???

  To systematically enforce strict behavioral guardrails and prevent prompt drift or shortcutting, the following mechanisms can be applied at the workspace and configuration levels:
  ──────
  ### 1. Workspace Hooks (Deterministic Pre-Tool Interception)

  Configure pre-tool hooks in hooks.json to programmatically validate calls before they execute.

  • Hook enforcement: Create a custom hook that intercepts calls to invoke_subagent.
  • Validation check: Verify that when TypeName: "self" is called with a custom role (e.g., Product Owner, Technical Architect, Plan Validator), the Prompt parameter contains the corresponding .
  agents/agents/{role}/agent.md header or full verbatim text.
  • Fail-closed: Reject the tool call with a validation error if the prompt is abbreviated or missing the static system definition.

  Example in .agents/hooks.json:

    {
      "hooks": {
        "pre_tool_call": [
          {
            "matcher": "invoke_subagent",
            "command": "python scripts/hooks/validate_subagent_injection.py"
          }
        ]
      }
    }
  ──────
  ### 2. Pre-Registered Custom Subagents in .agents/agents/

  Instead of relying on runtime prompt injection over TypeName: "self", ensure subagents are natively registered with their full definitions in .agents/agents/{name}/agent.md.

  • When subagents are natively exposed in the runtime catalog (as defined in subagents metadata), they run with their immutable system prompt baked in from disk.
  • Invoking TypeName: "architect" or TypeName: "product-owner" directly loads the static instructions without needing manual prompt stitching.
  ──────
  ### 3. Dedicated Slash Commands / Deterministic Workflow Scripts

  Encapsulate multi-agent lifecycle phases into single-command orchestration scripts or CLI workflows (e.g. python scripts/orchestrate.py --phase 1 --milestone ...).

  • Programmatic runners read the exact markdown files from disk (Path(".agents/agents/architect/agent.md").read_text()), append the task payload, and invoke the SDK or API without human or model intervention in
  the prompt assembly.
  ──────
  ### 4. Behavioral Rule Reinforcement in .agents/rules/

  Add a Zero-Tolerance Constraint in behavior.md:

    }
  ──────
  ### 2. Pre-Registered Custom Subagents in .agents/agents/

  Instead of relying on runtime prompt injection over TypeName: "self", ensure subagents are natively registered with their full definitions in .agents/agents/{name}/agent.md.

  • When subagents are natively exposed in the runtime catalog (as defined in subagents metadata), they run with their immutable system prompt baked in from disk.
  • Invoking TypeName: "architect" or TypeName: "product-owner" directly loads the static instructions without needing manual prompt stitching.
  ──────
  ### 3. Dedicated Slash Commands / Deterministic Workflow Scripts

  Encapsulate multi-agent lifecycle phases into single-command orchestration scripts or CLI workflows (e.g. python scripts/orchestrate.py --phase 1 --milestone ...).

  • Programmatic runners read the exact markdown files from disk (Path(".agents/agents/architect/agent.md").read_text()), append the task payload, and invoke the SDK or API without human or model intervention in
  the prompt assembly.
  ──────
  ### 4. Behavioral Rule Reinforcement in .agents/rules/

  Add a Zero-Tolerance Constraint in behavior.md:

  │ MANDATORY PROMPT INJECTION AUDIT:
  │ Under no circumstances may invoke_subagent be called with an ad-hoc or summarized prompt when a role has an associated .agents/agents/{role}/agent.md file. The tool call MUST be preceded by a view_file call
  │ on that exact file, and the entire file text MUST be injected verbatim as the base prompt. Any deviation is considered an immediate execution failure.