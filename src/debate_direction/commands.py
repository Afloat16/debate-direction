"""Local setup and installation commands; none of these starts a model call."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, EFFORTS, SessionConfig
from .providers import get_provider_preset, list_provider_presets, supported_efforts, supported_models, validate_provider_config
from .settings import default_config_path, read_profile, validate_profile, write_profile
from .skill_install import HOSTS, install_skill, skill_root

COMMANDS = ("setup", "providers", "doctor", "install-skill")


def _profile_parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"debate-direction {command}")
    parser.add_argument("--config", type=Path, help="profile path; defaults to the per-user configuration directory")
    return parser


def setup(argv: list[str]) -> int:
    parser = _profile_parser("setup")
    parser.description = "Save a provider, exact model and reasoning setting. API keys stay in environment variables."
    parser.add_argument("--provider", choices=[p["name"] for p in list_provider_presets()])
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", choices=EFFORTS)
    parser.add_argument("--base-url", help="trusted HTTPS API base; required for openai-compatible")
    parser.add_argument("--api-key-env", help="environment variable name only, never the API key itself")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing profile")
    args = parser.parse_args(argv)
    if not all((args.provider, args.model, args.reasoning_effort)):
        if not sys.stdin.isatty():
            raise ConfigError("setup needs --provider, --model and --reasoning-effort together when input is not interactive")
        print("Configure one shared provider/model/effort for both debate agents.")
        print("Available providers: " + ", ".join(p["name"] for p in list_provider_presets()))
        args.provider = args.provider or input("Provider: ").strip()
        preset = get_provider_preset(args.provider)
        models = supported_models(args.provider)
        if models and not args.model:
            print("Profiled models: " + ", ".join(models))
        args.model = args.model or input(f"Exact model ID (example: {preset.example_model}): ").strip()
        efforts = supported_efforts(args.provider, args.model)
        print("Supported settings: " + ", ".join(efforts))
        args.reasoning_effort = args.reasoning_effort or input("Reasoning setting: ").strip()
        if args.provider == "openai-compatible" and not args.base_url:
            args.base_url = input("Trusted HTTPS API base URL: ").strip()
    profile = {"provider": args.provider, "model": args.model, "reasoning_effort": args.reasoning_effort}
    for field in ("base_url", "api_key_env"):
        if getattr(args, field):
            profile[field] = getattr(args, field)
    profile = validate_profile(profile)
    preset = get_provider_preset(profile["provider"])
    validate_provider_config(preset.name, SessionConfig(model=args.model, reasoning_effort=args.reasoning_effort, provider=preset.name))
    if not (profile.get("base_url") or preset.base_url):
        raise ConfigError("openai-compatible requires --base-url")
    path = args.config.expanduser() if args.config else default_config_path()
    write_profile(path, profile, overwrite=args.overwrite)
    key_env = profile.get("api_key_env", preset.api_key_env)
    print(f"Saved configuration: {path}")
    print(f"Both agents: {preset.name} / {args.model} / {args.reasoning_effort}")
    print(f"API key environment variable: {key_env} ({'set' if os.environ.get(key_env) else 'not set'})")
    print('Next: debate-direction "What should we change, and how can we validate it?"')
    return 0


def providers(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="debate-direction providers", description="Provider presets and supported reasoning controls.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--provider", choices=[p["name"] for p in list_provider_presets()], help="show exact model profiles for one provider")
    args = parser.parse_args(argv)
    presets = list_provider_presets()
    if args.provider:
        presets = [p for p in presets if p["name"] == args.provider]
    for preset in presets:
        preset["model_profiles"] = {model: list(supported_efforts(preset["name"], model)) for model in supported_models(preset["name"])}
    if args.json:
        print(json.dumps(presets, indent=2))
    else:
        for preset in presets:
            print(f"{preset['name']} — {preset['display_name']}")
            print(f"  API key: {preset['api_key_env']}")
            print(f"  Settings: {', '.join(preset['supported_efforts'])}")
            print(f"  Example model: {preset['example_model']}")
            print(f"  {preset['notes']}")
            if args.provider:
                for model, efforts in preset["model_profiles"].items():
                    print(f"  {model}: {', '.join(efforts)}")
        print("Model-specific validation applies. No unsupported setting is silently translated.")
        if not args.provider:
            print("Use providers --provider NAME to list reviewed model profiles and their exact controls.")
    return 0


def doctor(argv: list[str]) -> int:
    parser = _profile_parser("doctor")
    parser.description = "Inspect local installation and configuration without contacting any model API."
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = args.config.expanduser() if args.config else default_config_path()
    result = {"version": __version__, "python": sys.version.split()[0], "executable": sys.executable,
              "config_path": str(path), "config_status": "not_configured", "network_checked": False,
              "hosts": {host: {"executable": shutil.which(host), "skill_path": str(skill_root(host) / "debate-direction"),
                               "skill_present": (skill_root(host) / "debate-direction" / "SKILL.md").is_file()}
                        for host in HOSTS}}
    if path.exists() or args.config:
        profile = read_profile(path)
        preset = get_provider_preset(profile["provider"])
        validate_provider_config(preset.name, SessionConfig(model=profile["model"], reasoning_effort=profile["reasoning_effort"], provider=preset.name))
        if not (profile.get("base_url") or preset.base_url):
            raise ConfigError("the openai-compatible profile needs base_url")
        key_env = profile.get("api_key_env", preset.api_key_env)
        result.update({"config_status": "configured", "provider": preset.name, "model": profile["model"],
                       "reasoning_effort": profile["reasoning_effort"], "api_key_env": key_env,
                       "api_key_present": bool(os.environ.get(key_env))})
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Debate Direction {__version__}; Python {result['python']}")
        print(f"Configuration: {result['config_status']} ({path})")
        if "provider" in result:
            print(f"Both agents: {result['provider']} / {result['model']} / {result['reasoning_effort']}")
            print(f"API key: {'set' if result['api_key_present'] else 'not set'} in {result['api_key_env']}")
        for host, info in result["hosts"].items():
            print(f"{host}: command {'found' if info['executable'] else 'not found'}; skill {'present' if info['skill_present'] else 'not installed'}")
        print("Local checks only. Host agent inheritance and live API access have not been tested by this command.")
    return 0


def install(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="debate-direction install-skill", description="Install the portable native skill without changing host model or reasoning settings.")
    parser.add_argument("--host", required=True, choices=(*HOSTS, "all"))
    parser.add_argument("--project", nargs="?", const=Path.cwd(), type=Path, help="install in this project (default: current directory) instead of per-user scope")
    parser.add_argument("--skills-dir", type=Path, help="explicit skills root for one host, including legacy or custom installations")
    parser.add_argument("--force", action="store_true", help="replace differing local content, preserving a backup")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.host == "all" and args.skills_dir:
        raise ConfigError("--skills-dir requires one specific --host")
    hosts = HOSTS if args.host == "all" else (args.host,)
    # Detect known conflicts across every selected host before changing any.
    if len(hosts) > 1:
        for host in hosts:
            install_skill(host, project=args.project, skills_dir=args.skills_dir, force=args.force, dry_run=True)
    results = []
    for host in hosts:
        try:
            result = install_skill(host, project=args.project, skills_dir=args.skills_dir, force=args.force, dry_run=args.dry_run)
        except (ConfigError, OSError) as exc:
            completed = ", ".join(r["host"] for r in results) or "none"
            raise ConfigError(f"skill installation stopped at {host}; completed hosts: {completed}. {exc}") from None
        results.append(result)
        if not args.json:
            print(f"{host}: {result['status']} at {result['path']}")
            if "backup" in result:
                print(f"Backup: {result['backup']}")
            print(f"Invoke inside {host}: {result['invocation']}")
    if args.json:
        print(json.dumps(results, indent=2))
    elif not args.dry_run:
        print("Refresh the host's skill list or open a new session to discover the skill. The host must expose two resumable agents and verifiable settings inheritance.")
    return 0


def dispatch(command: str, argv: list[str]) -> int:
    return {"setup": setup, "providers": providers, "doctor": doctor, "install-skill": install}[command](argv)
