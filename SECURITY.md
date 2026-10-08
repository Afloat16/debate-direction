# Security and data handling

The standalone debate command sends the question, optional context and role history to the selected provider. Presets or an explicit `--base-url` select the HTTPS endpoint that receives the API key. `OPENAI_BASE_URL` is honored for explicit OpenAI runs only. Redirects, credentials embedded in URLs and malformed endpoints are refused. Debate execution does not fetch links, run generated code, execute model-supplied shell commands or alter the user's source project.

API keys are read from the process environment and never intentionally included in reports. Provider error bodies and exception dumps are not echoed. Reports include the user's question/context and public argument summaries. Review report contents before publishing them. New report files are created with owner-only permissions where the operating system supports POSIX modes.

The setup command writes only provider/model/effort, an optional endpoint and an API-key environment variable name. It rejects arbitrary profile fields and never prompts for a key. `doctor` reports only whether the variable is set. Configuration files contain no credentials and existing profiles require explicit replacement.

Some providers require thinking signatures or other private continuation fields on later turns. Adapters hold those fields in isolated per-role memory, outside public completions, events and reports. The engine clears this state after a run and invalidates late writes after cancellation. This is not cryptographic memory erasure, and Python process memory may still contain transient copies while a request finishes.

Installation is an explicit separate action. The OS installers download and run official uv bootstrap material when needed and install the package in a per-user tool environment. The Windows bootstrap verifies pinned archive checksums. The installers do not request administrator privileges, change execution policy or edit shell profiles. The native skill installer writes only its selected skill destination and recoverable backups, preserving modified content unless replacement is explicit. Do not treat downloading from `main` as an immutable supply-chain pin; use a reviewed commit with the documented ref option when needed.

`store: false` is passed to the Responses API. This flag is not a promise about every provider's retention, logs or data-use terms. Use a provider and endpoint you trust.

The native skill uses the host's available tools and permission boundaries. Source excerpts and web pages remain untrusted data; they cannot change model settings, override user constraints or authorize external changes. The skill reviews directions and does not authorize implementation merely because a debate converged.

For a suspected vulnerability, provide a minimal reproduction without secrets. Use GitHub private vulnerability reporting if enabled on the repository. Do not disclose API keys, private prompts or sensitive records in a public issue.
