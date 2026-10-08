"""Deterministic reports: never ask a third model to rewrite the conclusion."""

from __future__ import annotations

import html
import json
from typing import Any

DECISIONS = {
    "ready_to_validate": "Direction agreed; ready for validation", "conditional": "Conditional recommendation; reservations remain",
    "blocked": "Blocking issues remain", "needs_clarification": "Essential information needed",
    "undetermined": "No reviewable conclusion yet",
}
STOPS = {
    "consensus": "Both agents accept the current direction", "converged": "Both agents accept the current direction",
    "round_limit": "Round limit reached", "budget_limit": "Usage stop threshold reached",
    "stalled": "Discussion stalled", "cancelled": "Cancelled", "provider_error": "Model call did not complete",
    "invalid_output": "Invalid response structure or issue references", "time_limit": "Time threshold reached",
    "needs_clarification": "Information needed to make the decision is missing",
    "invalid_response": "Invalid response structure, issue references or proposal version", "model_drift": "The provider reported a different model",
    "input_limit": "Input limit exceeded", "invalid_input": "Invalid input format",
    "call_limit": "Call limit reached", "engine_error": "Execution interrupted; result incomplete",
}

ASSESSMENTS = {"accept": "Accept the current direction", "revise": "Further revision required", "blocked": "Blocking issues identified", "needs_clarification": "More information required"}


def _display_proposal(report: dict) -> tuple[dict, str]:
    current = report.get("proposal") or {}
    if current and not current.get("reviewed"):
        previous = report.get("last_reviewed_proposal") or {}
        if previous:
            return previous, f"The latest revision v{current.get('version')} has not been reviewed; showing the last reviewed proposal, v{previous.get('version')}."
        return current, "This is a candidate proposal from Pro and has not been reviewed in full by Con."
    return current, f"Showing reviewed proposal v{current.get('version')}." if current else "No proposal yet."


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _md(value: Any) -> str:
    # Keep model/user text as literal content, not active HTML/Markdown links.
    text = html.escape(_text(value), quote=False).replace("\\", "\\\\")
    for char in "`*_{}[]()#+!|":
        text = text.replace(char, "\\" + char)
    return text.replace("\r", "").replace("\n", " ")


def _items(values: list | None) -> list[str]:
    return ["- " + _md(v) for v in values or []] or ["- No entries yet."]


