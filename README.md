# Debate Direction

**Two agents propose, challenge and revise a direction before you commit to an ambiguous requirement.**

The proposer develops concrete options. The critic looks for material counterexamples, unsupported assumptions and violated constraints. The coordinator maintains an issue ledger, checks proposal versions and produces a deterministic report of key exchanges, unresolved issues and validation steps.

Consensus is not proof of correctness. Two roles using the same model can share blind spots. The tool supports a clearer next decision; it does not certify feasibility or eliminate deception.

[Simplified Chinese](README.zh-CN.md) · [Design](docs/design.md) · [Validation](docs/validation.md) · [Native example](docs/native-example.md) · [MIT](LICENSE)

## What it does

- Turns a vague request into a goal, constraints, candidate options and acceptance criteria.
- Starts the two roles independently before exchanging their public arguments.
- Tracks every objection across proposal versions, including previously resolved issues.
- Separates convergence, disagreement, missing information, stalled discussion and execution failures.
- Produces Markdown, JSON and self-contained HTML decision reports.
- Includes a fixed offline example that needs no API key.

Project documentation, skill metadata, CLI messages, report labels and bundled examples are written in English. Debate responses default to English unless the user explicitly requests another language. User-supplied questions and context are preserved. A complete Chinese README is available through the link above.

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

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`. Without installing, set `$env:PYTHONPATH = "src"` before running `python -m debate_direction --demo`.

The example is explicitly scripted, makes **zero model calls**, and does not accept arbitrary user questions. Open the generated `report.html`; Markdown and JSON reports are also saved.

The scripted exchange starts with a search rewrite and AI recommendations. The critic questions the missing bottleneck evidence, two-week scope and permission boundaries. The proposer switches to a measured, reversible pilot of combined filters and personal views, with permission checks and rollback conditions. The critic accepts that direction for validation; no production measurements or tests are claimed to have passed.

## Native skill and standalone CLI

| | Native session skill | Standalone CLI |
| --- | --- | --- |
| Entry point | A ChatGPT Work / Codex host with real subagents | Python 3.11+ |
| Two roles | Two persistent native subagent threads | Two isolated role histories with live model calls |
| Model and reasoning effort | Documented parent-session inheritance, without overrides | An explicit, shared configuration |
| Separate API key | Not required | `OPENAI_API_KEY` for live calls |
| Evidence tools | Those actually available and authorized in the host | No automatic browsing or test execution |

The native skill at [`skills/debate-direction`](skills/debate-direction) creates exactly two real subagents in a compatible host. It reuses their threads and requests no model/effort overrides when the host documents parent-session inheritance. It checks host capability, never guesses a hidden UI setting, and does not impersonate two agents in a single reply. Install the entire directory using your host's supported skill installation workflow.

Example invocation:

> Use $debate-direction. Have two agents debate how to improve our support-ticket dashboard within two weeks. Preserve current permissions. Return the core exchanges, recommended direction, remaining disagreements and validation steps.

The skill defaults to two to four review rounds and keeps using the same agents. If the host cannot create two real subagents or guarantee model/effort inheritance, it reports that limitation. A request such as "Find feasible changes" without a subject or supporting context first needs the object and desired improvement clarified.

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

```json
{
  "model": "gpt-6-astra",
  "reasoning_effort": "high"
}
```

```bash
debate-direction --question-file examples/question.txt \
  --context-file examples/context.txt \
  --session-config examples/session-config.example.json
