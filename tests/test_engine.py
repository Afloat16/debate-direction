"""Adversarial integration tests for the deterministic two-agent coordinator."""

import copy
import json
import threading
import unittest
from unittest.mock import patch

from debate_direction.config import SessionConfig
from debate_direction.engine import DebateEngine
from debate_direction.provider import Completion, ProviderError


def proposal(*, responses=None, recommendation="Measure a baseline and run a reversible pilot."):
    return {
        "needs_clarification": False,
        "clarification_questions": [],
        "problem_statement": "Staff spend too long finding the relevant work item.",
        "goal": "Choose an improvement that can be evaluated within two weeks.",
        "success_criteria": ["Compare task completion time and error rate against a recorded baseline."],
        "assumptions": ["Representative staff can participate in a pilot."],
        "options": [
            {"id": "P1", "title": "Reversible pilot", "approach": "Measure, then pilot one small change.", "tradeoffs": ["Does not address every workflow."]},
            {"id": "P2", "title": "Full redesign", "approach": "Replace the existing workflow.", "tradeoffs": ["Scope may exceed the two-week limit."]},
        ],
        "recommended_option_id": "P1",
        "recommendation": recommendation,
        "implementation_steps": ["Record a baseline.", "Ship the pilot behind a reversible switch."],
        "conditions": ["Reuse existing permission checks."],
        "validation_steps": ["Check permission isolation and compare the baseline before expansion."],
        "public_summary": "A bounded pilot gives a concrete direction with explicit validation work.",
        "responses": copy.deepcopy(responses or []),
    }


def risk_scan():
    return {
        "needs_clarification": False, "clarification_questions": [],
        "success_criteria": ["Preserve access controls and rollback."],
        "risk_areas": [{
            "id": "R1", "severity": "high", "concern": "A changed workflow could bypass access controls.",
            "check": "Retain permission checks and test isolation.",
        }],
        "public_summary": "Independently inspect permission boundaries, scope, and reversibility.",
    }


def issue(issue_id="I-001", severity="high"):
    return {
        "id": issue_id, "severity": severity, "title": "Permission checks must remain explicit",
        "description": "The pilot must not expose work items beyond current permissions.",
        "target": "P1 permission boundary",
        "resolution_criterion": "Specify the existing server-side permission check and isolation test.",
    }


def response_to(issue_id="I-001", action="fix"):
    return {
        "issue_id": issue_id, "action": action,
        "summary": "Keep the current server-side access checks and make isolation a release condition.",
        "change": "Add permission-isolation checks to the pilot acceptance criteria." if action == "fix" else "",
    }


def evaluation(issue_id="I-001", status="resolved"):
    return {
        "issue_id": issue_id, "status": status,
        "rationale": "The current proposal explicitly retains the server-side checks and isolation test.",
    }


def review(version, *, assessment="accept", new_issues=None, evaluations=None):
    return {
        "reviewed_version": version,
        "assessment": assessment,
        "public_summary": "Accept the bounded direction subject to the stated, unexecuted validation steps.",
        "clarification_questions": [],
        "new_issues": copy.deepcopy(new_issues or []),
        "issue_evaluations": copy.deepcopy(evaluations or []),
        "conditions": ["Actual validation is still required."],
        "next_steps": ["Run the documented pilot checks before expanding it."],
    }


def issue_script(*, severity="high", action="fix", resolution="resolved"):
    return {
        ("review", 1): review(1, assessment="revise", new_issues=[issue(severity=severity)]),
        ("revise", 2): proposal(responses=[response_to(action=action)]),
        ("review", 2): review(2, evaluations=[evaluation(status=resolution)]),
    }