def render_markdown(report: dict) -> str:
    config, usage = report.get("config", {}), report.get("usage", {})
    proposal, version_note = _display_proposal(report)
    decision = report.get("decision", "undetermined")
    lines = ["# Debate Direction · Decision Report", "",
             f"**Decision: {DECISIONS.get(decision, _md(decision))}**", ""]
    if report.get("demo"):
        lines += ["> Fixed offline demo: all content comes from a scripted example. No models were called, and your own question was not analyzed.", ""]
    lines += ["## Question and current recommendation", "", _md(report.get("question", "")), "",
              _md(proposal.get("recommendation", "No fully reviewed recommendation is available yet.")), "",
              "**Version status:** " + _md(version_note), "",
              "**Verification status: Not independently verified.** This report records arguments and revisions; agreement does not establish factual correctness or passing tests.", "",
              f"**Stop reason:** {STOPS.get(report.get('stop_reason'), _md(report.get('stop_reason', 'unknown')))}.", "",
              "## Core exchanges", ""]
    if report.get("independent_risk_scan"):
        lines += ["**Con's independent opening:** " + _md(report["independent_risk_scan"].get("public_summary", "")), ""]
    for index, exchange in enumerate(report.get("core_exchanges", []), 1):
        lines += [f"### Round {exchange.get('round', index)} · Proposal v{exchange.get('proposal_version', index)}", ""]
        if isinstance(exchange, dict):
            lines += [f"- **Pro:** {_md(exchange.get('pro_summary', ''))}",
                      f"- **Con:** {_md(exchange.get('con_summary', ''))}",
                      f"- **Round assessment:** {_md(ASSESSMENTS.get(exchange.get('assessment'), exchange.get('assessment', '')))}"]
            for response in exchange.get("responses", []):
                lines += [f"- **Response to {_md(response.get('issue_id', ''))}:** {_md(response.get('summary', ''))} {_md(response.get('change', ''))}"]
            if exchange.get("new_issue_ids"):
                lines += ["- **New objections:** " + _md(", ".join(exchange["new_issue_ids"]))]
        else:
            lines += [_md(exchange)]
        lines += [""]
    if not report.get("core_exchanges"):
        lines += ["No exchange between both agents has been completed yet.", ""]
    lines += ["## Current proposal", "", "### Implementation steps", "", *_items(proposal.get("implementation_steps")), "",
              "### Acceptance checks and further validation", "", *_items(proposal.get("validation_steps")), "",
              "### Assumptions and conditions", "", *_items(list(dict.fromkeys(proposal.get("assumptions", []) + proposal.get("conditions", []) + report.get("conditions", [])))), "",
              "## Objection log", ""]
    for issue in report.get("issues", []):
        lines += [f"### {_md(issue.get('id', '?'))} · {_md(issue.get('title', 'Objection'))}", "",
                  f"- **Severity / status:** {_md(issue.get('severity', '?'))} / {_md(issue.get('status', 'open'))}",
                  f"- **Issue:** {_md(issue.get('description', issue.get('concern', '')))}",
                  f"- **Resolution criterion:** {_md(issue.get('resolution_criterion', ''))}"]
        for key in ("resolution_rationale",):
            if issue.get(key):
                lines += [f"- **Latest decision rationale:** {_md(issue[key])}"]
        for item in issue.get("history", []):
            lines += [f"- **Round {_md(item.get('round'))} → {_md(item.get('to'))}:** {_md(item.get('rationale', ''))}"]
        lines += [""]
    if not report.get("issues"):
        lines += ["No objections have been logged; this does not prove the proposal is free of problems.", ""]
    lines += ["## Information needed", "", *_items(report.get("clarification_questions")), "",
              "## Next steps", "", *_items(report.get("next_steps")), "",
              "## Run record", "",
              f"- Requested model: {_md(config.get('model', 'unknown'))}",
              f"- Reasoning effort: {_md(config.get('reasoning_effort', 'unknown'))}",
              f"- Configuration source: {_md(config.get('config_source', 'unknown'))}; the CLI does not read selections from the ChatGPT interface.",
              f"- Provider-reported model: {_md(report.get('model_identity', {}).get('returned', 'unknown'))}",
              f"- Completed review rounds: {_md(report.get('rounds_completed', 0))}",
              f"- Provider calls: {_md(usage.get('calls', 0))}" + (" (scripted demo; actual model calls: 0)" if report.get("demo") else ""),
              f"- Reported token usage: {_md(usage.get('total_tokens', 0))}; threshold: {_md(usage.get('max_total_tokens', config.get('max_total_tokens', 0)))}",
              "- The usage threshold is checked after responses return and may be exceeded by calls already in progress; unreported usage from failed requests is unknown.",
              "- Actual tool validation: none. This program does not automatically browse the web, execute code or modify your systems.", ""]
    if report.get("errors"):
        lines += ["## Incomplete items / errors", "", *_items(report["errors"]), ""]
    return "\n".join(lines)


