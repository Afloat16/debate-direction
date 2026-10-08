# Host compatibility

## Contents

- [Installation and invocation](#installation-and-invocation)
- [Required runtime checks](#required-runtime-checks)
- [Hosted collaboration tools](#hosted-collaboration-tools)
- [Codex CLI](#codex-cli)
- [Claude Code](#claude-code)
- [Kimi Code CLI](#kimi-code-cli)
- [DeepSeek and other model providers](#deepseek-and-other-model-providers)
- [Operating systems and validation limits](#operating-systems-and-validation-limits)

Official documentation was reviewed on **2026-10-08**. Read the installed host's current tool definitions before acting. A documented route is conditional on those capabilities and the active configuration; it is not evidence that this project executed a native run on that host. Do not call undocumented parameters or relax the debate protocol to make an installation appear supported.

## Installation and invocation

Each destination below contains the complete `debate-direction/` directory, including `SKILL.md` and its references. The portable frontmatter contains `name` and `description`. Keep the coordinator in the main conversation; do not add fixed `model`, `effort`, or `context: fork` frontmatter to this shared skill. `agents/openai.yaml` is optional OpenAI UI metadata, not a portable subagent definition.

| Local host | Personal skill directory | Project skill directory | Invocation |
| --- | --- | --- | --- |
| Codex CLI | `~/.agents/skills/debate-direction/` | `.agents/skills/debate-direction/` | `$debate-direction`, or select it with `/skills` |
| Claude Code | `~/.claude/skills/debate-direction/` | `.claude/skills/debate-direction/` | `/debate-direction` |
| Current Kimi Code CLI | `$KIMI_CODE_HOME/skills/debate-direction/`; defaults to `~/.kimi-code/skills/debate-direction/` | `.kimi-code/skills/debate-direction/` | `/skill:debate-direction` |

Sources: [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), and [Kimi Code skills](https://moonshotai.github.io/kimi-code/en/customization/skills). Kimi Code also discovers `~/.agents/skills/` and project `.agents/skills/`; its generic personal directory remains under the OS home even when `KIMI_CODE_HOME` changes. Avoid installing duplicate copies unnecessarily.

Older Python `kimi-cli` documentation describes different roots, including `~/.kimi/skills/`. Use an explicit custom destination for such installations and verify that version's agent capabilities separately. The current Kimi Code route below does not certify a legacy version. See the [legacy skill documentation](https://moonshotai.github.io/kimi-cli/en/customization/skills.html).

Installing files makes the workflow discoverable. It does not authenticate a host, enable child agents, verify model inheritance, or start a debate. Do not alter global model defaults, credentials, permissions, agent-team settings, or the user's other installed skills as part of a debate.

## Required runtime checks

| Check | Required handling |
| --- | --- |
| Two persistent child agents | Require real creation results and two distinct agent IDs that can be resumed. A task label, a background job ID alone, or two sections of one generated response is insufficient. Reuse the same pair throughout the run; forbid further delegation and never add a third judge. |
| Model and reasoning effort | Require applicable documented inheritance of both settings or trustworthy runtime evidence that both match the initiating conversation. Omit fixed overrides; use an advertised inherit-only selector when the host requires one. Check relevant subagent defaults and type-specific settings without reading credentials or unrelated configuration. |
| Evidence quality | Record `runtime_verified` only for values actually verified. Use `documented_inheritance` for an applicable documented guarantee and `unknown` for unreadable values. A skill path or successful installation proves neither. If neither verification nor an applicable guarantee is available, use `unverified` and stop with `unsupported`. |
| Changing configuration | Retain the initial configuration evidence. Recheck any reported substitution, fallback, clamping, or setting change. Stop with `unsupported` if identical model and effort can no longer be established; preserve completed scope and report the mismatch. Do not silently switch both agents to a new model. |
| Blind openings | Create both agents before consuming either substantive opening. Prefer preparation acknowledgments followed by `start_opening` on the original IDs. A host may submit two isolated openings together. Never forward one opening into the other agent's starting context. |
| Insufficient slots | Use normal host scheduling or report the block. Do not interrupt the user's other work to free capacity. If no valid pair can be created, stop with `unsupported`; a failed partial launch is `provider_error`. |
| Lost continuity | If an original agent cannot be resumed, stop with `provider_error` and report the incomplete run. A replacement with the same role name is still a new agent. |
| Waiting and cancellation | Use documented completion, follow-up, and interrupt tools. Do not infer completion from elapsed time. Apply actual user or host limits, preserve the ledger, and never count preparation or repair as review rounds. |

Do not treat equally named effort levels across different providers as equal reasoning budgets. A Boolean thinking toggle is not proof of a particular effort level. Where a provider maps a requested setting to an effective setting, record that distinction in configuration evidence. Do not invent unreadable values.

## Hosted collaboration tools

This route applies only where the actual `collaboration` tool definitions provide the described capabilities. When `spawn_agent` exists, use it for creation. Use `followup_task` to resume an original agent that completed a turn, and `send_message` to add information to one still running. Observe completion through `list_agents`, `wait_agent`, or documented equivalents. On cancellation, use the available interrupt or close capability.

When the current tool contract explicitly guarantees that full-history forks inherit the parent's model and reasoning effort, omit both overrides and use `fork_turns: "all"`. Do not assume a fresh-context mode also preserves those settings. Select `fork_turns: "none"` only when its current contract establishes the same inheritance.

### Preparation examples

These examples apply only to the advertised collaboration API and its full-history inheritance guarantee. Replace all placeholders and normalize task names to characters the host accepts. Capture actual returned agent IDs; names alone are not proof of creation.

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

After both creations succeed, resume each original ID with `start_opening` and its role task. The second instruction must not contain the first opening. If an early substantive response contaminates the other agent's inherited context, repair only through isolation the host actually supports; otherwise stop with `invalid_response`. Never create a third agent to conceal the defect. Shared context and a shared model can still produce correlated errors; do not claim statistical independence.

## Codex CLI

Use Codex's available native subagent creation and follow-up tools, keeping two original IDs. Its [subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents) supports parent inheritance, but omission alone is insufficient: explicit spawn settings and `[agents]` defaults precede the parent, and custom agent files can override the resolved model or effort. A model chosen without an effort can also select that model's default effort.

Before starting, establish that applicable `default_subagent_model`, `default_subagent_reasoning_effort`, and agent-type overrides preserve the initiating pair. Prefer the default type without overrides. Custom definitions may exist under `~/.codex/agents/` or project `.codex/agents/`; their presence does not certify inheritance. Read only relevant nonsecret settings when permitted. If conflicting defaults cannot be ruled out and runtime metadata does not prove equality, stop with `unsupported` instead of guessing or modifying the configuration. Check that the current session can keep two child agents available, and use the preparation barrier when context is forked.

## Claude Code

Use the currently advertised `Agent` tool. When available, the `fork` subagent type inherits the main conversation's context and model; use preparation acknowledgments to preserve blind openings. Otherwise, use a resumable general-purpose or custom type only after checking inheritance. Built-in Explore and Plan agents are one-shot and cannot implement this protocol. Resume original agent IDs through the documented `SendMessage` mechanism, rather than starting another `Agent` call under the same name. See [Claude Code subagents](https://code.claude.com/docs/en/sub-agents).

Check model selection from the invocation, definition, environment, and installed overrides. An explicit custom definition's `model: inherit` can select the parent model on versions that document it; it is not independently proof of effort inheritance. Subagent effort can override session effort, and older releases differ in thinking inheritance and resumption behavior. Do not use fixed custom profiles to approximate the current session. Require the installed version's applicable guarantee for both settings.

The [model configuration documentation](https://code.claude.com/docs/en/model-config) describes effort limits and model fallback. A fallback can change a subagent while leaving the main session unchanged. Watch available runtime metadata and notices; stop if the required identity no longer holds. Do not disable host protections or silently rewrite fallback policies.

[Agent teams](https://code.claude.com/docs/en/agent-teams) are experimental and unnecessary for ordinary resumable subagents. This skill does not enable them. If already enabled, inspect the actual behavior and require exactly two persistent role agents with the same configuration; do not assume that a named teammate is equivalent to a resumable subagent.

## Kimi Code CLI

Use the current `Agent` tool with a suitable persistent type, such as the built-in `coder`, and prohibit delegation in both role tasks. Capture the returned agent ID separately from any background task ID. Continue with `resume: <agent_id>`; the [tool reference](https://moonshotai.github.io/kimi-code/en/reference/tools) makes `resume` mutually exclusive with `subagent_type` and retains the existing model on resume. Supply the shared task facts explicitly because ordinary subagents have their own context. See [Kimi Code agents](https://moonshotai.github.io/kimi-code/en/customization/agents).

The [secondary-model configuration](https://moonshotai.github.io/kimi-code/en/configuration/config-files.html#secondary-model) determines the inheritance route:

- When the current tool advertises `model`, select `model: "primary"` for each initial creation. This is a documented selector for the caller's model **and effort**, not permission to choose a different model.
- If `model` is absent, distinguish an unconfigured pool from a forced model. With `secondary_model.force=true`, the tool hides the parameter and rejects `primary`; omission can therefore select another model. Proceed only when the active configuration and applicable documentation or runtime evidence establish both settings. Otherwise stop with `unsupported`.
- Do not select a pool alias as a substitute for `primary`: pool entries can bind their own effort. The section's `default_effort` and model-specific supported efforts also require attention; an unsupported effort can fall back to a different effective value.

Leave secondary-model configuration unchanged. Use preparation and the same two original IDs through all rounds. A legacy CLI installation or an advertised thinking toggle alone does not establish these current capabilities.

## DeepSeek and other model providers

A provider name is not a native agent host. DeepSeek documents [integration with Claude Code](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/); in that setup, install this skill for Claude Code and apply the Claude host checks. A Kimi model served through another host likewise follows that host's tools and skill paths. A plain model API does not supply the native persistence and orchestration required here.

DeepSeek's [Anthropic-compatible API](https://api-docs.deepseek.com/guides/anthropic_api/) maps some model names and ignores thinking token budgets. Its [thinking documentation](https://api-docs.deepseek.com/guides/thinking_mode/) distinguishes requested and mapped effort. Do not claim the selected UI label directly proves the actual model or reasoning budget. Where the initiating conversation already uses a documented provider mapping, retain its evidence and verify the same effective settings for both agents.

If a host only supports ordinary text generation or lacks the required inheritance evidence, report native mode as `unsupported`. Do not impersonate two agents, silently switch to API mode, request a key, or introduce another paid service. A separately requested API run needs explicit settings and must not claim it automatically reads another chat application's model selection.

## Operating systems and validation limits

The skill consists of portable text files. Resolve personal paths in the home directory of the environment that runs the host. Native Windows and WSL can have different homes and installed tools; copying into one does not install into the other. A custom destination changes discovery only, not runtime capabilities.

Host installation and platform prerequisites remain separate. Consult the official [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), [Claude Code setup](https://code.claude.com/docs/en/setup), and [Kimi Code getting started](https://moonshotai.github.io/kimi-code/en/guides/getting-started) pages. In particular, current Kimi Code on Windows requires Git for Windows for its Git Bash shell. Do not describe a file-copy check as a native Windows, macOS, or Linux debate test.

Report the host and evidence actually used in each run. Documentation review, installation success, scripted demos, and a successful exercise on another host do not prove native execution or configuration fidelity on this one.
