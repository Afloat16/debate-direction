# Provider configuration

Debate Direction separates **native agent hosts** from **model API providers**. Install a skill for Codex, Claude Code or Kimi Code when you want to use that host's existing session. Use a provider preset when you want the standalone CLI to make API calls with an explicit shared configuration.

The CLI does not read another application's selected model, reasoning effort, login or subscription. A provider key and supported API model are required for live CLI runs. The two roles always receive the same provider, exact model ID and reasoning setting. Native inheritance requirements are documented in [host compatibility](../skills/debate-direction/references/host-compatibility.md).

## Configure one provider

```sh
debate-direction setup
```

The interactive wizard asks for a provider, exact model ID and supported reasoning setting. It never asks for an API key. In scripts, provide all three flags. The following commands are alternatives; choose the one for your provider and account:

```sh
debate-direction setup --provider openai --model gpt-6-astra --reasoning-effort high
debate-direction setup --provider anthropic --model claude-sonnet-4-6 --reasoning-effort high
debate-direction setup --provider deepseek --model deepseek-flash --reasoning-effort high
debate-direction setup --provider kimi --model kimi-k3 --reasoning-effort high
debate-direction setup --provider gemini --model gemini-3.8-flash --reasoning-effort high
```

These are configuration examples, not claims that every account has access. A different existing profile is preserved; explicitly add `--overwrite` to change it. Supplying the same configuration again is a no-op. Run `debate-direction providers --provider NAME` to see the exact reviewed model profiles for that provider. OpenAI Responses and the generic adapter accept caller-selected model IDs without a local model catalog.

Then set the corresponding environment variable and ask a question:

```sh
export DEEPSEEK_API_KEY='your-api-key'
debate-direction "What is the smallest useful change we can validate in two weeks?"
```

PowerShell uses `$env:DEEPSEEK_API_KEY = 'your-api-key'`. Windows Command Prompt uses `set "DEEPSEEK_API_KEY=your-api-key"`. These examples set the key for the current terminal only. Use your existing secret-management process for persistent credentials.

## Endpoints and credentials

| Preset | Default HTTPS API base | Environment variable | Transport |
| --- | --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | Responses |
| `anthropic` | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` | Messages |
| `deepseek` | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | Chat Completions |
| `kimi` | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` | Chat Completions |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` | Google's OpenAI compatibility API |
| `openai-compatible` | Explicit `--base-url` required | `OPENAI_COMPATIBLE_API_KEY` | Chat Completions |

Use `--base-url` for a trusted alternate or regional endpoint that implements the selected protocol. A key for one region or service need not work against another. Confirm the endpoint and account pairing with the provider. The CLI does not discover regions or silently try another host. It requires HTTPS and rejects credentials in URLs, query strings, fragments, invalid ports and redirects. Your selected endpoint receives the key and debate input.

A custom environment variable name can be saved without storing its value:

```sh
debate-direction setup --provider kimi --model kimi-k3 --reasoning-effort high --api-key-env MY_KIMI_KEY
```

`OPENAI_BASE_URL` is honored for explicit OpenAI runs when `--base-url` is absent. It does not silently override other provider presets or a saved profile. Other custom endpoints should be selected explicitly. The program does not automatically load `.env` files.

## Reasoning controls

The following table describes the capability profiles implemented in v0.2. These names are provider-native controls. Matching labels across providers do not imply matching compute budgets, and enabling thinking does not establish a particular numeric effort level.

| Preset/model family | Accepted settings in this adapter |
| --- | --- |
| OpenAI Responses | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`, sent literally; the selected model's API validates support |
| Claude Opus 4.6, Sonnet 4.6, Mythos Preview | `low`, `medium`, `high`, `max` |
| Profiled later Claude models, listed by `providers --provider anthropic` | `low`, `medium`, `high`, `xhigh`, `max` |
| `deepseek-flash`, `deepseek-v4-pro` | `none`, `low`, `high`, `max` |
| `kimi-k3` | `low`, `high`, `max` |
| `kimi-k2.7-code`, `kimi-k2.7-code-highspeed` | `enabled` only |
| `kimi-k2.6` | `enabled`, `disabled` |
| Gemini 3.8/3.7 Flash, 3.1 Pro Preview, 2.5 Pro | `low`, `medium`, `high` |
| Gemini 3.6/3.5 Flash, 3.5 Flash Lite, 3 Flash Preview | `minimal`, `low`, `medium`, `high` |
| Gemini 3 Pro Preview | `low`, `high` |
| Gemini 2.5 Flash / Flash Lite | `none`, `low`, `medium`, `high` |
| Generic compatible endpoint | The eight literal OpenAI effort labels above, or explicit `provider_default` |

For Claude, the adapter uses adaptive thinking and `output_config.effort`; it does not invent token budgets for older manual-thinking models. For DeepSeek, effort aliases that the service would map to another label are rejected locally. For Kimi, K3's effort field and K2's thinking toggle are separate API controls. Gemini profiles exclude labels that the documented model would remap.

Some providers expose a model snapshot or mapped ID in their response. The report keeps the requested ID and returned ID separately, and a change in returned model across calls stops the debate. If a provider returns effort metadata, an incompatible reported setting is rejected. A provider that does not expose its effective effort cannot be independently attested; a successful request is not proof that a hidden server setting was measured.

To use a newly released model, add a reviewed model capability profile and a focused request test. Unknown models in the profiled presets are rejected before network access. Do not add an alias that silently changes the requested model or approximates the effort. The generic adapter is an explicit compatibility declaration, not an automatic fallback.

