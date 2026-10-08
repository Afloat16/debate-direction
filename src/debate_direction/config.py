"""Immutable configuration shared by both roles; never infer a UI setting."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any


class ConfigError(ValueError):
    """The caller must supply an unambiguous, supported configuration."""


EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")


@dataclass(frozen=True, slots=True)
class SessionConfig:
    model: str
    reasoning_effort: str
    max_rounds: int = 4
    min_rounds: int = 2
    max_output_tokens: int = 12000
    max_total_tokens: int = 150000
    timeout_seconds: float = 180
    stall_rounds: int = 2
    config_source: str = "explicit"
    max_duration_seconds: float = 900
    max_input_chars: int = 64000

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ConfigError("model must be a non-empty model ID; automatic UI inheritance is unavailable in the CLI")
        if self.model != self.model.strip() or any(c.isspace() for c in self.model):
            raise ConfigError("model must be an exact model ID without whitespace")
        if self.model.lower() in {"auto", "inherit", "inherited", "current", "default"}:
            raise ConfigError("supply the exact model ID; the CLI cannot resolve the current chat model")
        if self.reasoning_effort not in EFFORTS:
            raise ConfigError("reasoning_effort must be one of: " + ", ".join(EFFORTS))
        if self.config_source not in {"explicit", "session_config", "environment", "demo"}:
            raise ConfigError("config_source cannot claim native session inheritance")
        ranges = {
            "max_rounds": (1, 12), "min_rounds": (1, 12),
            "stall_rounds": (1, 12), "max_output_tokens": (256, 100000),
            "max_total_tokens": (512, 5000000), "max_input_chars": (1, 500000),
        }
        for name, (lower, upper) in ranges.items():
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ConfigError(f"{name} must be an integer in [{lower}, {upper}]")
        if self.min_rounds > self.max_rounds:
            raise ConfigError("min_rounds cannot exceed max_rounds")
        for name in ("timeout_seconds", "max_duration_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= 7200:
                raise ConfigError(f"{name} must be a finite number in [1, 7200]")


def resolve_config(
    *, model: str | None = None, reasoning_effort: str | None = None,
    session_config: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None, **limits: Any,
) -> SessionConfig:
    """Resolve a whole model/effort pair without silently mixing sources.

    A session_config is caller-supplied metadata, not proof that an external
    chat supplied it. Explicit arguments must agree with that metadata.
    Environment settings are used only when neither explicit field is given.
    """
    env = os.environ if env is None else env
    if session_config is not None:
        if not isinstance(session_config, Mapping):
            raise ConfigError("session_config must be a JSON object")
        if set(session_config) != {"model", "reasoning_effort"}:
            raise ConfigError("session_config must contain exactly model and reasoning_effort")
        resolved_model = session_config["model"]
        resolved_effort = session_config["reasoning_effort"]
        if model is not None and model != resolved_model:
            raise ConfigError("explicit model conflicts with session_config")
        if reasoning_effort is not None and reasoning_effort != resolved_effort:
            raise ConfigError("explicit reasoning_effort conflicts with session_config")
        source = "session_config"
    elif model is not None or reasoning_effort is not None:
        if model is None or reasoning_effort is None:
            raise ConfigError("supply --model and --reasoning-effort together; sources cannot be mixed")
        resolved_model, resolved_effort, source = model, reasoning_effort, "explicit"
    else:
        resolved_model = env.get("DEBATE_MODEL")
        resolved_effort = env.get("DEBATE_REASONING_EFFORT")
        if not resolved_model or not resolved_effort:
            raise ConfigError("supply --model and --reasoning-effort, --session-config, or both DEBATE_MODEL and DEBATE_REASONING_EFFORT")
        source = "environment"
    allowed = {f.name for f in fields(SessionConfig)} - {"model", "reasoning_effort", "config_source"}
    if set(limits) - allowed:
        raise ConfigError("unknown limit options: " + ", ".join(sorted(set(limits) - allowed)))
    return SessionConfig(model=resolved_model, reasoning_effort=resolved_effort,
                         config_source=source, **{k: v for k, v in limits.items() if v is not None})
