"""Configuration provenance and consistency tests; no ambient credentials needed."""

import dataclasses
import unittest

from debate_direction.config import ConfigError, SessionConfig, resolve_config


class SessionConfigTests(unittest.TestCase):
    def test_session_settings_are_immutable(self):
        config = SessionConfig(model="model-for-test", reasoning_effort="high")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            config.model = "a-different-model"

    def test_blank_model_or_effort_is_rejected(self):
        for model, effort in (("", "high"), ("  ", "high"), ("model", ""), ("model", "  ")):
            with self.subTest(model=model, effort=effort):
                with self.assertRaises(ConfigError):
                    SessionConfig(model=model, reasoning_effort=effort)

    def test_nonpositive_limits_are_rejected(self):
        for field in (
            "max_rounds", "min_rounds", "max_output_tokens", "max_total_tokens",
            "timeout_seconds", "stall_rounds", "max_duration_seconds", "max_input_chars",
        ):
            for value in (0, -1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ConfigError):
                        SessionConfig(model="model", reasoning_effort="high", **{field: value})

    def test_minimum_rounds_cannot_exceed_maximum(self):
        with self.assertRaises(ConfigError):
            SessionConfig(model="model", reasoning_effort="high", min_rounds=3, max_rounds=2)

    def test_deadlines_must_be_finite_numeric_values(self):
        for field in ("timeout_seconds", "max_duration_seconds"):
            for value in (float("inf"), float("nan"), True, "30"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ConfigError):
                        SessionConfig(model="model", reasoning_effort="high", **{field: value})

    def test_cli_does_not_treat_current_or_auto_as_a_resolved_model(self):
        for model in ("auto", "current", "inherited", "default"):
            with self.subTest(model=model):
                with self.assertRaises(ConfigError):
                    SessionConfig(model=model, reasoning_effort="high")


class ResolveConfigTests(unittest.TestCase):
    def test_explicit_pair_records_explicit_provenance(self):
        config = resolve_config(model="explicit-model", reasoning_effort="high", env={})
        self.assertEqual(config.model, "explicit-model")
        self.assertEqual(config.reasoning_effort, "high")
        self.assertEqual(config.config_source, "explicit")

    def test_session_pair_records_session_config_not_inherited(self):
        config = resolve_config(
            session_config={"model": "session-model", "reasoning_effort": "high"},
            env={},
        )
        self.assertEqual(config.model, "session-model")
        self.assertEqual(config.reasoning_effort, "high")
        self.assertEqual(config.config_source, "session_config")

    def test_environment_requires_and_preserves_a_complete_pair(self):
        config = resolve_config(env={
            "DEBATE_MODEL": "environment-model",
            "DEBATE_REASONING_EFFORT": "medium",
        })
        self.assertEqual(config.model, "environment-model")
        self.assertEqual(config.reasoning_effort, "medium")
        self.assertEqual(config.config_source, "environment")

    def test_explicit_pair_does_not_silently_use_environment_values(self):
        config = resolve_config(
            model="explicit-model", reasoning_effort="high",
            env={"DEBATE_MODEL": "environment-model", "DEBATE_REASONING_EFFORT": "low"},
        )
        self.assertEqual((config.model, config.reasoning_effort), ("explicit-model", "high"))
        self.assertEqual(config.config_source, "explicit")

    def test_missing_settings_do_not_select_an_arbitrary_default_model(self):
        with self.assertRaises(ConfigError):
            resolve_config(env={})

    def test_partial_pairs_cannot_be_completed_from_another_source(self):
        cases = (
            {"model": "explicit-model", "env": {"DEBATE_REASONING_EFFORT": "high"}},
            {"reasoning_effort": "high", "env": {"DEBATE_MODEL": "environment-model"}},
            {"model": "explicit-model", "session_config": {"reasoning_effort": "high"}, "env": {}},
            {"session_config": {"model": "session-model"}, "env": {
                "DEBATE_MODEL": "environment-model", "DEBATE_REASONING_EFFORT": "high",
            }},
            {"env": {"DEBATE_MODEL": "environment-model"}},
            {"env": {"DEBATE_REASONING_EFFORT": "high"}},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ConfigError):
                    resolve_config(**kwargs)

    def test_conflicting_session_and_explicit_settings_are_rejected(self):
        for explicit in (
            {"model": "other-model", "reasoning_effort": "high"},
            {"model": "session-model", "reasoning_effort": "low"},
        ):
            with self.subTest(explicit=explicit):
                with self.assertRaises(ConfigError):
                    resolve_config(
                        **explicit,
                        session_config={"model": "session-model", "reasoning_effort": "high"},
                        env={},
                    )

    def test_explicit_runtime_limits_are_retained(self):
        config = resolve_config(
            model="model", reasoning_effort="high", env={},
            max_rounds=3, min_rounds=2, max_output_tokens=2048,
            max_total_tokens=12000, timeout_seconds=30, stall_rounds=2,
        )
        self.assertEqual(config.max_rounds, 3)
        self.assertEqual(config.min_rounds, 2)
        self.assertEqual(config.max_output_tokens, 2048)
        self.assertEqual(config.max_total_tokens, 12000)
        self.assertEqual(config.timeout_seconds, 30)

    def test_caller_cannot_spoof_native_inheritance_provenance(self):
        with self.assertRaises(ConfigError):
            resolve_config(
                model="model", reasoning_effort="high", env={}, config_source="inherited",
            )
        with self.assertRaises(ConfigError):
            resolve_config(session_config={
                "model": "model", "reasoning_effort": "high", "config_source": "inherited",
            }, env={})


if __name__ == "__main__":
    unittest.main()
