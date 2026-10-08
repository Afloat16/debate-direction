"""Minimal OpenAI Responses transport. Never retries with different settings."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import SessionConfig
from . import __version__


class ProviderError(RuntimeError):
    """Safe, bounded diagnostic, without API keys or provider response dumps."""


@dataclass(frozen=True, slots=True)
class Completion:
    data: dict[str, Any]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    response_id: str = ""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Provider redirect refused; use the final trusted HTTPS endpoint")


def _http_transport(url: str, body: dict, headers: dict, timeout: float) -> dict:
    request = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ProviderError("Provider response exceeded 8 MB")
            return json.loads(raw)
    except HTTPError as exc:
        hints = {401: "authentication failed", 403: "access denied", 429: "rate limit or quota exceeded"}
        hint = hints.get(exc.code, "request rejected; verify model, effort, schema and token limits")
        raise ProviderError(f"Provider HTTP {exc.code}: {hint}; no automatic retry or model fallback") from None
    except (TimeoutError, socket.timeout):
        raise ProviderError("Provider request timed out; completion and billing status may be unknown") from None
    except URLError:
        raise ProviderError("Could not reach the provider; no automatic retry") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProviderError("Provider returned an invalid JSON response") from None


class OpenAIResponsesProvider:
    """Use an immutable shared config and isolated role histories supplied by the engine.

    A custom HTTPS base_url is explicitly trusted by the caller and receives the
    API key and question. Returned model names are recorded, not substituted for
    requested names. The engine checks them for drift across the entire run.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1",
                 transport: Callable[[str, dict, dict, float], dict] | None = None):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderError("OPENAI_API_KEY is required for a live run; use --demo for an offline example")
        parts = urlsplit(base_url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ProviderError("base_url must be a trusted HTTPS URL without credentials, query or fragment")
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/responses"
        self._transport = transport or _http_transport

    def complete(self, *, role: str, phase: str, round_number: int,
                 instructions: str, messages: list[dict], schema: dict,
                 config: SessionConfig) -> Completion:
        body = {
            "model": config.model,
            "reasoning": {"effort": config.reasoning_effort},
            "instructions": instructions,
            "input": messages,
            "max_output_tokens": config.max_output_tokens,
            "store": False,
            "text": {"format": {"type": "json_schema", "name": "debate_turn",
                                 "strict": True, "schema": schema}},
        }
        headers = {"Authorization": "Bearer " + self._api_key,
                   "Content-Type": "application/json", "User-Agent": "debate-direction/" + __version__}
        try:
            result = self._transport(self._url, body, headers, config.timeout_seconds)
        except ProviderError:
            raise
        except (TimeoutError, socket.timeout):
            raise ProviderError("Provider request timed out; completion and billing status may be unknown") from None
        except Exception:
            raise ProviderError("Provider transport failed; no automatic retry") from None
        if not isinstance(result, dict):
            raise ProviderError("Provider response must be a JSON object")
        if result.get("status") != "completed":
            raise ProviderError("Provider did not complete the response; no usable debate turn was accepted")
        model = result.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ProviderError("Provider omitted the reported model; model identity cannot be checked")
        reasoning = result.get("reasoning")
        if isinstance(reasoning, dict) and "effort" in reasoning and reasoning["effort"] != config.reasoning_effort:
            raise ProviderError("Provider reported a different reasoning effort; refusing silent configuration drift")
        texts = []
        output = result.get("output")
        if not isinstance(output, list):
            raise ProviderError("Provider omitted its structured output")
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue  # Do not expose or retain hidden reasoning items.
            contents = item.get("content", [])
            if not isinstance(contents, list):
                raise ProviderError("Malformed provider message content")
            for part in contents:
                if not isinstance(part, dict):
                    raise ProviderError("Malformed provider message content")
                if part.get("type") == "refusal":
                    raise ProviderError("The provider refused this request; debate remains incomplete")
                if part.get("type") == "output_text":
                    if not isinstance(part.get("text"), str):
                        raise ProviderError("Malformed provider text output")
                    texts.append(part["text"])
        if not texts:
            raise ProviderError("Provider returned no public structured text")
        try:
            data = json.loads("".join(texts))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("Provider returned invalid structured JSON; no turn was accepted") from None
        if not isinstance(data, dict):
            raise ProviderError("Debate output must be a JSON object")
        usage = result.get("usage")
        if not isinstance(usage, dict):
            raise ProviderError("Provider omitted token usage; the run's usage threshold cannot be enforced")
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        if type(input_tokens) is not int or type(output_tokens) is not int or min(input_tokens, output_tokens) < 0:
            raise ProviderError("Provider returned invalid token usage")
        response_id = result.get("id", "")
        if not isinstance(response_id, str):
            raise ProviderError("Provider returned an invalid response ID")
        return Completion(data=data, model=model, input_tokens=input_tokens,
                          output_tokens=output_tokens, response_id=response_id)