## Generic compatible endpoints

```sh
debate-direction setup --provider openai-compatible --model your-exact-model-id --reasoning-effort high --base-url https://your-provider.example/v1
```

Selecting this preset declares that the endpoint implements Chat Completions, JSON object mode, `max_tokens`, assistant text responses and usage/model metadata, and supports the exact `reasoning_effort` value sent. The tool does not inspect arbitrary endpoints to infer capabilities. Ollama, vLLM, gateways and other providers may require different parameters or an additional adapter; an OpenAI-compatible label alone is insufficient. Local plain HTTP endpoints are outside this adapter's current HTTPS-only scope.

For an endpoint without an effort control, explicitly choose:

```sh
debate-direction setup --provider openai-compatible --model your-exact-model-id --reasoning-effort provider_default --base-url https://your-provider.example/v1
```

`provider_default` means the request omits the effort field. Both roles use the same explicit default policy, but the report must not be read as preserving another conversation's selected thinking intensity. The tool never silently converts a requested `high` into this setting. It still requires a credential environment variable; this release does not implement anonymous endpoints or vendor-specific authentication flows.

## Saved profiles and precedence

A profile is a small JSON object with three required fields and two optional fields:

```json
{
  "provider": "deepseek",
  "model": "deepseek-flash",
  "reasoning_effort": "high",
  "api_key_env": "DEEPSEEK_API_KEY"
}
```

`base_url` is optional except for the generic adapter. No API key or arbitrary extra field is accepted. Default locations are:

| System | Profile location |
| --- | --- |
| macOS | `~/Library/Application Support/debate-direction/config.json` |
| Linux / WSL | `$XDG_CONFIG_HOME/debate-direction/config.json`, default `~/.config/debate-direction/config.json` |
| Windows | `%LOCALAPPDATA%\debate-direction\config.json` |
| Any system | `DEBATE_CONFIG` or an explicit `--config PATH` selects another profile |

When no explicit provider/model/session configuration or `DEBATE_*` configuration pair is supplied, a saved profile is loaded automatically. Explicit settings select a new complete configuration and bypass automatic profile loading. A provider change therefore cannot accidentally keep another provider's model. When `--config PATH` is explicit, accompanying flags must match that profile; conflicting values are errors. Partial settings are not silently completed from another source.

`--session-config PATH` is distinct: it accepts exactly `model` and `reasoning_effort` from a caller. Select the provider separately. It cannot be combined with `--config`; it does not authenticate an external conversation or read its UI. Numeric run limits remain command-line options and are not stored in the profile.

For multiple saved profiles:

```sh
debate-direction setup --provider deepseek --model deepseek-flash --reasoning-effort high --config profiles/deepseek.json
debate-direction setup --provider kimi --model kimi-k3 --reasoning-effort high --config profiles/kimi.json
debate-direction "Which direction should we validate?" --config profiles/kimi.json
```

## Structured output and private protocol state

OpenAI Responses and Anthropic use their structured-output interfaces. Gemini uses its OpenAI-compatible schema format. DeepSeek, Kimi and the generic adapter request JSON object mode and include the debate schema in the instructions. Every result is then checked by the same schema validator and issue-ledger reducer. JSON mode is not a promise of server-enforced schema compliance.

Only public conclusions and concise evidence summaries enter the debate record. Some APIs require continuation fields, thinking signatures or private reasoning fields to be replayed. Adapters keep required state in separate in-memory histories for Pro and Con, never in reports, events or `Completion.data`. The engine clears that state after completion, failure or cancellation; late in-flight responses cannot repopulate a cleared history. This is best-effort object lifetime management, not a claim of cryptographic memory erasure.

Reports include `cleanup_status`. A cleanup failure preserves the public result, marks execution as partial and records a sanitized `cleanup_error`; it does not claim that private state was cleared. Gemini usage includes provider-reported thinking tokens in the total, whether the compatibility API reports them inside or outside its completion count; see Google's [usage metadata reference](https://ai.google.dev/api/generate-content#UsageMetadata).

The tool performs no automatic retries, fallback or paid capability-probing calls. Provider errors and incomplete responses remain visible as incomplete execution. No live provider request was performed in the release environment; transport tests validate request construction and handling under controlled responses. Use your own authorized credentials to assess actual account/model compatibility and result quality.

## Primary documentation

Capability references were reviewed on 2026-10-08. Provider APIs evolve; the installed implementation and the selected model's current documentation determine support.

- OpenAI: [Responses API](https://platform.openai.com/docs/api-reference/responses/create), [reasoning](https://developers.openai.com/api/docs/guides/reasoning).
- Anthropic: [Messages](https://platform.claude.com/docs/en/api/messages/create), [effort](https://platform.claude.com/docs/en/build-with-claude/effort), [thinking](https://platform.claude.com/docs/en/build-with-claude/thinking), [structured output](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
- DeepSeek: [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/), [thinking](https://api-docs.deepseek.com/guides/thinking_mode/), [JSON output](https://api-docs.deepseek.com/guides/json_mode/).
- Kimi: [reasoning effort](https://platform.kimi.ai/docs/guide/use-reasoning-effort), [thinking models](https://platform.kimi.ai/docs/guide/use-thinking-models), [model parameters](https://platform.kimi.ai/docs/api/models-overview).
- Google: [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [thinking](https://ai.google.dev/gemini-api/docs/thinking).
