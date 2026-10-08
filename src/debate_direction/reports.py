"""Deterministic reports: never ask a third model to rewrite the conclusion."""

from __future__ import annotations

import html
import json
from typing import Any

DECISIONS = {
    "ready_to_validate": "方向已收敛，进入验证", "conditional": "有条件建议，仍有保留事项",
    "blocked": "仍有阻断问题", "needs_clarification": "需要补充关键信息",
    "undetermined": "尚未形成可审查结论",
}
STOPS = {
    "consensus": "双方接受当前方向", "converged": "双方接受当前方向",
    "round_limit": "达到轮数上限", "budget_limit": "达到用量停止阈值",
    "stalled": "讨论停滞", "cancelled": "已取消", "provider_error": "模型调用未完成",
    "invalid_output": "返回结构或问题引用无效", "time_limit": "达到时间阈值",
    "needs_clarification": "缺少会影响决策的信息",
    "invalid_response": "返回结构、问题引用或方案版本无效", "model_drift": "接口报告模型发生变化",
    "input_limit": "输入超过限制", "invalid_input": "输入格式无效",
    "call_limit": "达到调用次数上限", "engine_error": "执行异常，结果未完成",
}

ASSESSMENTS = {"accept": "接受当前方向", "revise": "要求继续修订", "blocked": "存在阻断", "needs_clarification": "需要补充信息"}


def _display_proposal(report: dict) -> tuple[dict, str]:
    current = report.get("proposal") or {}
    if current and not current.get("reviewed"):
        previous = report.get("last_reviewed_proposal") or {}
        if previous:
            return previous, f"最新修订 v{current.get('version')} 尚未复核；以下展示最后完成审查的 v{previous.get('version')}。"
        return current, "以下仅为正方候选提案，尚未经反方完整审查。"
    return current, f"展示已完成审查的方案 v{current.get('version')}。" if current else "尚未形成方案。"


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
    return ["- " + _md(v) for v in values or []] or ["- 暂无记录。"]


def render_markdown(report: dict) -> str:
    config, usage = report.get("config", {}), report.get("usage", {})
    proposal, version_note = _display_proposal(report)
    decision = report.get("decision", "undetermined")
    lines = ["# 方向辩论 · 决策报告", "",
             f"**结论：{DECISIONS.get(decision, _md(decision))}**", ""]
    if report.get("demo"):
        lines += ["> 固定离线演示：全部内容来自脚本示例，没有调用模型，也没有分析你自己的问题。", ""]
    lines += ["## 问题与当前建议", "", _md(report.get("question", "")), "",
              _md(proposal.get("recommendation", "当前没有经过完整审查的建议。")), "",
              "**版本状态：** " + _md(version_note), "",
              "**验证状态：尚未实际核验。** 本报告记录论证与修订；共识不等于事实正确或测试通过。", "",
              f"**停止原因：** {STOPS.get(report.get('stop_reason'), _md(report.get('stop_reason', 'unknown')))}。", "",
              "## 核心交锋", ""]
    if report.get("independent_risk_scan"):
        lines += ["**反方独立开场：** " + _md(report["independent_risk_scan"].get("public_summary", "")), ""]
    for index, exchange in enumerate(report.get("core_exchanges", []), 1):
        lines += [f"### 第 {exchange.get('round', index)} 轮 · 方案 v{exchange.get('proposal_version', index)}", ""]
        if isinstance(exchange, dict):
            lines += [f"- **正方：** {_md(exchange.get('pro_summary', ''))}",
                      f"- **反方：** {_md(exchange.get('con_summary', ''))}",
                      f"- **本轮判断：** {_md(ASSESSMENTS.get(exchange.get('assessment'), exchange.get('assessment', '')))}"]
            for response in exchange.get("responses", []):
                lines += [f"- **回应 {_md(response.get('issue_id', ''))}：** {_md(response.get('summary', ''))} {_md(response.get('change', ''))}"]
            if exchange.get("new_issue_ids"):
                lines += ["- **新增异议：** " + _md("、".join(exchange["new_issue_ids"]))]
        else:
            lines += [_md(exchange)]
        lines += [""]
    if not report.get("core_exchanges"):
        lines += ["尚未完成双方交锋。", ""]
    lines += ["## 当前方案", "", "### 实施步骤", "", *_items(proposal.get("implementation_steps")), "",
              "### 验收与后续验证", "", *_items(proposal.get("validation_steps")), "",
              "### 前提和成立条件", "", *_items(list(dict.fromkeys(proposal.get("assumptions", []) + proposal.get("conditions", []) + report.get("conditions", [])))), "",
              "## 异议记录", ""]
    for issue in report.get("issues", []):
        lines += [f"### {_md(issue.get('id', '?'))} · {_md(issue.get('title', '异议'))}", "",
                  f"- **级别 / 状态：** {_md(issue.get('severity', '?'))} / {_md(issue.get('status', 'open'))}",
                  f"- **问题：** {_md(issue.get('description', issue.get('concern', '')))}",
                  f"- **解除条件：** {_md(issue.get('resolution_criterion', ''))}"]
        for key in ("resolution_rationale",):
            if issue.get(key):
                lines += [f"- **最新处理理由：** {_md(issue[key])}"]
        for item in issue.get("history", []):
            lines += [f"- **第 {_md(item.get('round'))} 轮 → {_md(item.get('to'))}：** {_md(item.get('rationale', ''))}"]
        lines += [""]
    if not report.get("issues"):
        lines += ["没有已登记异议；这不证明方案没有问题。", ""]
    lines += ["## 待补充信息", "", *_items(report.get("clarification_questions")), "",
              "## 下一步", "", *_items(report.get("next_steps")), "",
              "## 运行记录", "",
              f"- 请求模型：{_md(config.get('model', 'unknown'))}",
              f"- 思考强度：{_md(config.get('reasoning_effort', 'unknown'))}",
              f"- 配置来源：{_md(config.get('config_source', 'unknown'))}；CLI 不读取 ChatGPT 界面选择。",
              f"- 接口报告模型：{_md(report.get('model_identity', {}).get('returned', 'unknown'))}",
              f"- 已完成审查轮数：{_md(report.get('rounds_completed', 0))}",
              f"- Provider 调用次数：{_md(usage.get('calls', 0))}" + ("（脚本演示，真实模型调用为 0）" if report.get("demo") else ""),
              f"- 已报告 token 用量：{_md(usage.get('total_tokens', 0))}；阈值：{_md(usage.get('max_total_tokens', config.get('max_total_tokens', 0)))}",
              "- 用量阈值在返回后检查，可能被正在进行的调用超过；错误请求的未报告用量未知。",
              "- 实际工具验证：无；没有自动检索网页、执行代码或替你修改系统。", ""]
    if report.get("errors"):
        lines += ["## 未完成事项 / 错误", "", *_items(report["errors"]), ""]
    return "\n".join(lines)


