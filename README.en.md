# Debate Direction

**Two agents propose, challenge and revise a direction before you commit to an ambiguous requirement.**

The proposer develops concrete options. The critic looks for material counterexamples, unsupported assumptions and violated constraints. The coordinator maintains an issue ledger, checks proposal versions and produces a deterministic report of key exchanges, unresolved issues and validation steps.

Consensus is not proof of correctness. Two roles using the same model can share blind spots. The tool supports a clearer next decision; it does not certify feasibility or eliminate deception.

[中文](README.md) · [Design](docs/design.md) · [Contributing](CONTRIBUTING.md) · [MIT](LICENSE)

## Try the offline example

Python 3.11+, with no third-party runtime dependencies:

```bash
PYTHONPATH=src python3 -m debate_direction --demo
```

Or install it in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
debate-direction --demo
```

The example is explicitly scripted, makes **zero model calls**, and does not accept arbitrary user questions. Open the generated `report.html`; Markdown and JSON reports are also saved.

## Native skill and standalone CLI

The native skill at [`skills/debate-direction`](skills/debate-direction) creates exactly two real subagents in a compatible host. It reuses their threads and requests no model/effort overrides when the host documents parent-session inheritance. It checks host capability, never guesses a hidden UI setting, and does not impersonate two agents in a single reply. Install the entire directory using your host's supported skill installation workflow.

Example invocation:

> Use $debate-direction. Have two agents debate how to improve our support-ticket dashboard within two weeks. Preserve current permissions. Return the core exchanges, recommended direction, remaining disagreements and validation steps.

The CLI creates two isolated role histories through an OpenAI Responses provider. Both roles receive the same immutable model and reasoning configuration. **It cannot read the ChatGPT model selector.** Explicit flags, caller-provided session JSON, or a complete environment-variable pair supply the configuration. Caller metadata is not authenticated proof of an external session's settings.

## Live model calls

The model and effort below are examples; replace them with the actual supported settings you want to preserve:

```bash
export OPENAI_API_KEY='your-api-key'
debate-direction 'Which changes should we pilot in our support dashboard?' \
  --model gpt-6-astra --reasoning-effort high \
  --context-file examples/context.txt
```

Or provide a JSON file containing exactly `model` and `reasoning_effort`:

```bash
debate-direction --question-file examples/question.txt \
  --session-config examples/session-config.example.json
```

Alternatively set both `DEBATE_MODEL` and `DEBATE_REASONING_EFFORT`. Partial sources are never silently mixed, and conflicting flags/session metadata are rejected. `.env.example` is documentation; the CLI does not automatically load dotenv files.

The native skill needs no separate API key. Live CLI runs require provider access. Unsupported settings, refusals, malformed output and incomplete responses fail visibly without model fallback or automatic retry.

## Protocol and reports

1. Run independent proposer and critic openings with no cross-role answer leakage.
2. Critic reviews the first proposal; this is review round one.
3. Proposer responds to every unresolved issue and creates a new version.
4. Critic reviews that exact version, including the entire historical issue ledger.
5. Stop on acceptance, missing input, stalled discussion, limits, cancellation or failure.

The default is at least two and at most four review rounds, with at most nine provider calls. A critic must explicitly accept an actual response to close an issue. Omission, unilateral claims and old-version acceptance cannot silently close it. A remaining critical/high issue blocks readiness. No third model rewrites the final decision.

Reports distinguish `status`, `stop_reason`, `decision` and `verification_status`. The CLI always uses `not_checked` for verification: it does not browse sources, execute code or run suggested tests. An issue marked `resolved` was addressed in the discussion, not empirically proven fixed.

Outputs:

- `report.html`: a script-free, self-contained, printable report.
- `report.md`: a readable account of the recommendation, exchanges and issues.
- `report.json`: full public records, versions, issue history, reported model identity and usage.

Reports include your question and context; review them before sharing. Hidden reasoning output is not included in debate records. Model text is escaped rather than executed as HTML.

## Limits and exit codes

Use `--max-rounds`, `--min-rounds`, `--stall-rounds`, `--max-output-tokens`, `--max-total-tokens`, `--timeout` and `--max-duration` to control the run. Reported token usage is checked after responses, so in-flight calls may exceed the threshold; this is not a precise spending cap. Output tokens include reasoning. Cancellation stops further calls, but already-sent requests may still be processed. Existing reports require explicit `--overwrite`.

`--json` writes the report to stdout; progress goes to stderr. `--quiet` suppresses progress.

Exit codes: `0` complete discussion, `1` configuration/input/filesystem error, `2` missing input or undetermined direction, `3` partial execution, `130` cancellation. Exit code zero does not certify that the recommendation is correct.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests use deterministic providers and transport mocks; they need no key and do not establish live-model quality. To integrate another host, implement `provider.complete(...) -> Completion`, preserving configuration, returning honest usage/model metadata and supporting two concurrent openings.

The first version includes a native skill, the Responses CLI, ledger and reports. Retrieval, executed verification, persisted resume and additional host adapters are future work, not implemented claims.

Official references: [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [reasoning](https://developers.openai.com/api/docs/guides/reasoning), [structured output](https://developers.openai.com/api/docs/guides/structured-outputs).