class ScriptedProvider:
    """Thread-safe scripted provider; every invocation is visible to assertions."""

    def __init__(self, script=None, *, hook=None, initial_barrier=None, usage=(20, 10), models=None):
        self.script = script or {}
        self.hook = hook
        self.initial_barrier = initial_barrier
        self.usage = usage
        self.models = models or {}
        self.calls = []
        self.returned = []
        self._lock = threading.Lock()

    def complete(self, **request):
        snapshot = copy.deepcopy({key: value for key, value in request.items() if key != "config"})
        snapshot["config"] = request["config"]
        snapshot["thread"] = threading.get_ident()
        with self._lock:
            self.calls.append(snapshot)
        phase, number = request["phase"], request["round_number"]
        if self.initial_barrier is not None and phase in {"propose", "risk_scan"}:
            self.initial_barrier.wait(timeout=3)
        if self.hook is not None:
            self.hook(request, self)
        value = self.script.get((phase, number))
        if isinstance(value, BaseException):
            raise value
        if value is None:
            if phase in {"propose", "revise"}:
                value = proposal()
            elif phase == "risk_scan":
                value = risk_scan()
            else:
                value = review(number)
        data = copy.deepcopy(value)
        tokens = self.usage(request) if callable(self.usage) else self.usage
        result = Completion(
            data=data,
            model=self.models.get((phase, number), "test-model-snapshot"),
            input_tokens=tokens[0], output_tokens=tokens[1],
            response_id=f"offline-{request['role']}-{phase}-{number}",
        )
        with self._lock:
            self.returned.append((phase, number, result))
        return result