def render_html(report: dict) -> str:
    """Self-contained, script-free report. All untrusted values are escaped."""
    esc = lambda v: html.escape(_text(v), quote=True)
    decision = report.get("decision", "undetermined")
    config, usage = report.get("config", {}), report.get("usage", {})
    proposal, version_note = _display_proposal(report)
    decision_title = DECISIONS.get(decision, decision)
    def lst(values):
        return "<ul>" + "".join("<li>" + esc(v) + "</li>" for v in values or ["暂无记录。"] ) + "</ul>"
    exchanges = []
    for i, exchange in enumerate(report.get("core_exchanges", []), 1):
        if isinstance(exchange, dict):
            body = f'<dt>正方 · 方案 v{esc(exchange.get("proposal_version", i))}</dt><dd>{esc(exchange.get("pro_summary", ""))}</dd><dt>反方 · {esc(ASSESSMENTS.get(exchange.get("assessment"), exchange.get("assessment", "")))}</dt><dd>{esc(exchange.get("con_summary", ""))}</dd>'
            for response in exchange.get("responses", []):
                body += f'<dt>回应 {esc(response.get("issue_id", ""))}</dt><dd>{esc(response.get("summary", ""))} {esc(response.get("change", ""))}</dd>'
            if exchange.get("new_issue_ids"):
                body += f'<dt>新增异议</dt><dd>{esc("、".join(exchange["new_issue_ids"]))}</dd>'
        else:
            body = f"<dd>{esc(exchange)}</dd>"
        exchanges.append(f'<article class="exchange"><span class="round">{i:02}</span><dl>{body}</dl></article>')
    issue_cards = []
    for issue in report.get("issues", []):
        status = issue.get("status", "open")
        issue_cards.append(f'<article class="issue"><div class="issue-head"><strong>{esc(issue.get("id", "?"))} · {esc(issue.get("title", "异议"))}</strong><span class="pill">{esc(issue.get("severity", ""))} / {esc(status)}</span></div><p>{esc(issue.get("description", ""))}</p><p class="muted">解除条件：{esc(issue.get("resolution_criterion", ""))}</p>' + (f'<details><summary>处理记录</summary><pre>{esc(json.dumps(issue.get("history", issue.get("resolution", [])), ensure_ascii=False, indent=2))}</pre></details>' if issue.get("history") or issue.get("resolution") else "") + "</article>")
    demo = '<div class="demo">固定离线演示 · 脚本示例 · 真实模型调用 0 次</div>' if report.get("demo") else ""
    errors = f'<section><h2>未完成事项</h2>{lst(report["errors"])}</section>' if report.get("errors") else ""
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>方向辩论 · 决策报告</title><style>
:root{{color-scheme:light;--ink:#172c38;--muted:#596c75;--teal:#116a65;--line:#d6e2e0;--paper:#f4f7f5}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.8 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1050px;margin:auto;padding:48px 28px 70px}}header{{border-bottom:1px solid var(--line);padding-bottom:30px}}.eyebrow{{letter-spacing:.15em;font-size:12px;font-weight:800;color:var(--teal)}}h1{{font-size:clamp(30px,5vw,48px);line-height:1.2;margin:12px 0}}h2{{font-size:24px;margin:0 0 20px}}h3{{font-size:17px}}p{{overflow-wrap:anywhere}}.subtitle,.muted{{color:var(--muted)}}.demo{{background:#fff0c7;color:#644913;padding:12px 18px;border-radius:8px;margin:20px 0}}.hero{{padding:30px;background:white;border:1px solid var(--line);border-left:5px solid var(--teal);border-radius:12px;margin:28px 0}}.hero h2{{font-size:28px;line-height:1.4;margin:10px 0}}.notice{{font-size:14px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}section{{margin-top:34px}}.panel{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px}}ul{{padding-left:22px;margin:0}}li{{margin:9px 0;overflow-wrap:anywhere}}.exchange{{display:flex;gap:20px;padding:20px 0;border-top:1px solid var(--line)}}.round{{font-size:24px;color:var(--teal);font-weight:750;min-width:34px}}dl{{margin:0;min-width:0}}dt{{font-weight:700;font-size:13px;color:var(--teal)}}dd{{margin:0 0 12px;overflow-wrap:anywhere}}.issue{{background:white;border:1px solid var(--line);border-radius:10px;padding:22px;margin:12px 0}}.issue-head{{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap}}.pill{{font-size:12px;background:#edf3f2;color:#274c49;padding:3px 10px;border-radius:99px}}details{{color:var(--muted);font-size:14px}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.stat{{border-top:2px solid var(--line);padding-top:12px;overflow-wrap:anywhere}}.stat b{{display:block;font-size:18px}}.stat span{{font-size:12px;color:var(--muted)}}footer{{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}}@media(max-width:650px){{main{{padding:28px 18px}}.grid{{grid-template-columns:1fr}}.hero{{padding:22px}}.stats{{grid-template-columns:1fr 1fr}}}}@media print{{body{{background:white}}main{{padding:12px}}.panel,.issue,.exchange{{break-inside:avoid}}details{{display:none}}}}
</style></head><body><main>
<header><div class="eyebrow">DEBATE DIRECTION / 双 AGENT 方案审查</div><h1>把模糊需求，变成可验证的方向。</h1><p class="subtitle">记录提出、质疑与修订，也保留没有解决的问题。</p></header>{demo}
<section class="hero"><div class="eyebrow">{esc(decision_title)}</div><h2>{esc(proposal.get("recommendation", "尚未形成完整建议。"))}</h2><p>{esc(report.get("question", ""))}</p><p class="notice">{esc(version_note)}</p><p class="notice">尚未实际核验 · {esc(STOPS.get(report.get("stop_reason"), report.get("stop_reason", "unknown")))}。双方认同并不证明方案正确或测试通过。</p></section>
<section><h2>核心交锋</h2><p class="muted">反方独立开场：{esc((report.get("independent_risk_scan") or {}).get("public_summary", "尚无完整记录。"))}</p>{''.join(exchanges) or '<p>尚未完成双方交锋。</p>'}</section>
<div class="grid"><section class="panel"><h2>实施步骤</h2>{lst(proposal.get("implementation_steps"))}</section><section class="panel"><h2>后续验证</h2>{lst(proposal.get("validation_steps"))}</section></div>
<section><h2>异议记录</h2>{''.join(issue_cards) or '<p>没有已登记异议；这不证明方案没有问题。</p>'}</section>
<div class="grid"><section class="panel"><h2>前提与条件</h2>{lst(list(dict.fromkeys(proposal.get("assumptions", []) + proposal.get("conditions", []) + report.get("conditions", []))))}</section><section class="panel"><h2>需要你补充</h2>{lst(report.get("clarification_questions"))}<h3>下一步</h3>{lst(report.get("next_steps"))}</section></div>
{errors}<section><h2>运行记录</h2><div class="stats"><div class="stat"><b>{esc(config.get("model", "unknown"))}</b><span>双方请求同一模型</span></div><div class="stat"><b>{esc(config.get("reasoning_effort", "unknown"))}</b><span>双方请求同一思考强度</span></div><div class="stat"><b>{esc(report.get("rounds_completed", 0))} 轮</b><span>已完成交锋</span></div><div class="stat"><b>{esc(usage.get("calls", 0))}</b><span>Provider 调用{'（脚本示例）' if report.get('demo') else ''}</span></div><div class="stat"><b>{esc(usage.get("total_tokens", 0))}</b><span>接口已报告 token</span></div><div class="stat"><b>{esc(config.get("config_source", "unknown"))}</b><span>配置来源</span></div></div><p class="notice">CLI 不读取聊天界面的模型选择。接口报告模型：{esc(report.get("model_identity", {}).get("returned", "unknown"))}。用量阈值在返回后检查，进行中的调用可能超过阈值；错误请求的未报告用量未知。</p></section>
<footer>Debate Direction · 公开论据摘要，不包含隐藏思考链。本程序不自动检索网页或执行测试；所有验证步骤都需要另行完成。</footer></main></body></html>'''
