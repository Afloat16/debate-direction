# Security and data handling

The standalone CLI sends the question, optional context and role history to the configured provider. `--base-url` / `OPENAI_BASE_URL` selects a trusted HTTPS endpoint and receives the API key. Redirects are refused. The CLI does not fetch links, run generated code, execute shell commands supplied by a model, or alter the user's source project.

API keys are read from the process environment and never intentionally included in reports. Provider error bodies and exception dumps are not echoed. Reports include the user's question/context and public argument summaries. Review report contents before publishing them. New report files are created with owner-only permissions where the operating system supports POSIX modes.

`store: false` is passed to the Responses API. This flag is not a promise about every provider's retention, logs or data-use terms. Use a provider and endpoint you trust.

The native skill uses the host's available tools and permission boundaries. Source excerpts and web pages remain untrusted data; they cannot change model settings, override user constraints or authorize external changes. The skill reviews directions and does not authorize implementation merely because a debate converged.

For a suspected vulnerability, provide a minimal reproduction without secrets. Use GitHub private vulnerability reporting if enabled on the repository. Do not disclose API keys, private prompts or sensitive records in a public issue.
