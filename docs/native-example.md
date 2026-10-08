# Debate Direction: native two-agent run example

This skill exercise ran on 2026-10-08 in a host with native subagent support. **The scenario was an invented test question; two real agents generated the role responses.** The exercise was conducted in Chinese. The input and run summary on this page are English translations of that original exercise, not a new run. This was neither the fixed CLI demonstration nor an investigation of an actual studio.

## Input

The original test input was in Chinese. Its English translation is:

> We are a six-person design studio sharing photography equipment. We currently book it through group messages, and missed messages lead to scheduling conflicts. We want an improvement within one week, have no dedicated administrator, and do not want to build a complex system. Use two agents to propose and challenge a direction, with at most two rounds. This run is for discussion only; do not make external changes.

## Result

The recommended direction was to try **one shared booking ledger, maintained by its users, with a check before taking equipment and explicit conflict-resolution rules**. Adoption remained conditional on confirming access for every member, dependencies between individual items and kits, migration of existing bookings, and members' ability to sustain manual checks. Existing booking tools and a physical booking board remained alternatives under different conditions.

| Field | Observed result |
| --- | --- |
| `status` | `completed` |
| `decision` | `ready_to_validate` |
| `stop_reason` | `converged` |
| `verification_status` | `not_checked` |
| Valid review rounds | 2 |
| Last reviewed proposal | V2 |
| Formal issue ledger | Empty; no issue IDs were fabricated |
| Model configuration source | `documented_inheritance`; neither subagent creation request supplied a model or effort override |

`ready_to_validate` means the direction can proceed to the listed validation steps. It still depends on unconfirmed adoption conditions. An empty issue ledger does not establish the external facts on which the proposal relies.

## What actually happened

The proposer and critic were created first and only acknowledged readiness. Blind opening tasks were sent after both existed. The same two roles continued throughout, without a third debate judge.

| Phase | Proposer's position or action | Critic's checks and disposition |
| --- | --- | --- |
| Blind openings | Offered three alternatives: a shared ledger, an existing calendar or booking tool, and a physical booking board; conditionally recommended the shared ledger | Independently examined booking authority and concurrency, resource and return boundaries, an implicit administrator burden, access and maintenance by all members, and the sample available within one week |
| Round 1: review of opening proposal V1 | V1 specified one authoritative record, checks before booking and taking equipment, user maintenance, conflict rules, and pause conditions | Found corresponding boundaries, validation requirements, or pause branches for the identified risks; accepted the V1 direction and raised no formal issues |
| Round 2: V2 | Submitted the complete V2 with no substantive changes, checking boundary cases, acceptance criteria, and the least costly validation steps | Reviewed V2 again and accepted it; did not transfer the previous version's acceptance automatically or require a meaningless change |

Concerns from the blind risk scan did not automatically become formal defects. The critic had to inspect the concrete proposal before deciding whether an actual defect existed. This case demonstrates **acceptance after review**. It does not contain a sequence in which the critic found defects and the proposer substantially redesigned the plan.

Both initial openings incorrectly marked matters that could be confirmed before the pilot as blocking clarification. The coordinator asked each existing role for one semantic correction, retaining the questions while removing their blocking effect on the current discussion. These corrections were not review rounds and did not create replacement roles. The protocol was subsequently clarified to make this distinction explicit.

## Retained conditions and validation steps

The following are **future validation plans discussed by the two roles; none was executed**:

| Matter to confirm | Proposed passing condition | Direction if it fails |
| --- | --- | --- |
| All six members can access and maintain the same record | Each member independently finds and enters their own example booking | Switch to a medium everyone can access, or pause |
| Simultaneous requests for the same equipment | The complete record retains both requests, and the users identify and resolve the conflict under the agreed rules before taking the equipment | Check synchronization and the process; repeated reminders cannot substitute for a safeguard |
| Dependencies between kits and individual items | Linked resources produce consistent availability decisions | Adjust the resource representation; choose another direction if it cannot represent dependencies accurately |
| Rescheduling, cancellation, and late returns | Recheck the new time slot, leave an unambiguous old record, and do not treat unreturned equipment as ready to take | Revise the rules and review the corresponding risks again |
| Ongoing maintenance burden | Users maintain their own bookings without one person continually entering missing records or arbitrating conflicts | The current direction does not meet the constraint of having no dedicated administrator |

An ordinary spreadsheet was not assumed to provide atomic bookings or automatic conflict prevention. If the workflow cannot tolerate missed manual checks or delayed equipment use, the required capabilities of existing booking tools must be checked first. Too few pilot bookings, or a pilot without competing requests, can establish only the operability actually observed, not the proposal's effectiveness.

**The schedule remains unverified.** The input requested an improvement within one week. The proposal included preparation, rehearsal, migration, and a one-week pilot, without establishing that all those steps fit within seven days from the start. Acceptance in two rounds did not remove this scheduling uncertainty; adoption still requires a feasible actual timetable.

## What this case establishes

The native skill did start two real roles, complete two reviews of specific proposal versions, and retain unknowns and validation plans. It also exposed that natural-language agents can misuse structured fields, requiring coordinator checks and limited correction.

This single exercise does not establish that two agents always outperform one or that the shared ledger has solved booking conflicts. Both roles inherited the same model and shared task context under the host's documented rules, so they can still share blind spots.
