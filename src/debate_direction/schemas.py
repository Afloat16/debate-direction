"""Strict public-output schemas and small, dependency-free validators.

The schemas describe concise, reviewable arguments. They never request a
model's private reasoning. All model-authored fields are treated as untrusted
data; the engine separately validates references and reduces issue state.
"""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "1.0"
SEVERITIES = ("critical", "high", "medium", "low")
ISSUE_STATUSES = ("open", "resolved", "accepted_risk", "disputed")
RESPONSE_ACTIONS = ("fix", "rebut", "accept_risk", "request_clarification")


def _object(properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def _enum(values: tuple[str, ...]) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


_STRING: dict[str, Any] = {"type": "string"}
_STRINGS = _array(_STRING)

OPTION_SCHEMA = _object({
    "id": _STRING,
    "title": _STRING,
    "approach": _STRING,
    "tradeoffs": _STRINGS,
})

RESPONSE_SCHEMA = _object({
    "issue_id": _STRING,
    "action": _enum(RESPONSE_ACTIONS),
    "summary": _STRING,
    "change": _STRING,
})

PROPOSAL_SCHEMA = _object({
    "needs_clarification": {"type": "boolean"},
    "clarification_questions": _STRINGS,
    "problem_statement": _STRING,
    "goal": _STRING,
    "success_criteria": _STRINGS,
    "assumptions": _STRINGS,
    "options": _array(OPTION_SCHEMA),
    "recommended_option_id": _STRING,
    "recommendation": _STRING,
    "implementation_steps": _STRINGS,
    "conditions": _STRINGS,
    "validation_steps": _STRINGS,
    "public_summary": _STRING,
    "responses": _array(RESPONSE_SCHEMA),
})

RISK_SCAN_SCHEMA = _object({
    "needs_clarification": {"type": "boolean"},
    "clarification_questions": _STRINGS,
    "success_criteria": _STRINGS,
    "risk_areas": _array(_object({
        "id": _STRING,
        "severity": _enum(SEVERITIES),
        "concern": _STRING,
        "check": _STRING,
    })),
    "public_summary": _STRING,
})

NEW_ISSUE_SCHEMA = _object({
    "id": _STRING,
    "severity": _enum(SEVERITIES),
    "title": _STRING,
    "description": _STRING,
    "target": _STRING,
    "resolution_criterion": _STRING,
})

ISSUE_EVALUATION_SCHEMA = _object({
    "issue_id": _STRING,
    "status": _enum(ISSUE_STATUSES),
    "rationale": _STRING,
})

REVIEW_SCHEMA = _object({
    "reviewed_version": {"type": "integer"},
    "assessment": _enum(("accept", "revise", "blocked", "needs_clarification")),
    "public_summary": _STRING,
    "clarification_questions": _STRINGS,
    "new_issues": _array(NEW_ISSUE_SCHEMA),
    "issue_evaluations": _array(ISSUE_EVALUATION_SCHEMA),
    "conditions": _STRINGS,
    "next_steps": _STRINGS,
})

# Short aliases make integrations straightforward without duplicating schemas.
PRO_SCHEMA = PROPOSAL_SCHEMA
CON_SCAN_SCHEMA = RISK_SCAN_SCHEMA
CON_REVIEW_SCHEMA = REVIEW_SCHEMA


class SchemaError(ValueError):
    """A response is not a valid public debate turn."""


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the closed subset of JSON Schema used in this module.

    This is deliberately not advertised as a general JSON Schema library.
    It rejects unknown keys and Python booleans where integers are required.
    """
    kind = schema.get("type")
    expected = {
        "object": dict,
        "array": list,
        "string": str,
        "boolean": bool,
        "integer": int,
    }.get(kind)
    if expected is None:
        raise SchemaError(f"{path}: unsupported schema type")
    if type(value) is not expected:
        raise SchemaError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: value is outside the allowed enumeration")
    if kind == "object":
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise SchemaError(f"{path}: missing fields: {', '.join(sorted(missing))}")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise SchemaError(f"{path}: unknown fields: {', '.join(sorted(map(str, extra)))}")
        for name, child in properties.items():
            if name in value:
                validate_schema(value[name], child, f"{path}.{name}")
    elif kind == "array":
        for index, item in enumerate(value):
            validate_schema(item, schema["items"], f"{path}[{index}]")


def validate_output(value: Any, schema: dict[str, Any]) -> None:
    """Backward-friendly descriptive alias for integration callers."""
    validate_schema(value, schema)
