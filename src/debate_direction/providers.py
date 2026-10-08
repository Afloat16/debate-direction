"""Explicit provider profiles and dependency-free API adapters.

Native host agents and API transports are different integrations. These API
adapters use the caller's exact model and provider-native effort; they cannot
read a Codex or Claude Code session's settings. They never retry, choose a new
model, or translate one provider's effort scale to another provider's scale.

Some APIs require opaque thinking protocol state on later turns. It is held
only in an isolated, in-memory role history and is never part of Completion.
Call clear_session() after a run to erase it and invalidate in-flight writes.
"""

from __future__ import annotations

import copy
import json
import re
import socket
import threading
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any, Callable
from urllib.parse import urlsplit

from . import __version__
from .config import ConfigError, SessionConfig
from .provider import Completion, OpenAIResponsesProvider, ProviderError, _http_transport


_OPENAI_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
_CLAUDE_BASE_EFFORTS = ("low", "medium", "high", "max")
_CLAUDE_FULL_EFFORTS = ("low", "medium", "high", "xhigh", "max")
_GEMINI_BASE_EFFORTS = ("low", "medium", "high")
_GEMINI_MINIMAL_EFFORTS = ("minimal", "low", "medium", "high")

# These are explicit capability profiles, not aliases to another model. Unknown
# models require a reviewed profile or the caller-declared generic transport.
_MODEL_EFFORTS = MappingProxyType({
    "anthropic": MappingProxyType({
        "claude-opus-4-6": _CLAUDE_BASE_EFFORTS,
        "claude-sonnet-4-6": _CLAUDE_BASE_EFFORTS,
        "claude-mythos-preview": _CLAUDE_BASE_EFFORTS,
        **{model: _CLAUDE_FULL_EFFORTS for model in (
            "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5", "claude-opus-5-5",
            "claude-sonnet-5", "claude-sonnet-5-5", "claude-haiku-5-5",
            "claude-fable-5", "claude-fable-5-1", "claude-mythos-5", "claude-mythos-5-1",
        )},
    }),
    "deepseek": MappingProxyType({
        "deepseek-flash": ("none", "low", "high", "max"),
        "deepseek-v4-pro": ("none", "low", "high", "max"),
    }),
    "kimi": MappingProxyType({
        "kimi-k3": ("low", "high", "max"),
        "kimi-k2.7-code": ("enabled",),
        "kimi-k2.7-code-highspeed": ("enabled",),
        "kimi-k2.6": ("enabled", "disabled"),
    }),
    "gemini": MappingProxyType({
        "gemini-3.8-flash": _GEMINI_BASE_EFFORTS,
        "gemini-3.7-flash": _GEMINI_BASE_EFFORTS,
        "gemini-3.6-flash": _GEMINI_MINIMAL_EFFORTS,
        "gemini-3.5-flash": _GEMINI_MINIMAL_EFFORTS,
        "gemini-3.5-flash-lite": _GEMINI_MINIMAL_EFFORTS,
        "gemini-3.1-pro-preview": _GEMINI_BASE_EFFORTS,
        "gemini-3-flash-preview": _GEMINI_MINIMAL_EFFORTS,
        "gemini-3-pro-preview": ("low", "high"),
        "gemini-2.5-pro": _GEMINI_BASE_EFFORTS,
        "gemini-2.5-flash": ("none", "low", "medium", "high"),
        "gemini-2.5-flash-lite": ("none", "low", "medium", "high"),
    }),
})


@dataclass(frozen=True, slots=True)
class ProviderPreset:
    name: str
    display_name: str
    protocol: str
    base_url: str | None
    api_key_env: str
    example_model: str
    supported_efforts: tuple[str, ...]
    notes: str
    documentation: tuple[str, ...]


