"""Mock end-to-end protocol checks: real engine and adapters, no live API calls.

DemoProvider supplies public turns; a transport wraps them in native envelopes.
Private sentinels are synthetic protocol fixtures, never real reasoning or keys.
"""

from __future__ import annotations

import copy
import json
import threading
import unittest
from collections import Counter

from debate_direction.config import SessionConfig
from debate_direction.demo import DEMO_CONTEXT, DEMO_QUESTION, DemoProvider
from debate_direction.engine import DebateEngine
from debate_direction.providers import create_provider, get_provider_preset
from debate_direction.reports import render_html, render_markdown


PROVIDERS = ("openai", "anthropic", "deepseek", "kimi", "gemini", "openai-compatible")
PRIVATE_PREFIX = "SYNTHETIC_PRIVATE_WIRE_ONLY"
KEY_SENTINEL = "synthetic-test-key-not-for-network-use"


class AdapterHarness:
    """Bind public engine call metadata to a thread-local controlled transport."""

    def __init__(self, name, *, model=None, effort="high", cancel_at=None,
                 cancel_initial_with_late_reply=False, cleanup_failure=False):
        self.name = name
        self.config = SessionConfig(
            provider=name, model=model or get_provider_preset(name).example_model,
            reasoning_effort=effort, max_rounds=2, min_rounds=2,
            max_output_tokens=4096, max_total_tokens=20000,
            timeout_seconds=17, max_duration_seconds=60,
        )
        self.local = threading.local()
        self.lock = threading.Lock()
        self.records = []
        self.cleanup_calls = 0
        self.cleanup_failure = cleanup_failure
        self.cancel_at = cancel_at
        self.cancel_initial_with_late_reply = cancel_initial_with_late_reply
        self.con_started = threading.Event()
        self.release_late_reply = threading.Event()
        self.late_reply_finished = threading.Event()
        self.demo = DemoProvider()
        options = {"api_key": KEY_SENTINEL, "transport": self.transport}
        if name == "openai-compatible":
            options["base_url"] = "https://integration-test.invalid/v1"
        self.adapter = create_provider(name, **options)
        self.returned_model = self.config.model + "-reported-test-snapshot"

    def __getattr__(self, name):
        if name == "clear_session":
            cleanup = getattr(self.adapter, name, None)
            if callable(cleanup):
                return self._clear_session
        raise AttributeError(name)

    def _clear_session(self):
        self.cleanup_calls += 1
        if self.cleanup_failure:
            raise RuntimeError(PRIVATE_PREFIX + " cleanup detail " + KEY_SENTINEL)
        self.adapter.clear_session()

    def complete(self, **request):
        self.local.request = request
        late = self.cancel_initial_with_late_reply and request["phase"] == "risk_scan"
        try:
            return self.adapter.complete(**request)
        finally:
            self.local.request = None
            if late:
                self.late_reply_finished.set()

    def transport(self, url, body, headers, timeout):
        request = self.local.request
        if request is None:
            raise AssertionError("transport lost its calling role")
        turn = (request["role"], request["phase"], request["round_number"])
        record = {
            "turn": turn, "url": url, "body": copy.deepcopy(body),
            "headers": dict(headers), "timeout": timeout,
            "config_object": request["config"],
            "public_messages": copy.deepcopy(request["messages"]),
        }
        with self.lock:
            self.records.append(record)
        if self.cancel_initial_with_late_reply:
            if request["phase"] == "risk_scan":
                self.con_started.set()
                if not self.release_late_reply.wait(3):
                    raise AssertionError("test did not release the pending CON response")
            elif request["phase"] == "propose":
                if not self.con_started.wait(3):
                    raise AssertionError("both blind calls did not start")
                raise KeyboardInterrupt()
        if turn == self.cancel_at:
            raise KeyboardInterrupt()
        completion = self.demo.complete(**request)
        public = json.dumps(completion.data, ensure_ascii=False)
        marker = PRIVATE_PREFIX + ":" + ":".join(map(str, turn))
        response_id = "mock-" + "-".join(map(str, turn))
        if self.name == "openai":
            response = {
                "id": response_id, "model": self.returned_model, "status": "completed",
                "reasoning": {"effort": self.config.reasoning_effort},
                "usage": {"input_tokens": 17, "output_tokens": 11},
                "output": [
                    {"type": "reasoning", "encrypted_content": marker, "summary": []},
                    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": public}]},
                ],
            }
        elif self.name == "anthropic":
            response = {
                "id": response_id, "model": self.returned_model, "type": "message",
                "role": "assistant", "stop_reason": "end_turn",
                "output_config": {"effort": self.config.reasoning_effort},
                "usage": {"input_tokens": 17, "cache_creation_input_tokens": 3,
                          "cache_read_input_tokens": 5, "output_tokens": 11},
                "content": [
                    {"type": "thinking", "thinking": "", "signature": marker + ":signature"},
                    {"type": "redacted_thinking", "data": marker + ":redacted"},
                    {"type": "text", "text": public},
                ],
            }
        else:
            message = {"role": "assistant", "content": public, "reasoning_content": marker + ":reasoning"}
            if self.name == "kimi":
                message["extra_content"] = {"kimi": {"continuation": marker + ":opaque"}}
            elif self.name == "gemini":
                message["extra_content"] = {"google": {"thought_signature": marker + ":signature"}}
            response = {
                "id": response_id, "model": self.returned_model,
                "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 11, "total_tokens": 28},
            }
            if self.name == "gemini":
                response["usage"].update({"total_tokens": 41, "completion_tokens_details": {"reasoning_tokens": 13}})
            if "reasoning_effort" in body:
                response["reasoning_effort"] = body["reasoning_effort"]
            if "thinking" in body:
                response["thinking"] = {"type": body["thinking"]["type"]}
        record["response"] = copy.deepcopy(response)
        return response

    def wire_messages(self, record):
        if self.name == "openai":
            return record["body"]["input"]
        messages = record["body"]["messages"]
        return messages if self.name == "anthropic" else messages[1:]

    def expected_assistant_replay(self, record):
        response = record["response"]
        if self.name == "anthropic":
            return {"role": "assistant", "content": response["content"]}
        if self.name == "openai":
            public = response["output"][-1]["content"][0]["text"]
            return {"role": "assistant", "content": public}
        message = response["choices"][0]["message"]
        if self.name == "kimi" and self.config.model in {"kimi-k3", "kimi-k2.7-code", "kimi-k2.7-code-highspeed"}:
            return message
        replay = {"role": "assistant", "content": message["content"]}
        if self.name == "gemini":
            replay["extra_content"] = message["extra_content"]
        return replay

    def private_history_is_empty(self):
        history = getattr(self.adapter, "_history", None)
        if history is None:
            return True
        with history._lock:
            return history._roles == {} and history._binding is None