```

Alternatively set both `DEBATE_MODEL` and `DEBATE_REASONING_EFFORT`. Partial sources are never silently mixed, and conflicting flags/session metadata are rejected. `.env.example` is documentation; the CLI does not automatically load dotenv files.

Supply the API key through the environment; do not put it in questions, session configuration files or the repository.

The native skill needs no separate API key. Live CLI runs require provider access. Unsupported settings, refusals, malformed output and incomplete responses fail visibly without model fallback or automatic retry.

## Protocol and reports

1. Run independent proposer and critic openings with no cross-role answer leakage.
2. Critic reviews the first proposal; this is review round one.
3. Proposer responds to every unresolved issue and creates a new version.
4. Critic reviews that exact version, including the entire historical issue ledger.
5. Stop on acceptance, missing input, stalled discussion, limits, cancellation or failure.

The default is at least two and at most four review rounds, with at most nine provider calls. A critic must explicitly accept an actual response to close an issue. Omission, unilateral claims and old-version acceptance cannot silently close it. A remaining critical/high issue blocks readiness. No third model rewrites the final decision.

Reports distinguish `status`, `stop_reason`, `decision` and `verification_status`. The CLI always uses `not_checked` for verification: it does not browse sources, execute code or run suggested tests. An issue marked `resolved` was addressed in the discussion, not empirically proven fixed.

| Decision | Meaning |
| --- | --- |
| `ready_to_validate` | Both roles accept the current direction for real-world validation |
| `conditional` | A conditional recommendation with retained risks or qualifications |
| `blocked` | Material unresolved issues prevent readiness |
| `needs_clarification` | Missing information could change the decision |
| `undetermined` | The execution or public record is insufficient for a complete conclusion |

Outputs:

- `report.html`: a script-free, self-contained, printable report.
- `report.md`: a readable account of the recommendation, exchanges and issues.
- `report.json`: full public records, versions, issue history, reported model identity and usage.

Reports include your question and context; review them before sharing. Hidden reasoning output is not included in debate records. Model text is escaped rather than executed as HTML.

## Limits and exit codes

```bash
debate-direction 'Your question' \
  --model gpt-6-astra --reasoning-effort high \
  --min-rounds 2 --max-rounds 4 \
  --max-output-tokens 12000 \
  --max-total-tokens 150000 \
  --timeout 180 --max-duration 900 \
  --out runs/my-review
```

Use `--max-rounds`, `--min-rounds`, `--stall-rounds`, `--max-output-tokens`, `--max-total-tokens`, `--timeout` and `--max-duration` to control the run. Reported token usage is checked after responses, so in-flight calls may exceed the threshold; this is not a precise spending cap. Output tokens include reasoning. Cancellation stops further calls, but already-sent requests may still be processed. Existing reports require explicit `--overwrite`.

After the duration threshold, no new calls start; in-flight requests remain subject to their individual timeout. A truncated response is incomplete, not acceptance. Higher reasoning effort may require a larger output-token limit. Failed requests may have unreported usage.

`--json` writes the report to stdout; progress goes to stderr. `--quiet` suppresses progress.

Exit codes: `0` complete discussion, `1` configuration/input/filesystem error, `2` missing input or undetermined direction, `3` partial execution, `130` cancellation. Exit code zero does not certify that the recommendation is correct.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests use deterministic providers and transport mocks; they need no key and do not establish live-model quality. To integrate another host, implement `provider.complete(...) -> Completion`, preserving configuration, returning honest usage/model metadata and supporting two concurrent openings.

The tests cover configuration consistency, isolated CLI openings, issue retention, outdated proposal acceptance, errors and truncation, cancellation, usage thresholds, report escaping and overwrite protection. See the [validation record](docs/validation.md) for the completed native exercise and the remaining validation limits. Native skill behavior must be exercised in a compatible host.

Contribution and reporting instructions are in [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Scope and next steps

The first version includes a native skill, the Responses CLI, ledger and reports. Retrieval, executed verification, persisted resume and additional host adapters are future work, not implemented claims.

The tool does not automatically implement recommendations, provide a hosted web service or authenticate another application's session settings.

## Official references

Official references: [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [reasoning](https://developers.openai.com/api/docs/guides/reasoning), [structured output](https://developers.openai.com/api/docs/guides/structured-outputs).

## License

[MIT](LICENSE). Contributions and adaptations are welcome.