PROVIDER_PRESETS = MappingProxyType({
    preset.name: preset for preset in (
        ProviderPreset(
            "openai", "OpenAI", "responses", "https://api.openai.com/v1",
            "OPENAI_API_KEY", "gpt-6-astra", _OPENAI_EFFORTS,
            "Uses the existing Responses adapter. Model availability and accepted effort "
            "levels are checked by the API; all settings are sent unchanged.",
            ("https://platform.openai.com/docs/api-reference/responses/create",),
        ),
        ProviderPreset(
            "anthropic", "Anthropic / Claude", "messages", "https://api.anthropic.com/v1",
            "ANTHROPIC_API_KEY", "claude-sonnet-4-6", _CLAUDE_FULL_EFFORTS,
            "Uses adaptive thinking and native output_config.effort on profiled models. "
            "Older manual-budget models are unsupported. Opaque thinking blocks remain "
            "in temporary protocol memory only; effort support varies by model.",
            ("https://platform.claude.com/docs/en/api/messages/create",
             "https://platform.claude.com/docs/en/build-with-claude/effort",
             "https://platform.claude.com/docs/en/build-with-claude/thinking",
             "https://platform.claude.com/docs/en/build-with-claude/structured-outputs"),
        ),
        ProviderPreset(
            "deepseek", "DeepSeek", "chat_completions", "https://api.deepseek.com",
            "DEEPSEEK_API_KEY", "deepseek-flash", ("none", "low", "high", "max"),
            "Current Flash and V4 Pro profiles send native reasoning_effort exactly. "
            "Provider aliases such as medium-to-high are rejected locally. JSON mode "
            "is checked again against the debate schema by the engine.",
            ("https://api-docs.deepseek.com/api/create-chat-completion/",
             "https://api-docs.deepseek.com/guides/thinking_mode/",
             "https://api-docs.deepseek.com/guides/json_mode/"),
        ),
        ProviderPreset(
            "kimi", "Moonshot / Kimi", "chat_completions", "https://api.moonshot.ai/v1",
            "MOONSHOT_API_KEY", "kimi-k3", ("low", "high", "max", "enabled", "disabled"),
            "K3 accepts low/high/max. K2.7 Code has fixed enabled thinking; K2.6 uses "
            "enabled/disabled. These modes are not numeric effort equivalents. K3 and "
            "K2.7 preserve required private reasoning protocol state in memory only.",
            ("https://platform.kimi.ai/docs/guide/use-reasoning-effort",
             "https://platform.kimi.ai/docs/guide/use-thinking-models",
             "https://platform.kimi.ai/docs/api/models-overview",
             "https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api"),
        ),
        ProviderPreset(
            "gemini", "Google / Gemini", "chat_completions",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "GEMINI_API_KEY", "gemini-3.8-flash", ("none", "minimal", "low", "medium", "high"),
            "Uses Google's official OpenAI-compatible endpoint and its documented "
            "reasoning_effort parameter. Profiles reject levels the model would "
            "remap or cannot support. Total reported usage includes thinking; native "
            "tools, images, and grounding are not used.",
            ("https://ai.google.dev/gemini-api/docs/openai",
             "https://ai.google.dev/gemini-api/docs/thinking"),
        ),
        ProviderPreset(
            "openai-compatible", "Custom OpenAI-compatible API", "chat_completions", None,
            "OPENAI_COMPATIBLE_API_KEY", "your-exact-model-id",
            (*_OPENAI_EFFORTS, "provider_default"),
            "Requires an explicit trusted HTTPS base URL. Selecting this preset "
            "declares that the endpoint supports Chat Completions, JSON object mode, "
            "max_tokens, usage, and the exact reasoning_effort value sent. No capability "
            "is inferred for an arbitrary endpoint. provider_default explicitly omits "
            "effort and does not claim a controlled or inherited thinking level.",
            ("https://platform.openai.com/docs/api-reference/chat/create",),
        ),
    )
})


def get_provider_preset(name: str) -> ProviderPreset:
    if not isinstance(name, str) or name not in PROVIDER_PRESETS:
        raise ConfigError("Unknown provider preset; choose: " + ", ".join(PROVIDER_PRESETS))
    return PROVIDER_PRESETS[name]


def list_provider_presets() -> list[dict[str, Any]]:
    presets = []
    for preset in PROVIDER_PRESETS.values():
        item = asdict(preset)
        item["supported_efforts"] = list(preset.supported_efforts)
        item["documentation"] = list(preset.documentation)
        presets.append(item)
    return presets


