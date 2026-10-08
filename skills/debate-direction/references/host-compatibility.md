# Host compatibility

Read the current tool definitions first. The following routing guidance does not imply that a tool exists on every host. Do not call undocumented parameters.

## Native collaboration hosts

When `collaboration.spawn_agent` exists, use it to create two child agents. When `followup_task` exists, use it to resume an original agent that has completed a turn. Use `send_message` to add information to an agent that is still running. Observe completion through `list_agents`, `wait_agent`, or the host's equivalent capabilities; do not infer completion from elapsed time. On cancellation, use the current API's interrupt or close capability and preserve the valid record accumulated so far.

| Check | Required handling |
| --- | --- |
| Model and reasoning effort | Omit all explicit overrides and use the host's documented parent-conversation inheritance. If tools cannot read the actual values, record `unknown`; do not infer them from a product name, an impression of the interface, or the system date. |
| Custom role configuration | Check agent-type overrides only where the current tools and readable configuration explicitly support this. Prefer a default agent without overrides. Do not read credentials or unrelated user configuration. |
| `fork_turns="none"` | Select this only when the tool documentation confirms that it also inherits the parent's model and reasoning effort. Otherwise use a mode with a documented inheritance guarantee. |
| Full-history inheritance | First create two roles that only acknowledge readiness, then issue `start_opening` through their original IDs. If the host supports submitting isolated tasks together, both may be submitted at once. Supply the same shared brief and instruct agents to use only its task facts. Report the limitations of shared context and correlated errors from the same model; do not claim statistical independence. |
| Fewer than two available slots | Wait through the host's normal scheduling or explain the block. Do not interrupt the user's other tasks to free slots. If two real openings cannot be completed, stop with `unsupported`, or `provider_error` after a partial launch. |
| Later rounds | Reuse the two real IDs from this run. Do not replace a lost agent with a new one and claim role continuity. If the original agent cannot be resumed, stop with `provider_error` and report the incomplete run. |
| Conversation settings cannot be read | When documentation explicitly guarantees inheritance, proceed with `documented_inheritance`. When neither verification nor a documented guarantee is available, record `unverified`, stop with `unsupported`, and offer concrete host-configuration steps. |
| Inheritance is known to be unavailable | Stop with `unsupported`. If the user later explicitly permits different settings, start a separate run under the revised requirement and disclose the configuration change. |

### Creation examples

Use these call shapes only when the current `spawn_agent` documentation explicitly guarantees that full-history mode inherits the parent's model and reasoning effort. Omit `model` and `reasoning_effort` in both calls. Prepare both roles before opening the debate so the first agent cannot finish a substantive opening early and contaminate the second agent's inherited context.

```json
{
  "task_name": "debate_pro_<run_id>",
  "fork_turns": "all",
  "message": "phase: prepare. You are the fixed PRO agent for this run. Reply only with ready and wait for start_opening. Do not propose a solution or position yet. Do not read other agents' output from this run or create other agents. In later turns, use only the shared task brief below, and provide public conclusions with concise reasons, without private chain-of-thought. <shared task brief>"
}
```

```json
{
  "task_name": "debate_con_<run_id>",
  "fork_turns": "all",
  "message": "phase: prepare. You are the fixed CON agent for this run. Reply only with ready and wait for start_opening. Do not propose risks or a position yet. Do not read other agents' output from this run or create other agents. In later turns, use only the shared task brief below, and provide public conclusions with concise reasons, without private chain-of-thought. <the same shared task brief>"
}
```

Normalize `run_id` to task-name characters permitted by the current host, such as lowercase letters, digits, and underscores. Capture the actual agent IDs returned by the tools; a `task_name` is not proof of successful creation. Replace all placeholders with the actual run information.

Once both agents are ready, use the host's supported resumption capability on the original IDs to send `start_opening` and each role's opening requirements from SKILL.md. The second opening instruction must not include the first agent's substantive output. If an agent violates the preparation requirement by producing a position early, and that output enters the opponent's inherited context, do not claim a blind opening. Repair the situation only through context isolation the host actually supports. Otherwise stop with `invalid_response`; never secretly create a third agent.

## Other hosts

When a host exposes real child-agent APIs under other names, map creation, resumption, waiting, and cancellation to its documented calls while preserving the role count, configuration inheritance, and ledger semantics.

Native mode is unavailable when the host provides only ordinary single-model text generation, labels text as multiple roles without creating agents, or permits prompt editing but no child-agent creation. Clearly report the capability gap without inventing a two-agent process. Do not silently switch to API mode, request a key, or introduce a paid service. A separately configured API mode must accurately disclose its settings and must not claim to read the current chat interface's model selection automatically.

Treat configuration consistency as an auditable constraint, not a cross-platform guarantee. Report the host's actual capabilities and evidence, and provide concrete steps to address limitations.
