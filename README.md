# Debate Direction

**Two agents propose, challenge and revise a direction before you commit to an ambiguous requirement.**

Give it a question and the relevant context. The proposer develops options; the critic finds material flaws. They revise the same proposal over several rounds, while a coordinator keeps an issue ledger and returns the core exchanges, the current recommendation, remaining disagreements and validation steps.

Consensus is not proof of correctness. Two roles using the same model can share blind spots. The result is a direction to validate, with its assumptions still visible.

[Simplified Chinese](README.zh-CN.md) · [Installation guide](docs/installation.md) · [Providers](docs/providers.md) · [Host compatibility](skills/debate-direction/references/host-compatibility.md) · [Validation](docs/validation.md) · [MIT](LICENSE)

## Install with one command

### macOS and Linux

```sh
curl -fsSL https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh
```

### Windows PowerShell

```powershell
& ([scriptblock]::Create((Invoke-RestMethod https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.ps1)))
```

The installer creates a per-user environment and obtains Python automatically through [uv](https://docs.astral.sh/uv/). You do not need to install Python or Git first. Initial installation needs internet access and a platform supported by uv's managed Python distributions. On Linux, the download command needs `curl`; the [installation guide](docs/installation.md) also covers alternatives, existing Python, WSL, updates and removal.

Use the exact executable path printed by the installer immediately. If `debate-direction` is not on your PATH, use its printed command to add the directory to your current terminal; add that directory to your user PATH for future terminals. Installation does not edit shell profiles or require administrator privileges.

Try the fixed offline example:

```sh
debate-direction --demo
```

Open the generated `report.html`. The demo makes **zero model calls** and shows a proposal changing after criticism. It uses a fixed example and does not analyze custom questions.

## Use it inside Codex, Claude Code or Kimi Code

Install the CLI and a native skill together by selecting your host:

```sh
curl -fsSL https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh -s -- --host codex
```

```powershell
& ([scriptblock]::Create((Invoke-RestMethod https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.ps1))) -Host claude
```

Choose `codex`, `claude`, `kimi`, or `all`. If the CLI is already installed:

```sh
debate-direction install-skill --host codex
debate-direction install-skill --host claude
debate-direction install-skill --host kimi
```

| Host | Default personal skill directory | Invoke in the host |
| --- | --- | --- |
| Codex | `~/.agents/skills/debate-direction` | `$debate-direction` |
| Claude Code | `~/.claude/skills/debate-direction` | `/debate-direction` |
| Current Kimi Code | `~/.kimi-code/skills/debate-direction`, or `$KIMI_CODE_HOME/skills/debate-direction` | `/skill:debate-direction` |

Refresh the host's skill list or open a new session after installation. For example, in Codex:

```text
$debate-direction
Find feasible changes to our support dashboard within two weeks.
Preserve existing permissions. Return the core exchanges, recommended
direction, unresolved issues and validation steps.
```

**Native mode is the route for preserving the initiating conversation's model and reasoning effort.** It creates exactly two persistent child agents and continues the same pair. It requires applicable inheritance guarantees or runtime evidence for both settings. Conflicting subagent defaults, model fallback or unavailable resumable agents produce an explicit limitation. It does not infer hidden UI values or write fixed model overrides.

The installer copies the skill; it does not install or authenticate Codex, Claude Code or Kimi Code. Native debates reuse the host's existing authentication. [Host compatibility](skills/debate-direction/references/host-compatibility.md) documents each host's requirements and current official sources. A plain chat interface without real subagent tools cannot run native mode.

Use `--project` for the current project, `--project PATH` for another project, or `--skills-dir PATH` for a custom or legacy skills root. Unchanged installations are a no-op. Modified skills are preserved unless `--force` is explicit; replacements keep a backup outside the scanned skills directory. Installation leaves host model settings unchanged.

## Use DeepSeek, Kimi, Claude, OpenAI or Gemini through the CLI

The standalone CLI supports six provider presets. Both agents use the same immutable provider, model and reasoning configuration. **The CLI cannot read another application's model selector.** Configure it explicitly once, or pass settings per run.

| Preset | API | API key environment variable |
| --- | --- | --- |
| `openai` | OpenAI Responses | `OPENAI_API_KEY` |
| `anthropic` | Anthropic Messages | `ANTHROPIC_API_KEY` |
| `deepseek` | DeepSeek Chat Completions | `DEEPSEEK_API_KEY` |
| `kimi` | Moonshot/Kimi Chat Completions | `MOONSHOT_API_KEY` |
| `gemini` | Gemini's OpenAI-compatible endpoint | `GEMINI_API_KEY` |
| `openai-compatible` | An explicitly selected compatible HTTPS endpoint | `OPENAI_COMPATIBLE_API_KEY` |

A provider is distinct from a host: DeepSeek used inside Claude Code follows the Claude skill installation path. The CLI's DeepSeek preset connects directly to the DeepSeek API.

### Configure once

Run the guided setup:

```sh
debate-direction setup
```

Or supply a complete configuration, for example:

```sh
debate-direction setup --provider deepseek --model deepseek-flash --reasoning-effort high
```

Set the API key in the current terminal. macOS/Linux:

```sh
export DEEPSEEK_API_KEY='your-api-key'
```

Windows PowerShell:

```powershell
$env:DEEPSEEK_API_KEY = 'your-api-key'
```

Then ask questions without repeating the settings:

```sh
debate-direction "Which changes should we pilot in our support dashboard?"
```

Setup saves only non-secret settings. It never asks for or stores your key. Use your normal environment or secret manager for credentials; `.env.example` is documentation and is not automatically loaded. See [provider configuration](docs/providers.md) for every preset, model-specific reasoning controls, regional endpoints and custom key-variable names.

### Explicit settings or caller metadata

```sh
debate-direction "Which direction should we validate first?" --provider kimi --model kimi-k3 --reasoning-effort high
```

For a larger brief:

```sh
debate-direction --question-file examples/question.txt --context-file examples/context.txt --provider openai --session-config examples/session-config.example.json
```

Session JSON contains exactly `model` and `reasoning_effort`. It is caller-supplied configuration, not authenticated evidence of another chat session. Alternatively supply the complete pair `DEBATE_MODEL` and `DEBATE_REASONING_EFFORT`, with `DEBATE_PROVIDER` if needed.

Explicit configuration takes precedence over automatic profile loading. A newly selected provider never silently reuses another provider's saved model. An explicit `--config PATH` must agree with any accompanying settings. Partial model/effort sources and conflicting pairs are rejected.

### Reasoning settings are model-specific

`high` is not a universal token budget. For example, current DeepSeek models expose `none`, `low`, `high`, and `max`; Kimi K3 exposes `low`, `high`, and `max`; some Kimi models expose only an enabled/disabled thinking control. The adapters validate supported controls and do not translate an unsupported label into a supposedly equivalent one.

For a custom endpoint, `provider_default` explicitly omits an effort parameter and makes no promise of exact effort control. Literal effort pass-through requires the caller to verify that endpoint's semantics. Returned model identities are recorded; model drift stops the run. Provider-side hidden configuration cannot be independently attested by this CLI.

## Helpful commands

```sh
debate-direction providers
debate-direction doctor
debate-direction install-skill --host all --dry-run
debate-direction --help
```

`doctor` checks the local installation, saved profile, credential presence and skill locations. It prints no key values and makes no model calls. It does not certify native inheritance or live API access. Listing providers, diagnostics and skill installation support `--json` for machine-readable output.

## How the debate works

1. Run independent proposer and critic openings with separate public histories.
2. Have the critic review the first proposal; this is review round one.
3. Have the proposer respond to unresolved objections and create a new version.
4. Have the critic review that exact version and every historical issue, including previously resolved ones.
5. Stop on convergence, essential missing input, stalled discussion, limits, cancellation or failure.

The default is at least two and at most four review rounds, with at most nine provider calls. Only the critic can accept an actual response and resolve an objection. Omission and old-version acceptance cannot close an issue. A remaining critical/high issue blocks readiness. A deterministic coordinator writes the final report; no third model changes the conclusion.

If the request has no subject or context, the correct result may be a small set of essential clarification questions. Unknowns that can remain validation conditions need not prevent choosing a direction.

## Results and evidence

Every run saves `report.html`, `report.md` and `report.json`. Reports retain proposal versions, the objection ledger, public exchanges, provider/model configuration, reported usage, stopping reason and next steps.

| Decision | Meaning |
| --- | --- |
| `ready_to_validate` | Both roles accept the current direction for real-world validation |
| `conditional` | A recommendation with retained risks or qualifications |
| `blocked` | Material unresolved issues prevent readiness |
| `needs_clarification` | Missing information could change the decision |
| `undetermined` | The execution or public record is insufficient for a complete conclusion |

The CLI always records `verification_status: not_checked`: it does not browse evidence, execute code or run suggested tests. An issue marked `resolved` was addressed in the discussion, not empirically proven fixed.

Reports contain your question and context; review them before sharing. Private provider reasoning and signatures are excluded from reports and events. Adapters may temporarily retain required protocol fields separately in memory to continue the same role's conversation; they clear that state when the run ends. HTML is script-free and escapes model text.

## Limits and failure behavior

```sh
debate-direction "Your question" --min-rounds 2 --max-rounds 4 --max-output-tokens 12000 --max-total-tokens 150000 --timeout 180 --max-duration 900 --out runs/my-review
```

The example uses your saved profile. Explicit model/provider flags work with the same limit options. `--stall-rounds` controls how many unchanged rounds trigger a stop. Higher effort may need a larger output allowance; truncated, refused, malformed and incomplete responses do not count as acceptance.

Usage and duration are observed stopping thresholds. In-flight requests can exceed them or finish later; failed calls may have unreported usage. No automatic retry or model fallback occurs. Cancellation prevents further calls but cannot revoke a request already processed by a provider. Existing reports require explicit `--overwrite`.

`--json` writes the report to stdout; progress stays on stderr. `--quiet` suppresses progress. Exit codes are `0` complete discussion, `1` configuration/input/filesystem error, `2` missing input or unresolved direction, `3` partial execution, and `130` cancellation. Exit code zero does not certify that the recommendation is correct.

## Development and validation

Python 3.11+, with no third-party runtime dependencies:

```sh
python -m pip install -e .
python scripts/sync_skill.py --check
python -m unittest discover -s tests -v
debate-direction --demo
```

GitHub Actions runs platform checks on Windows, macOS and Linux, including package and installer exercises. Adapter tests use controlled transports and need no API keys. The [validation record](docs/validation.md) distinguishes actual checks, the prior native exercise, documentation-based host compatibility, and untested live provider combinations.

To change the bundled native skill, edit `skills/debate-direction`, then run `python scripts/sync_skill.py` before building. An adapter implements `complete(...) -> Completion`, supports two concurrent openings, preserves the shared configuration and returns honest usage and model metadata. See [design](docs/design.md), [contribution instructions](CONTRIBUTING.md) and [security](SECURITY.md).

v0.2 adds OS installers, local setup/diagnostics, native host installation and multiple API adapters. Automatic retrieval, executed validation, persisted debate resume, a hosted service and authenticated reading of another application's session settings remain outside the current implementation.

Project descriptions, metadata, CLI messages, report labels and examples use English. Debate responses default to English unless explicitly requested otherwise; user input is preserved. [README.zh-CN.md](README.zh-CN.md) provides complete Chinese instructions.

## License

[MIT](LICENSE). Contributions and adaptations are welcome.