def supported_efforts(name: str, model: str | None = None) -> tuple[str, ...]:
    """Return the preset's union, or the exact model profile (empty if unknown)."""
    preset = get_provider_preset(name)
    if model is None or name not in _MODEL_EFFORTS:
        return preset.supported_efforts
    profiles = _MODEL_EFFORTS[name]
    if not isinstance(model, str):
        return ()
    if name == "anthropic":
        # A dated snapshot is sent as requested; this only selects its profile.
        model = re.sub(r"-\d{8}$", "", model)
    return profiles.get(model, ())


def supported_models(name: str) -> tuple[str, ...]:
    """Return explicit model profiles; generic/Responses transports return ()."""
    get_provider_preset(name)
    return tuple(_MODEL_EFFORTS.get(name, ()))


def validate_provider_config(name: str, config: SessionConfig) -> None:
    preset = get_provider_preset(name)
    if config.provider != name:
        raise ConfigError("SessionConfig.provider must match the selected API provider")
    efforts = supported_efforts(name, config.model)
    if not efforts:
        raise ConfigError(
            f"{preset.display_name} has no reviewed capability profile for this model. "
            "Use a documented supported model, update the profile, or explicitly "
            "configure the generic OpenAI-compatible transport if the endpoint supports it."
        )
    if config.reasoning_effort not in efforts:
        raise ConfigError(
            f"Unsupported reasoning effort for this {preset.display_name} model; "
            "choose exactly: " + ", ".join(efforts) + ". No effort translation is performed."
        )


def _endpoint(base_url: str | None, path: str) -> str:
    if not isinstance(base_url, str) or not base_url or any(c.isspace() or ord(c) < 32 for c in base_url):
        raise ProviderError("base_url must be an explicit trusted HTTPS URL")
    try:
        parts = urlsplit(base_url)
        invalid = (parts.scheme != "https" or not parts.hostname or parts.username is not None
                   or parts.password is not None or parts.query or parts.fragment)
        parts.port  # Validate a supplied port without changing it.
    except ValueError:
        raise ProviderError("base_url is not a valid trusted HTTPS URL") from None
    if invalid:
        raise ProviderError("base_url must be a trusted HTTPS URL without credentials, query or fragment")
    return base_url.rstrip("/") + path


def _parse_json_object(content: Any) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("Provider returned no public structured text")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("non-finite number")

    try:
        data = json.loads(content, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError):
        raise ProviderError("Provider returned invalid structured JSON; no turn was accepted") from None
    if not isinstance(data, dict):
        raise ProviderError("Debate output must be a JSON object")
    return data


def _token_count(usage: dict, field: str, *, optional: bool = False) -> int:
    value = usage.get(field, 0 if optional else None)
    if type(value) is not int or value < 0:
        raise ProviderError("Provider returned missing or invalid token usage")
    return value


def _identity(result: Any) -> tuple[str, str, dict]:
    if not isinstance(result, dict) or result.get("error"):
        raise ProviderError("Provider returned an invalid or unsuccessful response")
    model = result.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ProviderError("Provider omitted the reported model; model identity cannot be checked")
    response_id = result.get("id", "")
    if not isinstance(response_id, str):
        raise ProviderError("Provider returned an invalid response ID")
    usage = result.get("usage")
    if not isinstance(usage, dict):
        raise ProviderError("Provider omitted token usage; the run's usage threshold cannot be enforced")
    return model, response_id, usage


def _normalize_history(messages: Any) -> list[dict[str, str]]:
    if not isinstance(messages, list) or not messages or len(messages) % 2 != 1:
        raise ProviderError("Role history must end with a user turn and alternate user/assistant messages")
    normalized = []
    for index, message in enumerate(messages):
        expected_role = "user" if index % 2 == 0 else "assistant"
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] != expected_role or not isinstance(message["content"], str)):
            raise ProviderError("Role history must contain only public user/assistant text messages")
        content = message["content"]
        if expected_role == "assistant":
            content = json.dumps(_parse_json_object(content), sort_keys=True, ensure_ascii=False)
        normalized.append({"role": expected_role, "content": content})
    return normalized