class DebateEngineTests(unittest.TestCase):
    def config(self, **overrides):
        limits = {"max_rounds": 2, "min_rounds": 2, **overrides}
        return SessionConfig(model="test-model", reasoning_effort="high", **limits)

    def run_debate(self, provider=None, *, config=None, on_event=None, question="Improve the work-item workflow within two weeks."):
        provider = provider or ScriptedProvider()
        engine = DebateEngine(provider, config or self.config(), on_event=on_event)
        return engine.run(question, "Existing permissions must continue to apply."), engine, provider

    def test_clean_debate_runs_two_rounds_and_reports_validation_as_outstanding(self):
        report, _, provider = self.run_debate()
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["stop_reason"], "converged")
        self.assertEqual(report["decision"], "ready_to_validate")
        self.assertEqual(report["verification_status"], "not_checked")
        self.assertEqual(report["rounds_completed"], 2)
        self.assertEqual(report["proposal"]["version"], 2)
        self.assertTrue(report["proposal"]["reviewed"])
        self.assertEqual(len(provider.calls), 5)
        self.assertEqual(report["usage"]["calls"], len(provider.calls))

    def test_initial_calls_overlap_and_cannot_see_the_opponents_opening(self):
        initial_proposal = proposal()
        initial_proposal["public_summary"] = "PRO_OPENING_SENTINEL"
        initial_scan = risk_scan()
        initial_scan["public_summary"] = "CON_OPENING_SENTINEL"
        provider = ScriptedProvider(
            {("propose", 1): initial_proposal, ("risk_scan", 0): initial_scan},
            initial_barrier=threading.Barrier(2),
        )
        config = self.config()
        report, engine, _ = self.run_debate(provider, config=config)
        self.assertEqual(report["status"], "completed")
        openings = [call for call in provider.calls if call["phase"] in {"propose", "risk_scan"}]
        self.assertEqual(len({call["thread"] for call in openings}), 2)
        for call in openings:
            self.assertEqual(len(call["messages"]), 1)
            text = json.dumps(call["messages"])
            self.assertNotIn("PRO_OPENING_SENTINEL", text)
            self.assertNotIn("CON_OPENING_SENTINEL", text)
        for call in provider.calls:
            self.assertIs(call["config"], config)
        self.assertIsNot(engine.histories["pro"], engine.histories["con"])
        pro_assistant_text = " ".join(message["content"] for message in engine.histories["pro"] if message["role"] == "assistant")
        con_assistant_text = " ".join(message["content"] for message in engine.histories["con"] if message["role"] == "assistant")
        self.assertNotIn("CON_OPENING_SENTINEL", pro_assistant_text)
        self.assertNotIn("PRO_OPENING_SENTINEL", con_assistant_text)

    def test_provider_mutating_request_cannot_change_engine_histories_or_schemas(self):
        def mutate(request, provider):
            request["messages"][0]["content"] = "MUTATED_SNAPSHOT"
            request["schema"]["type"] = "array"
        report, engine, _ = self.run_debate(ScriptedProvider(hook=mutate))
        self.assertEqual(report["status"], "completed")
        self.assertNotIn("MUTATED_SNAPSHOT", json.dumps(engine.histories))

    def test_progress_callback_receives_detached_snapshots(self):
        def mutate(event):
            event.clear()
            event["type"] = "MUTATED_CALLBACK"
        report, _, _ = self.run_debate(ScriptedProvider(issue_script()), on_event=mutate)
        self.assertEqual(report["status"], "completed")
        self.assertNotIn("MUTATED_CALLBACK", json.dumps(report))
        self.assertEqual(report["issues"][0]["status"], "resolved")

    def test_mutating_a_provider_completion_later_cannot_rewrite_accepted_work(self):
        def mutate_earlier_completion(request, provider):
            if request["phase"] == "review":
                for phase, _, result in provider.returned:
                    if phase == "propose":
                        result.data["recommendation"] = "MUTATED_COMPLETION"
        report, _, _ = self.run_debate(
            ScriptedProvider(hook=mutate_earlier_completion),
            config=self.config(max_rounds=1, min_rounds=1),
        )
        self.assertEqual(report["status"], "completed")
        self.assertNotIn("MUTATED_COMPLETION", json.dumps(report))

    def test_issue_resolution_keeps_both_response_and_reviewer_history(self):
        report, _, _ = self.run_debate(ScriptedProvider(issue_script()))
        self.assertEqual(report["status"], "completed")
        item = report["issues"][0]
        self.assertEqual(item["id"], "I-001")
        self.assertEqual(item["status"], "resolved")
        self.assertEqual(item["responses"][0]["proposal_version"], 2)
        self.assertEqual([entry["to"] for entry in item["history"]], ["open", "resolved"])
        self.assertEqual(report["core_exchanges"][-1]["proposal_version"], 2)

    def test_proposer_cannot_silently_omit_a_live_objection(self):
        script = issue_script()
        script[("revise", 2)] = proposal()
        report, _, provider = self.run_debate(ScriptedProvider(script))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertEqual(report["issues"][0]["status"], "open")
        self.assertNotEqual(report["decision"], "ready_to_validate")
        self.assertEqual(len(provider.calls), 4)

    def test_critic_omission_does_not_close_the_proposers_claimed_fix(self):
        script = issue_script()
        script[("review", 2)] = review(2)
        report, _, _ = self.run_debate(ScriptedProvider(script))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertEqual(report["issues"][0]["status"], "open")
        self.assertFalse(report["proposal"]["reviewed"])
        self.assertEqual(report["rounds_completed"], 1)

    def test_accept_assessment_cannot_overrule_an_open_high_severity_issue(self):
        report, _, _ = self.run_debate(ScriptedProvider(issue_script(resolution="open")))
        self.assertEqual(report["stop_reason"], "round_limit")
        self.assertEqual(report["decision"], "blocked")
        self.assertEqual(report["issues"][0]["status"], "open")

    def test_high_accepted_risk_still_blocks_readiness(self):
        report, _, _ = self.run_debate(ScriptedProvider(issue_script(action="accept_risk", resolution="accepted_risk")))
        self.assertEqual(report["stop_reason"], "round_limit")
        self.assertEqual(report["decision"], "blocked")
        self.assertEqual(report["issues"][0]["status"], "accepted_risk")
        self.assertTrue(any("I-001" in condition for condition in report["conditions"]))

    def test_low_accepted_risk_remains_a_condition_even_when_discussion_converges(self):
        report, _, _ = self.run_debate(ScriptedProvider(issue_script(severity="low", action="accept_risk", resolution="accepted_risk")))
        self.assertEqual(report["stop_reason"], "converged")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["decision"], "conditional")
        self.assertEqual(report["issues"][0]["status"], "accepted_risk")

    def test_accepting_a_risk_cannot_be_relabelled_as_resolving_it(self):
        report, _, _ = self.run_debate(ScriptedProvider(issue_script(action="accept_risk", resolution="resolved")))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertEqual(report["issues"][0]["status"], "open")

    def test_fix_requires_a_concrete_change(self):
        script = issue_script()
        script[("revise", 2)]["responses"][0]["change"] = "   "
        report, _, _ = self.run_debate(ScriptedProvider(script))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertEqual(report["issues"][0]["status"], "open")
        self.assertEqual(report["issues"][0]["responses"], [])

    def test_invalid_review_cannot_partially_mutate_the_ledger(self):
        script = {
            ("review", 1): review(1, assessment="revise", new_issues=[issue("I-001"), issue("I-002")]),
            ("revise", 2): proposal(responses=[response_to("I-001"), response_to("I-002")]),
            ("review", 2): review(2, evaluations=[evaluation("I-001"), evaluation("UNKNOWN")]),
        }
        report, _, _ = self.run_debate(ScriptedProvider(script))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertEqual([item["status"] for item in report["issues"]], ["open", "open"])
        self.assertEqual([len(item["history"]) for item in report["issues"]], [1, 1])

    def test_new_objection_cannot_be_opened_and_closed_in_the_same_review(self):
        script = {("review", 1): review(1, new_issues=[issue()], evaluations=[evaluation()])}
        report, _, _ = self.run_debate(ScriptedProvider(script))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertNotEqual(report["status"], "completed")

    def test_stale_version_approval_does_not_review_the_latest_proposal(self):
        script = {("review", 2): review(1)}
        report, _, _ = self.run_debate(ScriptedProvider(script))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertEqual(report["proposal"]["version"], 2)
        self.assertFalse(report["proposal"]["reviewed"])
        self.assertEqual(report["rounds_completed"], 1)

    def test_resolved_objection_cannot_be_skipped_after_a_later_revision(self):
        script = issue_script()
        script[("revise", 3)] = proposal(recommendation="Remove the earlier permission check to save time.")
        script[("review", 3)] = review(3)
        report, _, _ = self.run_debate(ScriptedProvider(script), config=self.config(max_rounds=3, min_rounds=3))
        self.assertEqual(report["stop_reason"], "invalid_response")
        self.assertFalse(report["proposal"]["reviewed"])
        self.assertNotEqual(report["status"], "completed")

    def test_a_resolved_issue_can_be_reopened_against_a_new_version(self):
        script = issue_script()
        script[("review", 3)] = review(3, assessment="blocked", evaluations=[evaluation(status="open")])
        report, _, _ = self.run_debate(ScriptedProvider(script), config=self.config(max_rounds=3, min_rounds=3))
        self.assertEqual(report["stop_reason"], "round_limit")
        self.assertEqual(report["decision"], "blocked")
        self.assertEqual([entry["to"] for entry in report["issues"][0]["history"]], ["open", "resolved", "open"])

    def test_reported_model_drift_stops_further_debate(self):
        provider = ScriptedProvider(models={("review", 1): "a-different-snapshot"})
        report, _, _ = self.run_debate(provider)
        self.assertEqual(report["stop_reason"], "model_drift")
        self.assertFalse(report["model_identity"]["consistent"])
        self.assertNotEqual(report["status"], "completed")
        self.assertEqual(len(provider.calls), 3)

    def test_initial_peer_failure_preserves_successful_work_and_known_usage(self):
        provider = ScriptedProvider({("risk_scan", 0): ProviderError("Offline failure")})
        report, _, _ = self.run_debate(provider)
        self.assertEqual(report["stop_reason"], "provider_error")
        self.assertIsNotNone(report["proposal"])
        self.assertFalse(report["proposal"]["reviewed"])
        self.assertEqual(report["usage"]["calls"], 2)
        self.assertEqual(report["usage"]["completed_calls"], 1)
        self.assertEqual(report["usage"]["failed_calls"], 1)
        self.assertEqual(report["usage"]["unknown_usage_calls"], 1)
        self.assertEqual(report["usage"]["total_tokens"], 30)

    def test_exact_usage_threshold_stops_before_starting_another_call(self):
        report, _, provider = self.run_debate(ScriptedProvider(usage=(256, 0)), config=self.config(max_total_tokens=512))
        self.assertEqual(report["stop_reason"], "budget_limit")
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(report["usage"]["total_tokens"], 512)
        self.assertFalse(report["usage"]["threshold_exceeded"])
        self.assertFalse(report["proposal"]["reviewed"])

    def test_inflight_usage_overrun_is_disclosed_and_no_more_calls_start(self):
        report, _, provider = self.run_debate(ScriptedProvider(usage=(300, 0)), config=self.config(max_total_tokens=512))
        self.assertEqual(report["stop_reason"], "budget_limit")
        self.assertTrue(report["usage"]["threshold_exceeded"])
        self.assertEqual(report["usage"]["total_tokens"], 600)
        self.assertEqual(len(provider.calls), 2)

    def test_final_review_crossing_usage_threshold_is_still_a_partial_run(self):
        def usage(request):
            return (500, 0) if request["phase"] == "review" and request["round_number"] == 2 else (10, 0)
        report, _, provider = self.run_debate(ScriptedProvider(usage=usage), config=self.config(max_total_tokens=512))
        self.assertEqual(len(provider.calls), 5)
        self.assertEqual(report["stop_reason"], "budget_limit")
        self.assertEqual(report["status"], "partial")
        self.assertNotEqual(report["decision"], "ready_to_validate")

    def test_elapsed_time_threshold_prevents_new_calls_without_sleeping(self):
        clock = {"now": 0.0}
        def advance_after_opening(request, provider):
            if request["phase"] in {"propose", "risk_scan"}:
                clock["now"] = 2.0
        with patch("debate_direction.engine.time.monotonic", side_effect=lambda: clock["now"]):
            report, _, provider = self.run_debate(
                ScriptedProvider(hook=advance_after_opening, initial_barrier=threading.Barrier(2)),
                config=self.config(max_duration_seconds=1),
            )
        self.assertEqual(report["stop_reason"], "time_limit")
        self.assertEqual(len(provider.calls), 2)
        self.assertTrue(report["usage"]["duration_threshold_exceeded"])

    def test_cancellation_of_a_sequential_call_records_unknown_usage_and_stops(self):
        provider = ScriptedProvider({("review", 1): KeyboardInterrupt()})
        report, _, _ = self.run_debate(provider)
        self.assertEqual(report["stop_reason"], "cancelled")
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["calls"][-1]["status"], "interrupted")
        self.assertEqual(report["usage"]["unknown_usage_calls"], 1)
        self.assertEqual(len(provider.calls), 3)

    def test_unproductive_discussion_stalls_with_the_objection_preserved(self):
        script = {("review", 1): review(1, assessment="revise", new_issues=[issue()])}
        for number in range(2, 7):
            script[("revise", number)] = proposal(responses=[response_to(action="rebut")])
            script[("review", number)] = review(number, assessment="revise", evaluations=[evaluation(status="open")])
        report, _, provider = self.run_debate(
            ScriptedProvider(script), config=self.config(max_rounds=6, stall_rounds=2),
        )
        self.assertEqual(report["stop_reason"], "stalled")
        self.assertEqual(report["rounds_completed"], 3)
        self.assertEqual(report["issues"][0]["status"], "open")
        self.assertEqual(len(provider.calls), 7)

    def test_missing_essential_information_stops_before_a_fabricated_debate(self):
        initial = proposal()
        initial.update({"needs_clarification": True, "clarification_questions": ["What object needs to be changed?"]})
        report, _, provider = self.run_debate(ScriptedProvider({("propose", 1): initial}), question="Find a feasible modification.")
        self.assertEqual(report["stop_reason"], "needs_clarification")
        self.assertEqual(report["decision"], "needs_clarification")
        self.assertEqual(report["clarification_questions"], ["What object needs to be changed?"])
        self.assertEqual(len(provider.calls), 2)

    def test_blank_input_does_not_call_a_model_or_claim_model_evidence(self):
        report, _, provider = self.run_debate(question="   ")
        self.assertEqual(report["decision"], "needs_clarification")
        self.assertEqual(provider.calls, [])
        self.assertIsNone(report["model_identity"]["consistent"])

    def test_oversized_input_is_rejected_before_calling_a_provider(self):
        report, _, provider = self.run_debate(config=self.config(max_input_chars=20))
        self.assertEqual(report["stop_reason"], "input_limit")
        self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