def render_html(report: dict) -> str:
    """Self-contained, script-free report. All untrusted values are escaped."""
    esc = lambda v: html.escape(_text(v), quote=True)
    decision = report.get("decision", "undetermined")
    config, usage = report.get("config", {}), report.get("usage", {})
    proposal, version_note = _display_proposal(report)
    decision_title = DECISIONS.get(decision, decision)
    def lst(values):
        return "<ul>" + "".join("<li>" + esc(v) + "</li>" for v in values or ["No entries yet."] ) + "</ul>"
    exchanges = []
    for i, exchange in enumerate(report.get("core_exchanges", []), 1):
        if isinstance(exchange, dict):
            body = f'<dt>Pro · Proposal v{esc(exchange.get("proposal_version", i))}</dt><dd>{esc(exchange.get("pro_summary", ""))}</dd><dt>Con · {esc(ASSESSMENTS.get(exchange.get("assessment"), exchange.get("assessment", "")))}</dt><dd>{esc(exchange.get("con_summary", ""))}</dd>'
            for response in exchange.get("responses", []):
                body += f'<dt>Response to {esc(response.get("issue_id", ""))}</dt><dd>{esc(response.get("summary", ""))} {esc(response.get("change", ""))}</dd>'
            if exchange.get("new_issue_ids"):
                body += f'<dt>New objections</dt><dd>{esc(", ".join(exchange["new_issue_ids"]))}</dd>'
        else:
            body = f"<dd>{esc(exchange)}</dd>"
        exchanges.append(f'<article class="exchange"><span class="round">{i:02}</span><dl>{body}</dl></article>')
    issue_cards = []
    for issue in report.get("issues", []):
        status = issue.get("status", "open")
        issue_cards.append(f'<article class="issue"><div class="issue-head"><strong>{esc(issue.get("id", "?"))} · {esc(issue.get("title", "Objection"))}</strong><span class="pill">{esc(issue.get("severity", ""))} / {esc(status)}</span></div><p>{esc(issue.get("description", ""))}</p><p class="muted">Resolution criterion: {esc(issue.get("resolution_criterion", ""))}</p>' + (f'<details><summary>Resolution history</summary><pre>{esc(json.dumps(issue.get("history", issue.get("resolution", [])), ensure_ascii=False, indent=2))}</pre></details>' if issue.get("history") or issue.get("resolution") else "") + "</article>")
    demo = '<div class="demo">Fixed offline demo · Scripted example · Actual model calls: 0</div>' if report.get("demo") else ""
    errors = f'<section><h2>Incomplete items</h2>{lst(report["errors"])}</section>' if report.get("errors") else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Debate Direction · Decision Report</title><style>
