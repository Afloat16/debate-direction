# Changelog

## 0.2.0 — 2026-10-08

- Add one-command per-user installers for macOS/Linux and Windows PowerShell, including managed Python, source/ref selection, updates, offline preparation and optional native skill installation.
- Add safe installation for Codex, Claude Code and current Kimi Code skill directories, with project/custom scope, unchanged reruns, modification protection and recoverable backups.
- Bundle the portable skill in the Python package so no Git checkout is needed.
- Add OpenAI, Anthropic, DeepSeek, Kimi, Gemini and generic OpenAI-compatible provider presets, with provider-specific model and reasoning controls.
- Add non-secret setup profiles, exact provider/model/effort validation, provider inspection and local diagnostics.
- Keep required private continuation fields separate from public reports and clear adapter state after a run; retain public work if cleanup fails.
- Expand offline CI to Windows, macOS and Linux with package and installer exercises, including Windows PowerShell 5.1.
- Handle unavailable home directories without a traceback, and preserve Unicode JSON output through legacy Windows encodings.
- Update the English documentation and complete Chinese README with matching setup commands.

The existing positional-question command and OpenAI Responses path remain available. Reports add the selected provider and cleanup status. Explicit settings bypass automatic profile loading; no current chat model is guessed. Native host discovery does not establish native agent runtime support, and no live API compatibility claim is inferred from mocked tests.

## 0.1.0 — 2026-10-08

- Introduce two persistent debate roles, blind openings, version-specific reviews and a deterministic issue ledger.
- Add an OpenAI Responses CLI, native skill, public HTML/Markdown/JSON reports and a fixed offline example.
- Record a native two-agent exercise and its remaining validation limits.