@dataclass(slots=True)
class _RoleState:
    public: list[dict]
    wire: list[dict]
    pending: object | None = None


class _ProtocolHistory:
    """Keep wire-only fields isolated by role and invalidate late completions."""

    def __init__(self):
        self._lock = threading.Lock()
        self._generation = 0
        self._binding: tuple[str, str, str] | None = None
        self._roles: dict[str, _RoleState] = {}

    def prepare(self, role: str, messages: list[dict], config: SessionConfig) -> tuple:
        if role not in {"pro", "con"}:
            raise ProviderError("The API adapter supports exactly the pro and con roles")
        public = _normalize_history(messages)
        binding = (config.provider, config.model, config.reasoning_effort)
        with self._lock:
            if self._binding is not None and binding != self._binding:
                raise ProviderError("Provider, model, or effort changed within a session; start a new run")
            state = self._roles.get(role)
            if state is None:
                state = _RoleState([], [])
            if state.pending is not None:
                raise ProviderError("Concurrent calls for the same debate role are unsupported")
            if public[:-1] != state.public:
                raise ProviderError("Provider protocol history does not match public role history; start a new run")
            self._binding = binding
            marker = object()
            state.pending = marker
            self._roles[role] = state
            token = (self._generation, role, marker)
            wire = copy.deepcopy(state.wire) + [copy.deepcopy(messages[-1])]
        return token, public, wire

    def remember(self, token: tuple, public: list[dict], wire: list[dict],
                 data: dict, assistant: dict) -> None:
        generation, role, marker = token
        with self._lock:
            state = self._roles.get(role)
            if generation != self._generation or state is None or state.pending is not marker:
                return  # A cancelled run must not regain private state later.
            state.public = copy.deepcopy(public) + [{
                "role": "assistant", "content": json.dumps(data, sort_keys=True, ensure_ascii=False),
            }]
            state.wire = copy.deepcopy(wire) + [copy.deepcopy(assistant)]
            state.pending = None

    def release(self, token: tuple) -> None:
        generation, role, marker = token
        with self._lock:
            state = self._roles.get(role)
            if generation == self._generation and state is not None and state.pending is marker:
                state.pending = None

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._roles.clear()
            self._binding = None


class _APIProvider:
    def __init__(self, name: str, api_key: str, base_url: str | None, path: str,
                 transport: Callable[[str, dict, dict, float], dict] | None = None):
        self.preset = get_provider_preset(name)
        if not isinstance(api_key, str) or not api_key or any(c.isspace() or ord(c) < 32 for c in api_key):
            raise ProviderError(f"{self.preset.api_key_env} must contain an API key for a live run")
        self._url = _endpoint(base_url, path)
        self._api_key = api_key
        self._transport = transport or _http_transport
        self._history = _ProtocolHistory()

    def clear_session(self) -> None:
        """Erase private protocol history and invalidate pending history writes."""
        self._history.clear()

    def _send(self, body: dict, headers: dict, config: SessionConfig) -> dict:
        headers = {"Content-Type": "application/json", "User-Agent": "debate-direction/" + __version__, **headers}
        try:
            return self._transport(self._url, body, headers, config.timeout_seconds)
        except ProviderError:
            raise
        except (TimeoutError, socket.timeout):
            raise ProviderError("Provider request timed out; completion and billing status may be unknown") from None
        except Exception:
            raise ProviderError("Provider transport failed; no automatic retry") from None


