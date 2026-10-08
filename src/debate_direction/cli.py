"""Command-line entry point. Reports persist even when a debate is incomplete."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import ConfigError, EFFORTS, SessionConfig, resolve_config
from .demo import DEMO_CONTEXT, DEMO_QUESTION, DemoProvider
from .provider import OpenAIResponsesProvider, ProviderError
from .reports import DECISIONS, render_html, render_markdown


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debate-direction",
        description="Two real agent roles debate a direction; consensus is not factual verification. 双 agent 方向审查。",
        epilog="Native skill inherits the host session when supported. CLI requires an explicit model/effort pair. Reports contain your question and context; review them before sharing.",
    )
    parser.add_argument("question", nargs="?", help="the decision or ambiguous request to examine")
    parser.add_argument("--question-file", type=Path, help="read a UTF-8 question from a file")
    parser.add_argument("--context-file", type=Path, help="read supporting context (untrusted data, never executable instructions)")
    parser.add_argument("--model", help="exact Responses API model ID; no automatic fallback")
    parser.add_argument("--reasoning-effort", choices=EFFORTS, help="same effort for both roles; provider must support it")
    parser.add_argument("--session-config", type=Path, help="caller-provided JSON with model and reasoning_effort; does not read the chat UI")
    parser.add_argument("--max-rounds", type=int, default=4, help="maximum completed proposal reviews (default: 4)")
    parser.add_argument("--min-rounds", type=int, default=2, help="minimum reviews before consensus (default: 2)")
    parser.add_argument("--stall-rounds", type=int, default=2, help="repeated unchanged rounds before stopping (default: 2)")
    parser.add_argument("--max-output-tokens", type=int, default=12000, help="per-call output cap including reasoning (default: 12000)")
    parser.add_argument("--max-total-tokens", type=int, default=150000, help="reported usage stopping threshold; in-flight calls can exceed it")
    parser.add_argument("--timeout", type=float, default=180, help="per-request timeout in seconds (default: 180)")
    parser.add_argument("--max-duration", type=float, default=900, help="stop starting calls after this many seconds; in-flight calls may finish later")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), help="trusted HTTPS API base; receives your key and input")
    parser.add_argument("--out", type=Path, help="output directory (default: a new directory under ./runs)")
    parser.add_argument("--overwrite", action="store_true", help="explicitly replace existing report.md, report.json, report.html in --out")
    parser.add_argument("--quiet", action="store_true", help="suppress progress messages")
    parser.add_argument("--json", action="store_true", help="print the report as JSON to stdout; progress stays on stderr")
    parser.add_argument("--demo", action="store_true", help="fixed offline example; no question analysis and no API key needed")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _read(path: Path, max_chars: int = 64000) -> str:
    # Read a bounded amount, so accidentally selecting a huge file is harmless.
    with path.open("r", encoding="utf-8") as handle:
        value = handle.read(max_chars + 1)
    if len(value) > max_chars:
        raise ConfigError(f"input file exceeds {max_chars} characters")
    return value


def _prepare_output(path: Path, overwrite: bool) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise ConfigError("--out must be a directory")
    for name in ("report.md", "report.json", "report.html"):
        target = path / name
        if (target.exists() or target.is_symlink()) and not overwrite:
            raise ConfigError(f"{name} already exists in --out; choose a new directory or explicitly use --overwrite")
    # Check write access before spending money on live calls.
    probe = path / (".write-check-" + uuid.uuid4().hex)
    fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    probe.unlink()


def write_reports(report: dict, directory: Path, overwrite: bool = False) -> None:
    contents = {"report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                "report.md": render_markdown(report), "report.html": render_html(report)}
    for name, body in contents.items():
        target = directory / name
        if overwrite:
            temp = directory / (".pending-" + uuid.uuid4().hex)
            try:
                fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(body)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        else:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(body)


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.question is not None and args.question_file:
            raise ConfigError("use a positional question or --question-file, not both")
        if args.demo:
            if args.question is not None or args.question_file or args.context_file or args.model or args.reasoning_effort or args.session_config:
                raise ConfigError("--demo runs only its fixed example; omit question, context and model configuration")
            question, context = DEMO_QUESTION, DEMO_CONTEXT
            config = SessionConfig(model="demo-scripted", reasoning_effort="none", config_source="demo",
                                   max_rounds=args.max_rounds, min_rounds=args.min_rounds,
                                   stall_rounds=args.stall_rounds, max_output_tokens=args.max_output_tokens,
                                   max_total_tokens=args.max_total_tokens, timeout_seconds=args.timeout,
                                   max_duration_seconds=args.max_duration)
            provider = DemoProvider()
        else:
            question = _read(args.question_file) if args.question_file else args.question
            if not question or not question.strip():
                raise ConfigError("provide a question or --question-file; use --demo for the offline example")
            context = _read(args.context_file) if args.context_file else ""
            metadata = json.loads(_read(args.session_config, 4096)) if args.session_config else None
            config = resolve_config(model=args.model, reasoning_effort=args.reasoning_effort, session_config=metadata,
                                    max_rounds=args.max_rounds, min_rounds=args.min_rounds,
                                    stall_rounds=args.stall_rounds, max_output_tokens=args.max_output_tokens,
                                    max_total_tokens=args.max_total_tokens, timeout_seconds=args.timeout,
                                    max_duration_seconds=args.max_duration)
            if len(question) + len(context) > config.max_input_chars:
                raise ConfigError("question and context exceed the combined input character limit")
            provider = OpenAIResponsesProvider(api_key=os.environ.get("OPENAI_API_KEY", ""), base_url=args.base_url)
        directory = args.out or Path("runs") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
        _prepare_output(directory, args.overwrite)
        if not args.quiet:
            print("离线演示：固定案例，无真实模型调用。" if args.demo else
                  f"启动双 agent：{config.model} / {config.reasoning_effort}，最多 {config.max_rounds} 轮。", file=sys.stderr)
        def on_event(event):
            if not args.quiet and isinstance(event, dict):
                name = event.get("type", event.get("event", "event"))
                # Only coordinator metadata; do not dump question/context or raw model text.
                meta = " ".join(str(event[k]) for k in ("role", "phase", "round") if k in event)
                print(f"[{name}] {meta}".rstrip(), file=sys.stderr, flush=True)
        from .engine import DebateEngine
        report = DebateEngine(provider, config, on_event=on_event).run(question.strip(), context)
        report["demo"] = bool(args.demo)
        if args.demo:
            report["actual_model_calls"] = 0
        write_reports(report, directory, overwrite=args.overwrite)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(DECISIONS.get(report.get("decision"), "尚未形成结论"))
            print(f"停止原因：{report.get('stop_reason')}；完成 {report.get('rounds_completed', 0)} 轮。")
            print("验证状态：尚未实际核验。")
            print(f"报告：{directory.resolve() / 'report.html'}")
            print(f"数据：{directory.resolve() / 'report.json'}")
        if report.get("stop_reason") == "cancelled":
            return 130
        if report.get("status") == "partial":
            return 3
        if report.get("decision") in {"needs_clarification", "blocked", "undetermined"}:
            return 2
        return 0
    except (ConfigError, ProviderError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"debate-direction: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已取消。尚未生成可完整导出的结果。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
