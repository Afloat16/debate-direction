# Debate Direction v0.1 validation record

Validation date: 2026-10-08. The results below describe separate coverage of implementation, orchestration, and generated-output quality. Evidence for one does not substitute for evidence for another.

The English-language documentation update does not constitute a new native-agent exercise or a live Responses API run.

## Completed checks

| Check | Result | What it supports |
| --- | --- | --- |
| Python 3.12 offline unit tests | 69 passed | Configuration, API adaptation, protocol state, failure handling, and export behavior satisfy the assertions under controlled inputs |
| Fixed CLI demonstration | Generated HTML, Markdown, and JSON | The entry point, two-role protocol, and report export run end to end; actual model calls: 0 |
| Python package build and installation into a separate directory | Succeeded; the installed version command and demonstration passed | The package structure and CLI entry point can be installed and run |
| Native skill structural validation | Passed | The skill metadata and file structure are valid |
| Native exercise with two real agents | Two continuing roles completed two valid review rounds | The current host, which supports subagents, can perform preparation, blind openings, version-specific reviews, and final reporting |
| Model-setting inheritance | Followed the current host's documented inheritance rules without model or effort overrides | The configuration source is `documented_inheritance`; this does not claim that either thread's actual runtime model or effort was read |

The native exercise used an invented photography-equipment booking scenario. A public account is available in the [native run example](native-example.md). The critic accepted the direction in round one and accepted it again after reviewing boundaries in round two. Issues were not fabricated to make the exchange more dramatic. The separate, fixed offline example demonstrates the visible sequence of raising issues, revising a proposal, and accepting it.

## Test coverage

- Model and reasoning effort must come from one explicit configuration pair. Mixed partial sources, false claims of current-UI inheritance, and conflicting settings are rejected.
- The CLI's blind openings receive separate public role histories, which are reused in later rounds. Full-history inheritance in the native host still includes shared context.
- Every historical issue must be reviewed again, including resolved issues. Omitted, duplicated, or unknown IDs and incorrect proposal versions cannot alter the valid ledger.
- The proposer cannot resolve objections unilaterally. Accepting a risk cannot be relabeled as fixing it, and material unresolved issues prevent a readiness judgment.
- Incomplete structures, refusals, truncated responses, missing usage, and model drift are rejected. Confirmable partial results are retained after errors.
- Cancellation, duration and token thresholds, and the call limit are covered. In-flight calls can incur additional usage.
- Report escaping, directory overwrite protection, structural integrity, and the distinction between the last reviewed proposal and an unreviewed revision are covered.

## Generation error found and addressed during the exercise

Both native roles initially classified matters to confirm before a pilot as blocking clarification. The coordinator asked each original role for one semantic correction: retain the questions and conditions, but do not make them block the current choice of direction. These corrections did not count as formal review rounds and did not introduce additional agents.

The skill protocol was subsequently clarified: `needs_clarification` is reserved for high-impact gaps that prevent the current direction decision; unknowns that can remain pilot conditions need not stop discussion. That clarification passed structural validation, but a second native case was not run afterward. It therefore cannot be claimed to have eliminated every instance of this generation error.

## Not yet verified

- **No live Responses API end-to-end call was performed.** No API key was available in the release environment. Provider requests and error handling were tested with a controlled transport; those tests do not establish online compatibility for every model, account, or parameter combination.
- **No real-world validation of the proposed directions was performed.** Neither the native exercise nor the CLI demonstration visited an actual studio, contacted members, configured tools, or ran a pilot. Their verification status remains `not_checked`.
- The total time required for preparation, rehearsal, and the one-week pilot in the native case was not checked. Acceptance by both roles does not establish that all steps fit within the seven days requested in the input.
- **HTML did not receive a visual acceptance check in a browser.** Dependencies needed for local browser execution were unavailable, and the cloud browser's security policy did not permit local `file:` previews. Exported content, escaping, and the absence of external scripts were checked; those checks were not presented as screenshot-based acceptance.
- There has been no cross-host validation, long-running deployment, real API cost benchmark, or large-sample evaluation of proposal quality. The project cannot promise that two agents are always more accurate than one.

GitHub Actions is configured to run offline tests, the demonstration, and installation checks on Python 3.11, 3.12, and 3.13. The repository's Actions records are the source for the outcome of each remote run.

## Reproduce the offline checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m debate_direction --demo
python3 -m pip install .
debate-direction --version
```

See the [README](../README.md) for live-model usage. Retain the actual configuration, reports, and failure states rather than documenting only successful cases.