class EngineProviderIntegrationTests(unittest.TestCase):
    def public_output(self, engine, report, events):
        return "\n".join((
            json.dumps(report, ensure_ascii=False), json.dumps(events, ensure_ascii=False),
            json.dumps(engine.histories, ensure_ascii=False),
            render_markdown(report), render_html(report),
        ))

    def assert_public_only(self, engine, report, events):
        public = self.public_output(engine, report, events)
        self.assertNotIn(PRIVATE_PREFIX, public)
        self.assertNotIn(KEY_SENTINEL, public)

    def assert_shared_settings(self, harness, records):
        for record in records:
            self.assertIs(record["config_object"], harness.config)
            self.assertEqual(record["body"]["model"], harness.config.model)
            self.assertEqual(record["timeout"], harness.config.timeout_seconds)
            self.assertNotIn(PRIVATE_PREFIX, json.dumps(record["public_messages"]))
            self.assertNotIn(KEY_SENTINEL, json.dumps(record["public_messages"]))
            if harness.name == "openai":
                self.assertEqual(record["body"]["reasoning"]["effort"], harness.config.reasoning_effort)
            elif harness.name == "anthropic":
                self.assertEqual(record["body"]["output_config"]["effort"], harness.config.reasoning_effort)
            elif harness.name == "kimi" and harness.config.model != "kimi-k3":
                self.assertEqual(record["body"]["thinking"]["type"], harness.config.reasoning_effort)
                self.assertNotIn("reasoning_effort", record["body"])
            elif harness.config.reasoning_effort == "provider_default":
                self.assertNotIn("reasoning_effort", record["body"])
            else:
                self.assertEqual(record["body"]["reasoning_effort"], harness.config.reasoning_effort)

    def assert_round_replay(self, harness, records):
        by_role = {"pro": [], "con": []}
        for record in records:
            role = record["turn"][0]
            previous = by_role[role]
            wire = harness.wire_messages(record)
            self.assertEqual(len(wire), 2 * len(previous) + 1)
            self.assertEqual(wire[-1], record["public_messages"][-1])
            for index, earlier in enumerate(previous):
                actual = wire[index * 2 + 1]
                expected = harness.expected_assistant_replay(earlier)
                if harness.name == "openai":
                    self.assertEqual(actual["role"], "assistant")
                    self.assertEqual(json.loads(actual["content"]), json.loads(expected["content"]))
                else:
                    self.assertEqual(actual, expected)
            opposite = "con" if role == "pro" else "pro"
            self.assertNotIn(PRIVATE_PREFIX + ":" + opposite + ":", json.dumps(wire))
            previous.append(record)
        self.assertEqual([item["turn"][1] for item in by_role["pro"]], ["propose", "revise"])
        self.assertEqual([item["turn"][1] for item in by_role["con"]], ["risk_scan", "review", "review"])

    def assert_successful_run(self, harness, engine, report, events, records):
        self.assertEqual((report["status"], report["stop_reason"], report["decision"]), ("completed", "converged", "ready_to_validate"), report["errors"])
        self.assertEqual(report["rounds_completed"], 2)
        self.assertEqual(report["verification_status"], "not_checked")
        self.assertEqual(report["proposal"]["version"], 2)
        self.assertTrue(report["proposal"]["reviewed"])
        self.assertEqual(report["proposal"]["recommended_option_id"], "P2")
        self.assertEqual({issue["id"]: issue["status"] for issue in report["issues"]}, {"I-001": "resolved", "I-002": "resolved"})
        self.assertEqual(report["config"]["provider"], harness.name)
        self.assertEqual(report["config"]["model"], harness.config.model)
        self.assertEqual(report["config"]["reasoning_effort"], harness.config.reasoning_effort)
        self.assertEqual(report["config"]["config_source"], "explicit")
        self.assertEqual(report["model_identity"], {
            "requested": harness.config.model, "returned": harness.returned_model,
            "models_seen": [harness.returned_model], "consistent": True,
        })
        self.assertEqual(Counter(call["role"] for call in report["calls"]), {"pro": 2, "con": 3})
        self.assertEqual(report["usage"]["completed_calls"], 5)
        self.assertEqual(report["usage"]["unknown_usage_calls"], 0)
        expected_input, expected_output = {"anthropic": (25, 11), "gemini": (17, 24)}.get(harness.name, (17, 11))
        self.assertEqual(report["usage"]["input_tokens"], expected_input * 5)
        self.assertEqual(report["usage"]["output_tokens"], expected_output * 5)
        self.assertEqual(report["usage"]["total_tokens"], (expected_input + expected_output) * 5)
        self.assertEqual(len(records), 5)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["cleanup_status"], "not_needed" if harness.name == "openai" else "cleared")
        self.assertTrue(harness.private_history_is_empty())
        self.assert_shared_settings(harness, records)
        self.assert_round_replay(harness, records)
        self.assert_public_only(engine, report, events)
        self.assertEqual(events[-1]["type"], "run_finished")

    def test_all_six_adapters_complete_two_rounds_with_private_public_separation(self):
        for name in PROVIDERS:
            with self.subTest(provider=name):
                harness = AdapterHarness(name)
                events = []
                engine = DebateEngine(harness, harness.config, on_event=events.append)
                report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
                self.assert_successful_run(harness, engine, report, events, harness.records)
                self.assertEqual(harness.cleanup_calls, 0 if name == "openai" else 1)

    def test_kimi_fixed_thinking_mode_preserves_opaque_replay_through_real_rounds(self):
        harness = AdapterHarness("kimi", model="kimi-k2.7-code", effort="enabled")
        events = []
        engine = DebateEngine(harness, harness.config, on_event=events.append)
        report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
        self.assert_successful_run(harness, engine, report, events, harness.records)
        self.assertTrue(all(record["body"]["thinking"] == {"type": "enabled", "keep": "all"} for record in harness.records))

    def test_generic_provider_default_is_recorded_without_an_invented_effort(self):
        harness = AdapterHarness("openai-compatible", effort="provider_default")
        events = []
        engine = DebateEngine(harness, harness.config, on_event=events.append)
        report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
        self.assert_successful_run(harness, engine, report, events, harness.records)
        self.assertEqual(report["config"]["reasoning_effort"], "provider_default")
        self.assertIn("provider_default", render_markdown(report))

    def test_same_engine_and_adapter_can_run_again_after_successful_cleanup(self):
        for name in PROVIDERS:
            with self.subTest(provider=name):
                harness = AdapterHarness(name)
                events = []
                engine = DebateEngine(harness, harness.config, on_event=events.append)
                first = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
                self.assertEqual(first["stop_reason"], "converged", first["errors"])
                events.clear()
                second = engine.run(DEMO_QUESTION, DEMO_CONTEXT + " A separate second run.")
                self.assert_successful_run(harness, engine, second, events, harness.records[5:])
                self.assertNotEqual(first["run_id"], second["run_id"])
                self.assertEqual(harness.cleanup_calls, 0 if name == "openai" else 2)

    def test_cancellation_after_one_review_keeps_ledger_and_clears_each_adapter(self):
        for name in PROVIDERS:
            with self.subTest(provider=name):
                harness = AdapterHarness(name, cancel_at=("pro", "revise", 2))
                events = []
                engine = DebateEngine(harness, harness.config, on_event=events.append)
                report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
                self.assertEqual((report["status"], report["stop_reason"]), ("partial", "cancelled"))
                self.assertEqual(report["rounds_completed"], 1)
                self.assertEqual(report["proposal"]["version"], 1)
                self.assertEqual({issue["id"]: issue["status"] for issue in report["issues"]}, {"I-001": "open", "I-002": "open"})
                self.assertEqual(report["calls"][-1]["status"], "interrupted")
                self.assertEqual(report["usage"]["unknown_usage_calls"], 1)
                self.assertEqual(report["cleanup_status"], "not_needed" if name == "openai" else "cleared")
                self.assertTrue(harness.private_history_is_empty())
                self.assert_shared_settings(harness, harness.records)
                self.assert_public_only(engine, report, events)

    def test_cancelled_blind_run_late_reply_cannot_repopulate_private_history(self):
        for name in PROVIDERS:
            with self.subTest(provider=name):
                harness = AdapterHarness(name, cancel_initial_with_late_reply=True)
                events = []
                engine = DebateEngine(harness, harness.config, on_event=events.append)
                try:
                    report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
                    self.assertEqual((report["status"], report["stop_reason"]), ("partial", "cancelled"))
                    self.assertEqual(report["rounds_completed"], 0)
                    self.assertTrue(harness.con_started.is_set())
                    self.assertFalse(harness.late_reply_finished.is_set())
                    self.assertTrue(harness.private_history_is_empty())
                    snapshot = json.dumps(report, sort_keys=True)
                finally:
                    harness.release_late_reply.set()
                    finished = harness.late_reply_finished.wait(3)
                self.assertTrue(finished, "in-flight test call did not finish after release")
                self.assertTrue(harness.private_history_is_empty())
                self.assertEqual(json.dumps(report, sort_keys=True), snapshot)
                self.assertEqual(report["usage"]["unknown_usage_calls"], 2)
                self.assert_public_only(engine, report, events)

    def test_cleanup_failure_retains_result_and_sanitizes_error_details(self):
        harness = AdapterHarness("anthropic", cleanup_failure=True)
        events = []
        engine = DebateEngine(harness, harness.config, on_event=events.append)
        report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
        self.assertEqual((report["status"], report["stop_reason"], report["decision"]), ("partial", "converged", "ready_to_validate"))
        self.assertEqual(report["cleanup_status"], "failed")
        self.assertEqual(report["rounds_completed"], 2)
        self.assertEqual(report["proposal"]["version"], 2)
        self.assertEqual(len(report["core_exchanges"]), 2)
        self.assertEqual([error["code"] for error in report["errors"]], ["cleanup_error"])
        self.assertFalse(harness.private_history_is_empty())
        self.assert_public_only(engine, report, events)
        self.assertEqual(events[-1]["status"], "partial")
        harness.adapter.clear_session()
        harness.cleanup_failure = False
        second = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
        self.assertEqual(second["status"], "completed", second["errors"])
        self.assertEqual(second["cleanup_status"], "cleared")

    def test_cleanup_failure_does_not_replace_cancellation_or_erase_issues(self):
        harness = AdapterHarness("kimi", cancel_at=("pro", "revise", 2), cleanup_failure=True)
        events = []
        engine = DebateEngine(harness, harness.config, on_event=events.append)
        try:
            report = engine.run(DEMO_QUESTION, DEMO_CONTEXT)
            self.assertEqual((report["status"], report["stop_reason"]), ("partial", "cancelled"))
            self.assertEqual(report["cleanup_status"], "failed")
            self.assertEqual(report["rounds_completed"], 1)
            self.assertEqual({error["code"] for error in report["errors"]}, {"cancelled", "cleanup_error"})
            self.assertEqual({issue["id"] for issue in report["issues"]}, {"I-001", "I-002"})
            self.assert_public_only(engine, report, events)
        finally:
            harness.adapter.clear_session()


if __name__ == "__main__":
    unittest.main()
