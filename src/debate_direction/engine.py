"""Deterministic orchestration of exactly two isolated public debate histories.

The reducer, not a third model judge, owns issue state and stopping decisions.
No browsing or tests are executed here, so every report remains not_checked.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable, TYPE_CHECKING

from .prompts import instructions_for, task_message
from .schemas import (
    PROPOSAL_SCHEMA, REVIEW_SCHEMA, RISK_SCAN_SCHEMA, SCHEMA_VERSION,
    SchemaError, validate_schema,
)

if TYPE_CHECKING:
    from .config import SessionConfig


_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_UNRESOLVED = {"open", "disputed", "accepted_risk"}


class DebateProtocolError(ValueError):
    """A valid JSON response violated the debate's state-transition rules."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


class DebateEngine:
    """Run a bounded debate with a provider implementing ``complete``.

    ``on_event`` receives detached event dictionaries on the calling thread.
    Providers must be safe for the two concurrent blind initial calls. Their
    request timeout comes from the shared immutable SessionConfig.
    """

    def __init__(self, provider: Any, config: SessionConfig, *,
                 on_event: Callable[[dict[str, Any]], None] | None = None):
        self.provider = provider
        self.config = config
        self.on_event = on_event
        self._run_lock = threading.Lock()

    def run(self, question: str, context: str = "") -> dict[str, Any]:
        """Return a public report, including explicit partial failures.

        The token and duration limits are observed stopping thresholds. Usage
        from already in-flight calls may exceed them; this is not a strict cost
        cap. No calls start after an observed threshold has been reached.
        """
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("a DebateEngine instance cannot run concurrently")
        try:
            self._reset(question, context)
            try:
                self._run_protocol()
            except KeyboardInterrupt:
                self._stop_reason = "cancelled"
                self._error("cancelled", "Run cancelled; in-flight provider billing may be unknown")
            except Exception as exc:
                # Unknown implementation/provider failures must never look like
                # consensus. Avoid exposing arbitrary exception text or secrets.
                self._stop_reason = "engine_error"
                self._error("engine_error", f"Debate interrupted by {type(exc).__name__}; no success was inferred")
            return self._finish()
        finally:
            self._run_lock.release()

    def _reset(self, question: str, context: str) -> None:
        self._started = time.monotonic()
        self._started_at = _utc_now()
        self._run_id = uuid.uuid4().hex
        self._question = question
        self._context = context
        self.histories: dict[str, list[dict[str, str]]] = {"pro": [], "con": []}
        self._events: list[dict[str, Any]] = []
        self._errors: list[dict[str, Any]] = []
        self._callback_enabled = self.on_event is not None
        self._proposal: dict[str, Any] | None = None
        self._last_reviewed_proposal: dict[str, Any] | None = None
        self._risk_scan: dict[str, Any] | None = None
        self._last_review: dict[str, Any] | None = None
        self._proposal_history: list[dict[str, Any]] = []
        self._review_history: list[dict[str, Any]] = []
        self._issues: dict[str, dict[str, Any]] = {}
        self._exchanges: list[dict[str, Any]] = []
        self._clarification_questions: list[str] = []
        self._stop_reason = ""
        self._rounds_completed = 0
        self._models_seen: list[str] = []
        self._calls: list[dict[str, Any]] = []
        self._usage = {
            "calls": 0,
            "completed_calls": 0,
            "failed_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "max_calls": 2 * self.config.max_rounds + 1,
            "max_total_tokens": self.config.max_total_tokens,
            "threshold_exceeded": False,
            "unknown_usage_calls": 0,
        }
        self._last_fingerprint = ""
        self._unchanged_rounds = 0

    def _emit(self, event_type: str, **details: Any) -> None:
        event = {"type": event_type, "timestamp": _utc_now(), **details}
        self._events.append(event)
        if self._callback_enabled and self.on_event is not None:
            try:
                self.on_event(copy.deepcopy(event))
            except Exception:
                self._callback_enabled = False
                self._errors.append({
                    "code": "event_callback_error",
                    "message": "Progress callback failed; debate continued without it",
                })

    def _error(self, code: str, message: str, **details: Any) -> None:
        error = {"code": code, "message": message, **details}
        self._errors.append(error)
        self._emit("error", **error)

    def _limit_reason(self, new_calls: int = 1) -> str:
        if self._usage["total_tokens"] >= self.config.max_total_tokens:
            return "budget_limit"
        if time.monotonic() - self._started >= self.config.max_duration_seconds:
            return "time_limit"
        if self._usage["calls"] + new_calls > self._usage["max_calls"]:
            return "call_limit"
        return ""

    def _prepare_call(self, role: str, phase: str, round_number: int,
                      payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        message = {"role": "user", "content": task_message(phase, payload)}
        self.histories[role].append(message)
        self._usage["calls"] += 1
        call = {
            "call_number": self._usage["calls"],
            "role": role,
            "phase": phase,
            "round": round_number,
            "status": "started",
        }
        self._calls.append(call)
        self._emit("call_started", **call)
        return {
            "role": role,
            "phase": phase,
            "round_number": round_number,
            "instructions": instructions_for(role, phase),
            "messages": copy.deepcopy(self.histories[role]),
            "schema": copy.deepcopy(schema),
            "config": self.config,
        }

    def _record_completion(self, completion: Any, call: dict[str, Any],
                           schema: dict[str, Any]) -> dict[str, Any] | None:
        usage_recorded = False
        try:
            input_tokens = completion.input_tokens
            output_tokens = completion.output_tokens
            if type(input_tokens) is not int or type(output_tokens) is not int or min(input_tokens, output_tokens) < 0:
                raise DebateProtocolError("provider returned invalid token usage")
            self._usage["input_tokens"] += input_tokens
            self._usage["output_tokens"] += output_tokens
            self._usage["total_tokens"] += input_tokens + output_tokens
            self._usage["threshold_exceeded"] = self._usage["total_tokens"] > self.config.max_total_tokens
            self._usage["completed_calls"] += 1
            usage_recorded = True
            call.update({"input_tokens": input_tokens, "output_tokens": output_tokens})
            model = completion.model
            if not isinstance(model, str) or not model.strip():
                raise DebateProtocolError("provider omitted its reported model identity")
            call["returned_model"] = model
            if model not in self._models_seen:
                self._models_seen.append(model)
            if len(self._models_seen) > 1:
                self._stop_reason = "model_drift"
                raise DebateProtocolError("provider reported different models across debate calls")
            response_id = getattr(completion, "response_id", "")
            if not isinstance(response_id, str):
                raise DebateProtocolError("provider returned an invalid response ID")
            call["response_id"] = response_id
            data = completion.data
            validate_schema(data, schema)
            result = copy.deepcopy(data)
            self.histories[call["role"]].append({
                "role": "assistant", "content": json.dumps(result, ensure_ascii=False),
            })
            call["status"] = "completed"
            self._emit("call_completed", **call)
            return result
        except (AttributeError, SchemaError, DebateProtocolError) as exc:
            if not usage_recorded:
                self._usage["unknown_usage_calls"] += 1
            call["status"] = "invalid"
            self._stop_reason = self._stop_reason or "invalid_response"
            self._error(self._stop_reason, str(exc), role=call["role"], phase=call["phase"], round=call["round"])
            return None

    def _record_provider_failure(self, exc: Exception, call: dict[str, Any]) -> None:
        from .provider import ProviderError

        call["status"] = "failed"
        self._usage["failed_calls"] += 1
        self._usage["unknown_usage_calls"] += 1
        self._stop_reason = self._stop_reason or "provider_error"
        message = str(exc)[:1000] if isinstance(exc, ProviderError) else "Provider call failed; no debate turn was accepted"
        self._error("provider_error", message, role=call["role"], phase=call["phase"], round=call["round"])

    def _call(self, role: str, phase: str, round_number: int,
              payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any] | None:
        limit = self._limit_reason()
        if limit:
            self._stop_reason = limit
            return None
        request = self._prepare_call(role, phase, round_number, payload, schema)
        call = self._calls[-1]
        try:
            completion = self.provider.complete(**request)
        except KeyboardInterrupt:
            call["status"] = "interrupted"
            self._usage["unknown_usage_calls"] += 1
            raise
        except Exception as exc:
            self._record_provider_failure(exc, call)
            return None
        return self._record_completion(completion, call, schema)

    def _blind_start(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        limit = self._limit_reason(new_calls=2)
        if limit:
            self._stop_reason = limit
            return None, None
        payload = {"question": self._question, "context": self._context}
        results: dict[str, dict[str, Any] | None] = {"pro": None, "con": None}
        executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="debate-agent")
        futures = {}
        interrupted = False
        try:
            for role, phase, schema in (("pro", "propose", PROPOSAL_SCHEMA), ("con", "risk_scan", RISK_SCAN_SCHEMA)):
                limit = self._limit_reason()
                if limit:
                    self._stop_reason = limit
                    break
                request = self._prepare_call(role, phase, 0 if role == "con" else 1, payload, schema)
                future = executor.submit(self.provider.complete, **request)
                futures[future] = (self._calls[-1], schema)
            for future in as_completed(futures):
                call, schema = futures[future]
                try:
                    completion = future.result()
                except Exception as exc:
                    self._record_provider_failure(exc, call)
                    continue
                results[call["role"]] = self._record_completion(completion, call, schema)
        except KeyboardInterrupt:
            interrupted = True
            for future, (call, _) in futures.items():
                if call["status"] == "started":
                    future.cancel()
                    call["status"] = "interrupted"
                    self._usage["unknown_usage_calls"] += 1
            raise
        finally:
            executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
        return results["pro"], results["con"]

    @staticmethod
    def _check_id(value: str, label: str) -> None:
        if not _ID.fullmatch(value):
            raise DebateProtocolError(f"{label} must be a short stable alphanumeric ID")

    @staticmethod
    def _require_text(value: str, label: str) -> None:
        if not value.strip():
            raise DebateProtocolError(f"{label} must include a substantive public explanation")

    def _validate_clarification(self, needs: bool, questions: list[str]) -> None:
        if len(questions) > 3:
            raise DebateProtocolError("ask at most three essential clarification questions")
        if needs and not _unique_strings(questions):
            raise DebateProtocolError("needs_clarification requires an essential question")
        if not needs and questions:
            raise DebateProtocolError("essential questions require needs_clarification")
        for question in questions:
            self._require_text(question, "clarification question")

    def _accept_proposal(self, proposal: dict[str, Any], round_number: int) -> None:
        self._validate_clarification(proposal["needs_clarification"], proposal["clarification_questions"])
        self._require_text(proposal["public_summary"], "proposal public_summary")
        option_ids: set[str] = set()
        if len(proposal["options"]) > 3:
            raise DebateProtocolError("a proposal may contain at most three options")
        for option in proposal["options"]:
            self._check_id(option["id"], "option id")
            if option["id"] in option_ids:
                raise DebateProtocolError("duplicate option ID")
            option_ids.add(option["id"])
            self._require_text(option["title"], "option title")
            self._require_text(option["approach"], "option approach")
        recommended = proposal["recommended_option_id"]
        if recommended and recommended not in option_ids:
            raise DebateProtocolError("recommended_option_id references an unknown option")
        if not proposal["needs_clarification"]:
            if not recommended:
                raise DebateProtocolError("a concrete proposal requires a recommended option")
            for name in ("problem_statement", "goal", "recommendation"):
                self._require_text(proposal[name], name)
            for name in ("success_criteria", "implementation_steps", "validation_steps"):
                if not _unique_strings(proposal[name]):
                    raise DebateProtocolError(f"a concrete proposal requires {name}")
        response_ids: set[str] = set()
        for response in proposal["responses"]:
            issue_id = response["issue_id"]
            if issue_id not in self._issues:
                raise DebateProtocolError("proposal response references an unknown issue ID")
            if issue_id in response_ids:
                raise DebateProtocolError("duplicate proposal response for an issue")
            response_ids.add(issue_id)
            self._require_text(response["summary"], "issue response summary")
            if response["action"] == "fix":
                self._require_text(response["change"], "a fix's concrete change")
            if response["action"] == "request_clarification" and not proposal["needs_clarification"]:
                raise DebateProtocolError("request_clarification response requires essential questions")
        required_ids = {key for key, issue in self._issues.items() if issue["status"] in _UNRESOLVED}
        if not proposal["needs_clarification"] and not required_ids.issubset(response_ids):
            raise DebateProtocolError("proposal omitted responses to unresolved issues")
        proposal = copy.deepcopy(proposal)
        proposal.update({"version": round_number, "round": round_number, "reviewed": False})
        self._proposal = proposal
        self._proposal_history.append(copy.deepcopy(proposal))
        for response in proposal["responses"]:
            self._issues[response["issue_id"]]["responses"].append({
                "round": round_number, "proposal_version": round_number, **copy.deepcopy(response),
            })
        self._emit("proposal", round=round_number, version=round_number,
                   public_summary=proposal["public_summary"], needs_clarification=proposal["needs_clarification"])

    def _accept_scan(self, scan: dict[str, Any]) -> None:
        self._validate_clarification(scan["needs_clarification"], scan["clarification_questions"])
        self._require_text(scan["public_summary"], "risk scan public_summary")
        if len(scan["risk_areas"]) > 5:
            raise DebateProtocolError("risk scan may include at most five risk areas")
        ids: set[str] = set()
        for risk in scan["risk_areas"]:
            self._check_id(risk["id"], "risk id")
            if risk["id"] in ids:
                raise DebateProtocolError("duplicate risk ID")
            ids.add(risk["id"])
            self._require_text(risk["concern"], "risk concern")
            self._require_text(risk["check"], "risk check")
        self._risk_scan = copy.deepcopy(scan)
        self._emit("risk_scan", role="con", public_summary=scan["public_summary"],
                   needs_clarification=scan["needs_clarification"])

    def _accept_review(self, review: dict[str, Any], round_number: int) -> None:
        if self._proposal is None:
            raise DebateProtocolError("review requires a proposal")
        if review["reviewed_version"] != self._proposal["version"]:
            raise DebateProtocolError("reviewed_version does not match the current proposal version")
        needs = review["assessment"] == "needs_clarification"
        self._validate_clarification(needs, review["clarification_questions"])
        self._require_text(review["public_summary"], "review public_summary")
        if len(review["new_issues"]) > 5:
            raise DebateProtocolError("a review may raise at most five new issues")
        new_ids: set[str] = set()
        for issue in review["new_issues"]:
            self._check_id(issue["id"], "issue id")
            if issue["id"] in self._issues or issue["id"] in new_ids:
                raise DebateProtocolError("new issue ID duplicates an existing issue")
            new_ids.add(issue["id"])
            for name in ("title", "description", "target", "resolution_criterion"):
                self._require_text(issue[name], "issue " + name)
        responses = {response["issue_id"]: response for response in self._proposal["responses"]}
        evaluated: set[str] = set()
        for evaluation in review["issue_evaluations"]:
            issue_id = evaluation["issue_id"]
            if issue_id not in self._issues:
                raise DebateProtocolError("review evaluation references an unknown issue ID")
            if issue_id in evaluated:
                raise DebateProtocolError("duplicate review evaluation for an issue")
            evaluated.add(issue_id)
            self._require_text(evaluation["rationale"], "issue evaluation rationale")
            old_status = self._issues[issue_id]["status"]
            new_status = evaluation["status"]
            if new_status in {"resolved", "accepted_risk"} and new_status != old_status and issue_id not in responses:
                raise DebateProtocolError("CON cannot close or accept an issue without PRO's current response")
            if new_status == "resolved" and issue_id in responses and responses[issue_id]["action"] in {"accept_risk", "request_clarification"}:
                raise DebateProtocolError("accepting a risk or requesting input cannot resolve an objection")
        # Previously resolved issues must be rechecked against every new
        # version: a later proposal can remove the fix that closed them.
        required = set(self._issues)
        if not needs and not required.issubset(evaluated):
            raise DebateProtocolError("review omitted evaluations of historical issues")

        # Validation above is atomic: an invalid review cannot partially mutate
        # or erase the ledger before its failure is reported.
        for evaluation in review["issue_evaluations"]:
            issue = self._issues[evaluation["issue_id"]]
            previous = issue["status"]
            issue["status"] = evaluation["status"]
            issue["last_review_round"] = round_number
            issue["resolution_rationale"] = evaluation["rationale"]
            issue["history"].append({
                "round": round_number, "from": previous, "to": evaluation["status"],
                "rationale": evaluation["rationale"],
            })
        for item in review["new_issues"]:
            issue = copy.deepcopy(item)
            issue.update({
                "status": "open", "raised_round": round_number,
                "proposal_version": self._proposal["version"],
                "last_review_round": round_number,
                "resolution_rationale": "", "responses": [],
                "history": [{"round": round_number, "from": "", "to": "open", "rationale": item["description"]}],
            })
            self._issues[issue["id"]] = issue
        self._proposal["reviewed"] = True
        self._proposal_history[-1]["reviewed"] = True
        self._last_reviewed_proposal = copy.deepcopy(self._proposal)
        self._last_review = copy.deepcopy(review)
        self._review_history.append({"round": round_number, **copy.deepcopy(review)})
        self._rounds_completed = round_number
        exchange = {
            "round": round_number,
            "proposal_version": self._proposal["version"],
            "pro_summary": self._proposal["public_summary"],
            "con_summary": review["public_summary"],
            "assessment": review["assessment"],
            "responses": copy.deepcopy(self._proposal["responses"]),
            "new_issue_ids": [item["id"] for item in review["new_issues"]],
            "evaluations": copy.deepcopy(review["issue_evaluations"]),
        }
        self._exchanges.append(exchange)
        self._emit("review", **exchange)

    def _can_converge(self, round_number: int) -> bool:
        if round_number < self.config.min_rounds or self._last_review is None or self._proposal is None:
            return False
        if not self._proposal["reviewed"] or self._last_review["assessment"] != "accept":
            return False
        for issue in self._issues.values():
            if issue["status"] in {"open", "disputed"}:
                return False
            if issue["status"] == "accepted_risk" and issue["severity"] in {"critical", "high"}:
                return False
        return True

    def _is_stalled(self) -> bool:
        assert self._proposal is not None
        substantive = {key: value for key, value in self._proposal.items()
                       if key not in {"public_summary", "responses", "version", "round", "reviewed"}}
        ledger = [{key: value for key, value in issue.items()
                   if key not in {"history", "responses", "last_review_round", "resolution_rationale"}}
                  for issue in self._issues.values()]
        fingerprint = hashlib.sha256(json.dumps(
            {"proposal": substantive, "issues": ledger}, ensure_ascii=False, sort_keys=True,
        ).encode("utf-8")).hexdigest()
        self._unchanged_rounds = self._unchanged_rounds + 1 if fingerprint == self._last_fingerprint else 0
        self._last_fingerprint = fingerprint
        return self._unchanged_rounds >= self.config.stall_rounds

    def _protocol_failure(self, exc: Exception, phase: str, round_number: int) -> None:
        self._stop_reason = "invalid_response"
        self._error("invalid_response", str(exc), phase=phase, round=round_number)

    def _run_protocol(self) -> None:
        self._emit("run_started", run_id=self._run_id,
                   model=self.config.model, reasoning_effort=self.config.reasoning_effort,
                   max_calls=self._usage["max_calls"])
        if not isinstance(self._question, str) or not isinstance(self._context, str):
            self._stop_reason = "invalid_input"
            self._error("invalid_input", "question and context must be strings")
            return
        if not self._question.strip():
            self._stop_reason = "needs_clarification"
            self._clarification_questions = ["请提供要讨论的问题，以及需要决定或修改的对象。"]
            return
        if len(self._question) + len(self._context) > self.config.max_input_chars:
            self._stop_reason = "input_limit"
            self._error("input_limit", "Combined question and context exceed max_input_chars")
            return

        proposal, scan = self._blind_start()
        # Preserve individually valid partial work even if its peer failed.
        if proposal is not None:
            try:
                self._accept_proposal(proposal, 1)
            except DebateProtocolError as exc:
                self._protocol_failure(exc, "propose", 1)
        if scan is not None:
            try:
                self._accept_scan(scan)
            except DebateProtocolError as exc:
                self._protocol_failure(exc, "risk_scan", 0)
        if self._stop_reason:
            return
        if self._proposal is None or self._risk_scan is None:
            self._stop_reason = "provider_error"
            return
        for output in (self._proposal, self._risk_scan):
            if output["needs_clarification"]:
                self._clarification_questions.extend(output["clarification_questions"])
        if self._clarification_questions:
            self._stop_reason = "needs_clarification"
            return

        for round_number in range(1, self.config.max_rounds + 1):
            if round_number > 1:
                proposal = self._call("pro", "revise", round_number, {
                    "question": self._question, "context": self._context,
                    "previous_proposal": self._proposal,
                    "independent_risk_scan": self._risk_scan,
                    "previous_review": self._last_review,
                    "issue_ledger": list(self._issues.values()),
                }, PROPOSAL_SCHEMA)
                if proposal is None:
                    return
                try:
                    self._accept_proposal(proposal, round_number)
                except DebateProtocolError as exc:
                    self._protocol_failure(exc, "revise", round_number)
                    return
                if self._proposal["needs_clarification"]:
                    self._clarification_questions = self._proposal["clarification_questions"]
                    self._stop_reason = "needs_clarification"
                    return
            review = self._call("con", "review", round_number, {
                "question": self._question, "context": self._context,
                "proposal": self._proposal,
                "independent_risk_scan": self._risk_scan,
                "issue_ledger": list(self._issues.values()),
                "round": round_number,
                "remaining_review_rounds": self.config.max_rounds - round_number,
            }, REVIEW_SCHEMA)
            if review is None:
                return
            try:
                self._accept_review(review, round_number)
            except DebateProtocolError as exc:
                self._protocol_failure(exc, "review", round_number)
                return
            if review["assessment"] == "needs_clarification":
                self._clarification_questions = review["clarification_questions"]
                self._stop_reason = "needs_clarification"
                return
            # Observe actual usage after every returned turn, including a final
            # review. A threshold stop does not imply a complete debate.
            limit = self._limit_reason(new_calls=0)
            if limit:
                self._stop_reason = limit
                return
            if self._can_converge(round_number):
                self._stop_reason = "converged"
                return
            if self._is_stalled() and round_number >= self.config.min_rounds:
                self._stop_reason = "stalled"
                return
        self._stop_reason = "round_limit"

    def _finish(self) -> dict[str, Any]:
        reason = self._stop_reason or "engine_error"
        unresolved = [issue for issue in self._issues.values() if issue["status"] != "resolved"]
        if reason == "needs_clarification":
            status, decision = "needs_clarification", "needs_clarification"
        elif reason == "converged":
            status = "completed"
            decision = "conditional" if unresolved else "ready_to_validate"
        else:
            status = "partial"
            if any(issue["severity"] in {"critical", "high"} for issue in unresolved) or (self._last_review and self._last_review["assessment"] == "blocked"):
                decision = "blocked"
            elif reason in {"invalid_input", "input_limit", "invalid_response", "model_drift", "provider_error", "engine_error", "cancelled"}:
                decision = "undetermined"
            elif self._proposal is not None and self._proposal["reviewed"]:
                decision = "conditional"
            else:
                decision = "undetermined"
        conditions = list(self._proposal["conditions"]) if self._proposal else []
        next_steps = list(self._proposal["validation_steps"]) if self._proposal else []
        if self._last_review:
            conditions.extend(self._last_review["conditions"])
            next_steps.extend(self._last_review["next_steps"])
        for issue in unresolved:
            conditions.append(f"{issue['id']} [{issue['severity']}/{issue['status']}]: {issue['title']}")
            next_steps.append(issue["resolution_criterion"])
        if self._proposal is not None and not self._proposal["reviewed"]:
            conditions.append("最新方案尚未经反方审查，不能视为双方确认的结论。")
        questions = _unique_strings(self._clarification_questions)[:3]
        if decision == "needs_clarification":
            next_steps = questions + next_steps
        if not next_steps:
            next_steps = ["根据停止原因补充信息或调整运行限制，然后继续审查；当前结果尚未验证。"]
        actual_elapsed = time.monotonic() - self._started
        elapsed = round(actual_elapsed, 3)
        self._usage.update({
            "elapsed_seconds": elapsed,
            "max_duration_seconds": self.config.max_duration_seconds,
            "duration_threshold_exceeded": actual_elapsed > self.config.max_duration_seconds,
        })
        self._emit("run_finished", run_id=self._run_id, status=status,
                   decision=decision, stop_reason=reason, rounds_completed=self._rounds_completed)
        report = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self._run_id,
            "started_at": self._started_at,
            "finished_at": _utc_now(),
            "question": self._question,
            "context": self._context,
            "config": asdict(self.config),
            "roles": ["pro", "con"],
            "model_identity": {
                "requested": self.config.model,
                "returned": self._models_seen[0] if len(self._models_seen) == 1 else None,
                "models_seen": list(self._models_seen),
                "consistent": len(self._models_seen) == 1 if self._models_seen else None,
            },
            "status": status,
            "stop_reason": reason,
            "decision": decision,
            "verification_status": "not_checked",
            "rounds_completed": self._rounds_completed,
            "proposal": self._proposal,
            "last_reviewed_proposal": self._last_reviewed_proposal,
            "proposal_history": self._proposal_history,
            "review_history": self._review_history,
            "independent_risk_scan": self._risk_scan,
            "last_review": self._last_review,
            "issues": list(self._issues.values()),
            "core_exchanges": self._exchanges,
            "clarification_questions": questions,
            "conditions": _unique_strings(conditions),
            "next_steps": _unique_strings(next_steps),
            "next_action": _unique_strings(next_steps)[0],
            "usage": self._usage,
            "calls": self._calls,
            "events": self._events,
            "errors": self._errors,
        }
        return copy.deepcopy(report)