:root{{color-scheme:light;--ink:#172c38;--muted:#596c75;--teal:#116a65;--line:#d6e2e0;--paper:#f4f7f5}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.8 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1050px;margin:auto;padding:48px 28px 70px}}header{{border-bottom:1px solid var(--line);padding-bottom:30px}}.eyebrow{{letter-spacing:.15em;font-size:12px;font-weight:800;color:var(--teal)}}h1{{font-size:clamp(30px,5vw,48px);line-height:1.2;margin:12px 0}}h2{{font-size:24px;margin:0 0 20px}}h3{{font-size:17px}}p{{overflow-wrap:anywhere}}.subtitle,.muted{{color:var(--muted)}}.demo{{background:#fff0c7;color:#644913;padding:12px 18px;border-radius:8px;margin:20px 0}}.hero{{padding:30px;background:white;border:1px solid var(--line);border-left:5px solid var(--teal);border-radius:12px;margin:28px 0}}.hero h2{{font-size:28px;line-height:1.4;margin:10px 0}}.notice{{font-size:14px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}section{{margin-top:34px}}.panel{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px}}ul{{padding-left:22px;margin:0}}li{{margin:9px 0;overflow-wrap:anywhere}}.exchange{{display:flex;gap:20px;padding:20px 0;border-top:1px solid var(--line)}}.round{{font-size:24px;color:var(--teal);font-weight:750;min-width:34px}}dl{{margin:0;min-width:0}}dt{{font-weight:700;font-size:13px;color:var(--teal)}}dd{{margin:0 0 12px;overflow-wrap:anywhere}}.issue{{background:white;border:1px solid var(--line);border-radius:10px;padding:22px;margin:12px 0}}.issue-head{{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap}}.pill{{font-size:12px;background:#edf3f2;color:#274c49;padding:3px 10px;border-radius:99px}}details{{color:var(--muted);font-size:14px}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.stat{{border-top:2px solid var(--line);padding-top:12px;overflow-wrap:anywhere}}.stat b{{display:block;font-size:18px}}.stat span{{font-size:12px;color:var(--muted)}}footer{{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}}@media(max-width:650px){{main{{padding:28px 18px}}.grid{{grid-template-columns:1fr}}.hero{{padding:22px}}.stats{{grid-template-columns:1fr 1fr}}}}@media print{{body{{background:white}}main{{padding:12px}}.panel,.issue,.exchange{{break-inside:avoid}}details{{display:none}}}}
</style></head><body><main>
<header><div class="eyebrow">DEBATE DIRECTION / TWO-AGENT PROPOSAL REVIEW</div><h1>Turn vague requests into a testable direction.</h1><p class="subtitle">Record proposals, challenges and revisions while keeping unresolved issues visible.</p></header>{demo}
<section class="hero"><div class="eyebrow">{esc(decision_title)}</div><h2>{esc(proposal.get("recommendation", "No complete recommendation is available yet."))}</h2><p>{esc(report.get("question", ""))}</p><p class="notice">{esc(version_note)}</p><p class="notice">Not independently verified · {esc(STOPS.get(report.get("stop_reason"), report.get("stop_reason", "unknown")))}. Agreement between both agents does not prove the proposal is correct or that tests have passed.</p></section>
<section><h2>Core exchanges</h2><p class="muted">Con's independent opening: {esc((report.get("independent_risk_scan") or {}).get("public_summary", "No complete record yet."))}</p>{''.join(exchanges) or '<p>No exchange between both agents has been completed yet.</p>'}</section>
<div class="grid"><section class="panel"><h2>Implementation steps</h2>{lst(proposal.get("implementation_steps"))}</section><section class="panel"><h2>Further validation</h2>{lst(proposal.get("validation_steps"))}</section></div>
<section><h2>Objection log</h2>{''.join(issue_cards) or '<p>No objections have been logged; this does not prove the proposal is free of problems.</p>'}</section>
<div class="grid"><section class="panel"><h2>Assumptions and conditions</h2>{lst(list(dict.fromkeys(proposal.get("assumptions", []) + proposal.get("conditions", []) + report.get("conditions", []))))}</section><section class="panel"><h2>Information needed from you</h2>{lst(report.get("clarification_questions"))}<h3>Next steps</h3>{lst(report.get("next_steps"))}</section></div>
{errors}<section><h2>Run record</h2><div class="stats"><div class="stat"><b>{esc(config.get("model", "unknown"))}</b><span>Same model requested by both agents</span></div><div class="stat"><b>{esc(config.get("reasoning_effort", "unknown"))}</b><span>Same reasoning effort requested by both agents</span></div><div class="stat"><b>{esc(report.get("rounds_completed", 0))} rounds</b><span>Completed exchanges</span></div><div class="stat"><b>{esc(usage.get("calls", 0))}</b><span>Provider calls{' (scripted example)' if report.get('demo') else ''}</span></div><div class="stat"><b>{esc(usage.get("total_tokens", 0))}</b><span>Provider-reported tokens</span></div><div class="stat"><b>{esc(config.get("config_source", "unknown"))}</b><span>Configuration source</span></div></div><p class="notice">The CLI does not read the model selection in the chat interface. Provider-reported model: {esc(report.get("model_identity", {}).get("returned", "unknown"))}. The usage threshold is checked after responses return and may be exceeded by calls already in progress; unreported usage from failed requests is unknown.</p></section>
<footer>Debate Direction · Public argument summaries, without hidden chain of thought. This program does not automatically browse the web or run tests; all validation steps require separate work.</footer></main></body></html>'''
