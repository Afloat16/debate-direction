"""Portable, non-secret CLI profiles. Credentials remain in the environment."""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .config import ConfigError, SessionConfig, resolve_config


class _DefaultProfileHomeUnavailable(ConfigError):
    """Only automatic profile discovery may ignore an unavailable home."""


def expand_config_path(path: Path) -> Path:
    """Expand a selected profile path without leaking home-resolution errors."""
    try:
        return path.expanduser()
    except RuntimeError:
        raise ConfigError(
            "could not expand the configuration path; set DEBATE_CONFIG or use --config with an absolute path"
        ) from None


def default_config_path() -> Path:
    explicit = os.environ.get("DEBATE_CONFIG")
    if explicit:
        return expand_config_path(Path(explicit))
    try:
        if sys.platform == "win32":
            root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support"
        else:
            root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    except RuntimeError:
        raise _DefaultProfileHomeUnavailable(
            "could not determine the default configuration directory; set DEBATE_CONFIG or use --config with an absolute path"
        ) from None
    return root / "debate-direction" / "config.json"


def validate_profile(profile: object) -> dict:
    if not isinstance(profile, dict):
        raise ConfigError("profile must be a JSON object")
    allowed = {"provider", "model", "reasoning_effort", "base_url", "api_key_env"}
    if set(profile) - allowed:
        raise ConfigError("profile accepts only provider, model, reasoning_effort, base_url and api_key_env; never store API keys")
    if not {"provider", "model", "reasoning_effort"} <= set(profile):
        raise ConfigError("profile requires provider, model and reasoning_effort together")
    for key, value in profile.items():
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ConfigError(f"profile {key} must be a non-empty string without surrounding whitespace")
    SessionConfig(model=profile["model"], reasoning_effort=profile["reasoning_effort"], provider=profile["provider"])
    if "base_url" in profile:
        if any(c.isspace() or ord(c) < 32 for c in profile["base_url"]):
            raise ConfigError("base_url must not contain whitespace or control characters")
        try:
            parts = urlsplit(profile["base_url"])
            parts.port
        except ValueError:
            raise ConfigError("base_url must be a valid HTTPS URL with a valid port") from None
        if parts.scheme != "https" or not parts.hostname or parts.username is not None or parts.password is not None or parts.query or parts.fragment:
            raise ConfigError("base_url must be HTTPS without credentials, query parameters or a fragment")
    if "api_key_env" in profile and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", profile["api_key_env"]):
        raise ConfigError("api_key_env must name an environment variable, not contain a key")
    return dict(profile)


def read_profile(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = handle.read(16385)
        if len(raw) > 16384:
            raise ConfigError("profile exceeds 16 KiB")
        return validate_profile(json.loads(raw))
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(f"could not read a valid profile at {path}") from None


def write_profile(path: Path, profile: dict, *, overwrite: bool = False) -> None:
    profile = validate_profile(profile)
    if path.is_symlink():
        raise ConfigError("refusing to replace a profile through a symbolic link")
    if path.exists() and not overwrite:
        if read_profile(path) == profile:
            return
        raise ConfigError("a different profile already exists; use setup --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.parent / (".debate-config-" + uuid.uuid4().hex)
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(profile, handle, indent=2)
            handle.write("\n")
        if overwrite:
            os.replace(temp, path)
        else:
            # An exclusive destination prevents a concurrent setup from being
            # overwritten. The profile contains settings only, never a key.
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                raise ConfigError("profile appeared during setup; no existing file was overwritten") from None
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(temp.read_text(encoding="utf-8"))
    finally:
        temp.unlink(missing_ok=True)


def resolve_runtime(args, *, limits: dict | None = None) -> tuple[SessionConfig, dict]:
    """Never combine a saved model/effort pair with a different explicit provider."""
    env = os.environ
    requested = {"provider": args.provider, "model": args.model,
                 "reasoning_effort": args.reasoning_effort,
                 "base_url": args.base_url, "api_key_env": args.api_key_env}
    explicit_pair = args.model is not None or args.reasoning_effort is not None or args.session_config is not None
    env_pair = any(env.get(k) for k in ("DEBATE_MODEL", "DEBATE_REASONING_EFFORT", "DEBATE_PROVIDER"))
    path = None
    selected_profile = args.config is not None
    if selected_profile:
        path = expand_config_path(args.config)
    elif not explicit_pair and args.provider is None and not env_pair:
        # Resolving the default location is unnecessary when runtime settings
        # already select another source. A missing OS home only makes automatic
        # discovery unavailable; explicitly configured path errors still matter.
        selected_profile = bool(env.get("DEBATE_CONFIG"))
        try:
            path = default_config_path()
        except _DefaultProfileHomeUnavailable:
            if selected_profile:
                raise
    if path is not None and (selected_profile or path.exists()):
        profile = read_profile(path)
        for key, value in requested.items():
            if value is not None and value != profile.get(key):
                raise ConfigError(f"explicit {key} conflicts with the selected profile; supply a new complete configuration or update setup")
        if args.session_config is not None:
            raise ConfigError("use --config or --session-config, not both")
        config = SessionConfig(model=profile["model"], reasoning_effort=profile["reasoning_effort"],
                               provider=profile["provider"], config_source="saved_profile", **(limits or {}))
        return config, profile
    provider = args.provider or env.get("DEBATE_PROVIDER") or "openai"
    metadata = None
    if args.session_config is not None:
        try:
            with args.session_config.open("r", encoding="utf-8") as handle:
                raw = handle.read(4097)
            if len(raw) > 4096:
                raise ConfigError("session config exceeds 4 KiB")
            metadata = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ConfigError("could not read the session configuration") from None
    config = resolve_config(model=args.model, reasoning_effort=args.reasoning_effort,
                            session_config=metadata, provider=provider, **(limits or {}))
    profile = {"provider": provider, "model": config.model, "reasoning_effort": config.reasoning_effort}
    base_url = args.base_url or (env.get("OPENAI_BASE_URL") if provider == "openai" else None)
    if base_url:
        profile["base_url"] = base_url
    if args.api_key_env:
        profile["api_key_env"] = args.api_key_env
    return config, validate_profile(profile)