class AnthropicMessagesProvider(_APIProvider):
    """Anthropic Messages with adaptive thinking and structured public output."""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1",
                 transport: Callable[[str, dict, dict, float], dict] | None = None):
        super().__init__("anthropic", api_key, base_url, "/messages", transport)

    def complete(self, *, role: str, phase: str, round_number: int,
                 instructions: str, messages: list[dict], schema: dict,
                 config: SessionConfig) -> Completion:
        validate_provider_config("anthropic", config)
        token, public, wire = self._history.prepare(role, messages, config)
        body = {
            "model": config.model, "max_tokens": config.max_output_tokens,
            "system": instructions, "messages": copy.deepcopy(wire), "stream": False,
            "thinking": {"type": "adaptive", "display": "omitted"},
            "output_config": {
                "effort": config.reasoning_effort,
                "format": {"type": "json_schema", "schema": copy.deepcopy(schema)},
            },
        }
        try:
            result = self._send(body, {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}, config)
            model, response_id, usage = _identity(result)
            if (result.get("type") != "message" or result.get("role") != "assistant"
                    or result.get("stop_reason") != "end_turn"):
                raise ProviderError("Anthropic did not complete a public response; no debate turn was accepted")
            echoed = result.get("output_config")
            if isinstance(echoed, dict) and "effort" in echoed and echoed["effort"] != config.reasoning_effort:
                raise ProviderError("Provider reported a different reasoning effort; refusing configuration drift")
            contents = result.get("content")
            if not isinstance(contents, list):
                raise ProviderError("Anthropic omitted its structured message content")
            texts = []
            for part in contents:
                if not isinstance(part, dict):
                    raise ProviderError("Malformed Anthropic message content")
                kind = part.get("type")
                if kind == "text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
                elif kind == "thinking":
                    if not isinstance(part.get("thinking"), str) or not isinstance(part.get("signature"), str):
                        raise ProviderError("Malformed Anthropic thinking protocol state")
                elif kind == "redacted_thinking":
                    if not isinstance(part.get("data"), str):
                        raise ProviderError("Malformed Anthropic thinking protocol state")
                else:
                    raise ProviderError("Anthropic returned unsupported or refused content; no turn was accepted")
            data = _parse_json_object("".join(texts))
            input_tokens = (_token_count(usage, "input_tokens")
                            + _token_count(usage, "cache_creation_input_tokens", optional=True)
                            + _token_count(usage, "cache_read_input_tokens", optional=True))
            output_tokens = _token_count(usage, "output_tokens")
            self._history.remember(token, public, wire, data, {"role": "assistant", "content": contents})
            return Completion(data, model, input_tokens, output_tokens, response_id)
        finally:
            self._history.release(token)


