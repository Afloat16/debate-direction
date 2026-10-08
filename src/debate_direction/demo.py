"""A labeled, deterministic example. This provider makes zero model calls."""

from copy import deepcopy

from .provider import Completion

DEMO_QUESTION = "Improve the support ticket dashboard so support staff can find tickets that need attention faster. The team has only two weeks; identify a direction suitable for a pilot."
DEMO_CONTEXT = "Fixed demo context: a ticket list and access controls already exist. No user task timing data, API details or code have been provided. All proposals still require validation."


def proposal(revised=False):
    return {
        "needs_clarification": False, "clarification_questions": [],
        "problem_statement": "Support staff need to find pending tickets faster, but the specific bottleneck has not been measured.",
        "goal": "Choose and validate a reversible improvement direction within two weeks.",
        "success_criteria": ["Record baseline completion times and errors for representative tasks, then compare the pilot results.", "Preserve existing data permissions and workflow entry points."],
        "assumptions": ["The team can invite representative support staff to a short trial.", "The capabilities of the existing APIs still need to be checked."],
        "options": [
            {"id": "P1", "title": "Rebuild search and add smart recommendations", "approach": "Rebuild the search experience and add an entry point for recommendations.", "tradeoffs": ["The scope is broad, and there is no evidence identifying the bottleneck."]},
            {"id": "P2", "title": "Pilot combined filters and personal views", "approach": "Measure first, then run a small pilot with filters, sorting and saved views.", "tradeoffs": ["The improvement scope is limited, and APIs and permissions require validation."]},
        ],
        "recommended_option_id": "P2" if revised else "P1",
        "recommendation": "Observe representative tasks first, then pilot combined filters and personal views. Preserve the existing entry point and provide a rollback option." if revised else "Rebuild search and add smart recommendations to reduce the time spent finding tickets.",
        "implementation_steps": (["Observe representative ticket lookup tasks and record a baseline.", "Confirm existing API capabilities and permission constraints.", "Run a small pilot with combined filters, adjustable sorting and personal views.", "Use the agreed success criteria to decide whether to keep, adjust or roll back the changes."] if revised else ["Review the searchable fields.", "Build the new search and recommendation interface.", "Invite support staff to try it."]),
        "conditions": ["Pilot features must use the existing server-side permission checks.", "If the APIs do not support the required filters, adjust the pilot scope first."],
        "validation_steps": ["Measure completion times and errors for the same tasks before and after the changes.", "Check role permissions, unauthorized access and data isolation in saved views.", "Check query response times with a realistic volume of data."],
        "public_summary": "Withdraw the full rebuild in favor of a small, reversible pilot, with permission checks as a release condition." if revised else "Prioritize rebuilding search and adding smart recommendations, with a small filtering pilot as an alternative.",
        "responses": ([
            {"issue_id": "I-001", "action": "fix", "summary": "Accept the concerns about scope and insufficient evidence, and withdraw the full rebuild.", "change": "Switch to P2: measure first, then run the pilot."},
            {"issue_id": "I-002", "action": "fix", "summary": "Personal views save only filter settings; server-side queries still enforce existing permissions.", "change": "Add permission tests and rollback conditions for failures."},
        ] if revised else []),
    }


class DemoProvider:
    """Scripted responses solely for the built-in demonstration scenario."""

    def complete(self, *, role, phase, round_number, instructions, messages, schema, config):
        if phase in {"propose", "revise"}:
            data = proposal(revised=phase == "revise")
        elif phase == "risk_scan":
            data = {"needs_clarification": False, "clarification_questions": [],
                    "success_criteria": ["Measure the goal through task completion times and errors.", "Keep the changes reversible within the two-week period."],
                    "risk_areas": [
                        {"id": "R1", "severity": "high", "concern": "There is no evidence that search is the main bottleneck.", "check": "Observe real tasks first."},
                        {"id": "R2", "severity": "high", "concern": "Personal views could unintentionally expand access to data.", "check": "Reuse the existing server-side permission checks."},
                    ], "public_summary": "Independently assess the bottleneck evidence, two-week scope, permissions and reversibility."}
        elif phase == "review" and round_number == 1:
            data = {"assessment": "revise", "public_summary": "The full rebuild lacks evidence of the bottleneck, and the design does not yet specify how permission constraints will be enforced.",
                    "clarification_questions": [],
                    "new_issues": [
                        {"id": "I-001", "severity": "high", "title": "The rebuild scope lacks supporting evidence", "description": "No task data supports rebuilding search, so the investment is difficult to justify within two weeks.", "target": "P1", "resolution_criterion": "Reduce the change scope and measure a baseline first."},
                        {"id": "I-002", "severity": "high", "title": "Permission boundaries for personal views are unclear", "description": "Saved views must not bypass server-side ticket permissions.", "target": "P2", "resolution_criterion": "Include existing permission checks and isolation tests in the design and release conditions."},
                    ], "issue_evaluations": [], "conditions": ["Preserve the existing entry point."], "next_steps": ["Narrow the changes to a reversible pilot."]}
        elif phase == "review":
            data = {"assessment": "accept", "public_summary": "Accept the small pilot direction; its effect on the bottleneck and performance still require measurement.",
                    "clarification_questions": [], "new_issues": [],
                    "issue_evaluations": [
                        {"issue_id": "I-001", "status": "resolved", "rationale": "The latest proposal withdraws the full rebuild and instead measures a baseline before the pilot."},
                        {"issue_id": "I-002", "status": "resolved", "rationale": "The latest design explicitly reuses server-side permissions and includes isolation tests and rollback conditions."},
                    ], "conditions": ["Begin the pilot only after the API, permission and realistic performance checks pass."], "next_steps": ["Provide the current interface and representative workflows to define the pilot scope."]}
        else:
            raise ValueError("Unsupported demo phase")
        if phase == "review":
            data["reviewed_version"] = round_number
        return Completion(data=deepcopy(data), model="demo-scripted", input_tokens=0,
                          output_tokens=0, response_id=f"demo-{role}-{phase}-{round_number}")
