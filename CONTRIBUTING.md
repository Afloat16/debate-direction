# Contributing

Contributions of actual failure cases, protocol improvements, and code fixes are welcome. Remove personal information and credentials from questions, source material, and reports before sharing them.

## Local checks

Python 3.11+; runtime and tests use only the standard library.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m debate_direction --demo --out runs/review-example
```

PowerShell users can set `$env:PYTHONPATH = "src"` before running the Python commands, or install the package in a virtual environment.

## Invariants to preserve

- Exactly two role contexts. The coordinator is code, not a hidden third model judge.
- Both roles share one immutable model/effort configuration.
- Provider-specific reasoning controls remain literal; unsupported labels are rejected rather than approximated.
- CLI configuration is explicit or caller-supplied, never advertised as reading a chat UI.
- Blind initial analysis precedes the exchange of public arguments.
- An objection never disappears merely because a subsequent response omits it.
- Only a critic's explicit, justified evaluation can close an answered objection.
- The final proposal must have been reviewed at its actual version.
- A remaining critical/high objection prevents a ready-to-validate result.
- Consensus never changes `verification_status` to verified.
- Provider failure, time limits, cancellation and round limits remain visible in reports.
- User and model text never becomes executable code or report HTML.
- Keys stay out of saved profiles, diagnostics, model errors and reports. Required private protocol state stays separate from public histories and is cleared after the run.
- Installers preserve other host settings and modified skill content; replacements keep recoverable backups.

Run `python scripts/sync_skill.py` after changing the portable skill, and `python scripts/sync_skill.py --check` before a build. The wheel includes the same skill so users need no Git checkout. Provider profiles need current primary-source references and focused transport tests for their exact model/effort behavior. Use `debate-direction providers --provider NAME` to inspect the public capability catalog.

The CI matrix covers Windows, macOS and Linux. Installation checks exercise local source and an existing uv installation; they must not be described as fresh-machine bootstrap or live native-agent tests.

Before proposing an additional agent or model call, explain which demonstrated failure it resolves and how it affects cost, latency and the user's same-model requirement. Add focused regression tests for meaningful bugs, rather than tests that repeat implementation details.