class ChatCompletionsProvider(_APIProvider):
    """Profiled Chat Completions APIs; private reasoning never enters reports."""

    def __init__(self, name: str, api_key: str, base_url: str | None = None,
                 transport: Callable[[str, dict, dict, float], dict] | None = None):
        preset = get_provider_preset(name)
        if preset.protocol != "chat_completions":
            raise ConfigError("This provider does not use Chat Completions")
        super().__init__(name, api_key, preset.base_url if base_url is None else base_url,
                         "/chat/completions", transport)

    def complete(self, *, role: str, phase: str, round_number: int,
                 instructions: str, messages: list[dict], schema: dict,
                 config: SessionConfig) -> Completion:
        name = self.preset.name
        validate_provider_config(name, config)
        token, public, wire = self._history.prepare(role, messages, config)
        json_instruction = (
            "\n\nReturn exactly one valid JSON object matching the following JSON Schema. "
            "Do not wrap it in Markdown. Return concise public conclusions and evidence "
            "summaries only; do not include private reasoning or thinking traces.\n"
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        )
        body = {
            "model": config.model,
            "messages": [{"role": "system", "content": instructions + json_instruction}] + copy.deepcopy(wire),
            "max_tokens": config.max_output_tokens, "stream": False,
            "response_format": {"type": "json_object"},
        }
        preserve_reasoning = name == "kimi" and config.model in {
            "kimi-k3", "kimi-k2.7-code", "kimi-k2.7-code-highspeed",
        }
        if name == "kimi" and config.model != "kimi-k3":
            body["thinking"] = {"type": config.reasoning_effort}
            if preserve_reasoning:
                body["thinking"]["keep"] = "all"
        elif config.reasoning_effort != "provider_default":
            body["reasoning_effort"] = config.reasoning_effort
        if name == "gemini":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "debate_turn", "strict": True, "schema": copy.deepcopy(schema)},
            }
        try:
            result = self._send(body, {"Authorization": "Bearer " + self._api_key}, config)
            model, response_id, usage = _identity(result)
            choices = result.get("choices")
            if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                raise ProviderError("Provider must return exactly one completed choice")
            choice = choices[0]
            message = choice.get("message")
            if choice.get("finish_reason") != "stop":
                raise ProviderError("Provider did not complete the response; no usable debate turn was accepted")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ProviderError("Provider omitted its assistant message")
            if message.get("refusal") or message.get("tool_calls") or message.get("function_call"):
                raise ProviderError("Provider returned refused or tool-call content; no debate turn was accepted")
            if ("reasoning_effort" in result and config.reasoning_effort != "provider_default"
                    and "reasoning_effort" in body and result["reasoning_effort"] != config.reasoning_effort):
                raise ProviderError("Provider reported a different reasoning effort; refusing configuration drift")
            if "thinking" in body and isinstance(result.get("thinking"), dict):
                if result["thinking"].get("type") != body["thinking"]["type"]:
                    raise ProviderError("Provider reported a different thinking mode; refusing configuration drift")
            data = _parse_json_object(message.get("content"))
            input_tokens = _token_count(usage, "prompt_tokens")
            output_tokens = _token_count(usage, "completion_tokens")
            if name == "gemini":
                # Gemini compatibility responses can report visible completion
                # tokens separately from thinking. The provider's total includes
                # both. Subtract input once, rather than omit or double-add thinking.
                total_tokens = _token_count(usage, "total_tokens")
                if total_tokens < input_tokens + output_tokens:
                    raise ProviderError("Gemini returned inconsistent total token usage")
                output_tokens = total_tokens - input_tokens
                details = usage.get("completion_tokens_details")
                if details is not None:
                    if not isinstance(details, dict):
                        raise ProviderError("Gemini returned malformed token usage details")
                    if ("reasoning_tokens" in details
                            and _token_count(details, "reasoning_tokens") > output_tokens):
                        raise ProviderError("Gemini returned inconsistent reasoning token usage")
            elif "total_tokens" in usage and _token_count(usage, "total_tokens") != input_tokens + output_tokens:
                raise ProviderError("Provider returned inconsistent total token usage")
            if preserve_reasoning:
                # Replay the complete message as returned. The field is optional
                # in K3 responses; do not invent it or reject absent/null content.
                if message.get("reasoning_content") is not None and not isinstance(message["reasoning_content"], str):
                    raise ProviderError("Kimi returned malformed private reasoning protocol state")
                assistant = copy.deepcopy(message)
            else:
                assistant = {"role": "assistant", "content": message["content"]}
                # Gemini may return opaque continuation fields with ordinary
                # text messages. Preserve those fields only in wire history.
                if name == "gemini" and "extra_content" in message:
                    assistant["extra_content"] = copy.deepcopy(message["extra_content"])
            self._history.remember(token, public, wire, data, assistant)
            return Completion(data, model, input_tokens, output_tokens, response_id)
        finally:
            self._history.release(token)


class OpenAICompatibleChatProvider(ChatCompletionsProvider):
    def __init__(self, api_key: str, base_url: str,
                 transport: Callable[[str, dict, dict, float], dict] | None = None):
        super().__init__("openai-compatible", api_key, base_url, transport)


def create_provider(name: str, *, api_key: str, base_url: str | None = None,
                    transport: Callable[[str, dict, dict, float], dict] | None = None):
    """Construct one transport. Preflight the exact SessionConfig before calling."""
    preset = get_provider_preset(name)
    endpoint = preset.base_url if base_url is None else base_url
    if name == "openai":
        _endpoint(endpoint, "/responses")  # Consistent custom-endpoint validation.
        return OpenAIResponsesProvider(api_key, base_url=endpoint, transport=transport)
    if name == "anthropic":
        return AnthropicMessagesProvider(api_key, base_url=endpoint, transport=transport)
    return ChatCompletionsProvider(name, api_key, base_url=endpoint, transport=transport)
