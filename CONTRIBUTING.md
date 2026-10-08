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
- CLI configuration is explicit or caller-supplied, never advertised as reading a chat UI.
- Blind initial analysis precedes the exchange of public arguments.
- An objection never disappears merely because a subsequent response omits it.
- Only a critic's explicit, justified evaluation can close an answered objection.
- The final proposal must have been reviewed at its actual version.
- A remaining critical/high objection prevents a ready-to-validate result.
- Consensus never changes `verification_status` to verified.
- Provider failure, time limits, cancellation and round limits remain visible in reports.
- User and model text never becomes executable code or report HTML.

Before proposing an additional agent or model call, explain which demonstrated failure it resolves and how it affects cost, latency and the user's same-model requirement. Add focused regression tests for meaningful bugs, rather than tests that repeat implementation details.
