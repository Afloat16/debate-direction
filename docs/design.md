# Debate Direction protocol and design decisions

## Goal

Turn an ambiguous requirement into a reviewable candidate direction, material objections, and validation steps. Two agents broaden the review, expose assumptions, and track revisions; they do not prove that the conclusion is correct.

## Two execution paths

| Path | How the agents run | Model and reasoning-effort source | Intended use |
| --- | --- | --- | --- |
| Native skill | The host creates two actual subagents and continues their existing threads through the debate | Documented parent-session inheritance supported by the host; no unrequested model override | Direct requests in compatible ChatGPT Work / Codex environments |
| Python CLI | Two separate role histories handled by one Responses provider | Explicit arguments, caller-supplied JSON, or a complete environment-variable pair | Scripts, application integrations, and repeatable tests |

The paths share protocol semantics while retaining their actual permissions and execution environments. In the CLI, `session_config` contains caller-supplied settings; it does not authenticate their origin. The model can share training biases across roles. Here, "independent" describes role contexts and blind openings, not statistical independence.

## CLI state transitions

1. Validate the single immutable configuration, input length, and budget.
2. Run the proposer's initial proposal and the critic's blind risk scan concurrently. Neither opening receives the other role's answer.
3. Send the opening proposal to the critic for review round one.
4. Have the proposer respond to every accumulated unresolved issue and submit a new version; have the critic review that exact version.
5. Stop on convergence, essential missing information, stalled discussion, round/usage/time limits, or errors.
6. Generate the result and report with deterministic code, without adding another model that can freely rewrite the conclusion.

The default is at least two and at most four review rounds. The CLI permits at most `2 × max_rounds + 1` provider calls, or nine with the default settings. The two blind opening calls run concurrently; dependent exchanges run sequentially. The independent risk scan does not count as a proposal review.

## Issue ledger

Each issue records a stable ID, severity, target, description, resolution criterion, status, and history. The proposer can respond with `fix`, `rebut`, `accept_risk`, or `request_clarification`, but cannot change an issue's severity or close it unilaterally. The critic must evaluate the corresponding ID and provide a reason. An existing issue is not deleted merely because a later response omits it.

`resolved` means an objection was addressed in the discussion, not that it passed an actual test. `accepted_risk` remains a risk and must be presented with its conditions; renaming a material risk cannot make it disappear. The final proposal must indicate whether the critic reviewed it. Acceptance of an older version cannot be transferred to a newer version.

## Separate the decision from validation

| Field | Meaning |
| --- | --- |
| `status` | Completed, partially completed, or awaiting essential information |
| `stop_reason` | The actual reason for stopping; exhausting the round limit does not imply convergence |
| `decision` | `ready_to_validate` / `conditional` / `blocked` / `needs_clarification` / `undetermined` |
| `verification_status` | Always `not_checked` in the CLI, which does not retrieve evidence or execute tests |
| `model_identity` | The requested model and the model reported by the provider, so a requested setting is not presented as an observed execution result |
| `usage` | Reported tokens, actual provider call count, call limit, and whether the usage threshold was exceeded |

A request such as "Find a feasible modification" without an object to modify should produce the missing information and follow-up questions, not an invented product. When the object is known, discussion can continue with explicitly labeled assumptions, and the recommended direction still requires the corresponding validation.

## Usage, time, and failures

`max_total_tokens` is a stopping threshold for usage already reported by the provider, not a precise spending cap. Concurrent openings or in-flight calls can exceed it. Additional usage is unknown when a failed call returns no usage metadata. `max_output_tokens` includes internal reasoning tokens; a high-effort call may exhaust that allowance before returning a complete public answer, requiring the caller to adjust the limit.

The CLI does not retry automatically, silently switch models, reduce reasoning effort, or remove unsupported parameters. Each request has a timeout. Once the total duration reaches its threshold, no further calls start; in-flight requests remain subject to their individual timeouts. Cancellation or failure preserves completed work where possible and cannot turn one role's output into a completed two-agent conclusion.

## Evidence boundaries

A model saying "I tested it," asserting "research shows," or generating a URL is not tool-based verification. CLI proposals, conditions, and validation steps come from generated text and user-supplied material; the CLI does not read webpages, execute tests, or perform external actions. The native skill can read material within the host's available permissions and must identify the evidence actually obtained. Agreement between the roles cannot change the evidence status.

## References

- [OpenAI: subagents and model inheritance](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [OpenAI: Responses API reasoning parameters](https://developers.openai.com/api/docs/guides/reasoning)
- [OpenAI: structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

These interfaces and host capabilities evolve. Callers should use the versions and permissions actually available to them. The project does not hard-code a particular "latest model."
