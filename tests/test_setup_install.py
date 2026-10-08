"""Local setup and skill-preservation boundaries; no keys, hosts, or API calls."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from debate_direction.config import ConfigError
from debate_direction import settings, skill_install


PROFILE = {
    "provider": "openai",
    "model": "model-for-test",
    "reasoning_effort": "high",
    "api_key_env": "DEBATE_SETUP_TEST_KEY",
}
SECRET_SENTINEL = "test-only-sensitive-value-never-read-by-setup"


def arguments(**changes):
    values = {
        "provider": None, "model": None, "reasoning_effort": None,
        "base_url": None, "api_key_env": None, "session_config": None,
        "config": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


class LocalTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="debate setup test ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.environment = mock.patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def make_symlink(self, link: Path, target: Path, *, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links unavailable in this environment: {exc}")


class ProfileStorageTests(LocalTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.directory / "configuration directory" / "config.json"

    def test_profile_write_never_reads_or_stores_environment_key_value(self):
        os.environ[PROFILE["api_key_env"]] = SECRET_SENTINEL
        settings.write_profile(self.path, PROFILE)
        raw = self.path.read_text(encoding="utf-8")
        self.assertEqual(settings.read_profile(self.path), PROFILE)
        self.assertNotIn(SECRET_SENTINEL, raw)
        self.assertIn(PROFILE["api_key_env"], raw)
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_identical_rerun_is_a_noop_and_different_profile_requires_overwrite(self):
        settings.write_profile(self.path, PROFILE)
        original = self.path.read_bytes()
        mtime = self.path.stat().st_mtime_ns
        settings.write_profile(self.path, dict(PROFILE))
        self.assertEqual(self.path.stat().st_mtime_ns, mtime)
        with self.assertRaises(ConfigError):
            settings.write_profile(self.path, dict(PROFILE, model="another-model"))
        self.assertEqual(self.path.read_bytes(), original)
        settings.write_profile(self.path, dict(PROFILE, model="another-model"), overwrite=True)
        self.assertEqual(settings.read_profile(self.path)["model"], "another-model")
        self.assertEqual(list(self.path.parent.glob(".debate-config-*")), [])

    def test_profile_symlink_is_not_replaced_even_with_overwrite(self):
        original = self.directory / "existing.json"
        settings.write_profile(original, PROFILE)
        self.path.parent.mkdir()
        self.make_symlink(self.path, original)
        with self.assertRaises(ConfigError):
            settings.write_profile(self.path, dict(PROFILE, model="changed-model"), overwrite=True)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(settings.read_profile(original), PROFILE)

    def test_profile_rejects_embedded_credentials_without_echoing_them(self):
        cases = (
            dict(PROFILE, api_key=SECRET_SENTINEL),
            dict(PROFILE, api_key_env="test-key-not-an-environment-name"),
            dict(PROFILE, base_url=f"https://user:{SECRET_SENTINEL}@example.invalid/v1"),
            dict(PROFILE, base_url=f"https://example.invalid/v1?key={SECRET_SENTINEL}"),
            dict(PROFILE, base_url="http://example.invalid/v1"),
        )
        for profile in cases:
            with self.subTest(profile_field_set=sorted(profile)):
                with self.assertRaises(ConfigError) as caught:
                    settings.write_profile(self.path, profile)
                self.assertNotIn(SECRET_SENTINEL, str(caught.exception))
                self.assertFalse(self.path.exists())

    def test_malformed_url_and_invalid_port_are_configuration_errors(self):
        for base_url in (
            "https://[invalid/v1", "https://example.invalid:not-a-port/v1",
            "https://example.invalid:99999/v1",
        ):
            with self.subTest(base_url=base_url):
                with self.assertRaises(ConfigError):
                    settings.validate_profile(dict(PROFILE, base_url=base_url))

    def test_malformed_oversized_and_unknown_field_profiles_fail_without_echoing_content(self):
        self.path.parent.mkdir()
        for raw in (
            b"\xff\xfe", b"{invalid-json", b" " * 16385,
            json.dumps(dict(PROFILE, api_key=SECRET_SENTINEL)).encode("utf-8"),
        ):
            with self.subTest(length=len(raw)):
                self.path.write_bytes(raw)
                with self.assertRaises(ConfigError) as caught:
                    settings.read_profile(self.path)
                self.assertNotIn(SECRET_SENTINEL, str(caught.exception))

    def test_platform_path_routing_uses_user_configuration_roots(self):
        fake_home = self.directory / "home"
        for platform_name, env, expected in (
            ("linux", {}, fake_home / ".config" / "debate-direction" / "config.json"),
            ("linux", {"XDG_CONFIG_HOME": str(self.directory / "xdg config")}, self.directory / "xdg config" / "debate-direction" / "config.json"),
            ("darwin", {}, fake_home / "Library" / "Application Support" / "debate-direction" / "config.json"),
            ("win32", {}, fake_home / "AppData" / "Local" / "debate-direction" / "config.json"),
            ("win32", {"LOCALAPPDATA": str(self.directory / "local app data")}, self.directory / "local app data" / "debate-direction" / "config.json"),
        ):
            with self.subTest(platform=platform_name, env_keys=sorted(env)):
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(settings.sys, "platform", platform_name), mock.patch.object(Path, "home", return_value=fake_home):
                    self.assertEqual(settings.default_config_path(), expected)
        explicit = self.directory / "explicit config.json"
        with mock.patch.dict(os.environ, {"DEBATE_CONFIG": str(explicit)}, clear=True):
            self.assertEqual(settings.default_config_path(), explicit)


class RuntimeResolutionTests(LocalTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.directory / "config.json"
        self.default_path = mock.patch.object(settings, "default_config_path", return_value=self.path)
        self.default_path.start()
        self.addCleanup(self.default_path.stop)
        settings.write_profile(self.path, PROFILE)

    def test_saved_profile_is_whole_and_records_honest_provenance(self):
        config, profile = settings.resolve_runtime(arguments(), limits={"max_rounds": 3})
        self.assertEqual((config.provider, config.model, config.reasoning_effort), ("openai", "model-for-test", "high"))
        self.assertEqual(config.config_source, "saved_profile")
        self.assertEqual(config.max_rounds, 3)
        self.assertEqual(profile, PROFILE)

    def test_complete_explicit_configuration_supersedes_saved_profile(self):
        config, profile = settings.resolve_runtime(arguments(provider="deepseek", model="another-model", reasoning_effort="low"))
        self.assertEqual((config.provider, config.model, config.reasoning_effort), ("deepseek", "another-model", "low"))
        self.assertEqual(config.config_source, "explicit")
        self.assertNotIn("api_key_env", profile)
        self.assertEqual(settings.read_profile(self.path), PROFILE)

    def test_partial_explicit_configuration_does_not_borrow_from_profile_or_environment(self):
        os.environ.update({"DEBATE_MODEL": "env-model", "DEBATE_REASONING_EFFORT": "low"})
        for changes in ({"model": "explicit-model"}, {"reasoning_effort": "high"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ConfigError):
                    settings.resolve_runtime(arguments(**changes))
        os.environ.clear()
        with self.assertRaises(ConfigError):
            settings.resolve_runtime(arguments(provider="deepseek"))
        self.assertEqual(settings.read_profile(self.path), PROFILE)

    def test_complete_environment_configuration_supersedes_default_profile(self):
        os.environ.update({"DEBATE_PROVIDER": "deepseek", "DEBATE_MODEL": "env-model", "DEBATE_REASONING_EFFORT": "low", "OPENAI_BASE_URL": "https://openai-gateway.invalid/v1"})
        config, profile = settings.resolve_runtime(arguments())
        self.assertEqual((config.provider, config.model, config.reasoning_effort), ("deepseek", "env-model", "low"))
        self.assertEqual(config.config_source, "environment")
        self.assertNotIn("base_url", profile)

    def test_partial_environment_does_not_backfill_from_saved_profile(self):
        for env in ({"DEBATE_PROVIDER": "deepseek"}, {"DEBATE_MODEL": "env-model"}, {"DEBATE_REASONING_EFFORT": "low"}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ConfigError):
                    settings.resolve_runtime(arguments())

    def test_explicit_profile_wins_over_ambient_environment_and_rejects_conflicting_flags(self):
        os.environ.update({"DEBATE_PROVIDER": "deepseek", "DEBATE_MODEL": "env-model", "DEBATE_REASONING_EFFORT": "low", "OPENAI_BASE_URL": "https://ambient.invalid/v1"})
        config, profile = settings.resolve_runtime(arguments(config=self.path))
        self.assertEqual(config.config_source, "saved_profile")
        self.assertEqual(profile, PROFILE)
        for changes in (
            {"provider": "deepseek"}, {"model": "other-model"},
            {"reasoning_effort": "low"}, {"api_key_env": "ANOTHER_KEY"},
            {"base_url": "https://another.invalid/v1"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ConfigError):
                    settings.resolve_runtime(arguments(config=self.path, **changes))

    def test_explicit_missing_profile_is_not_silently_ignored(self):
        with self.assertRaises(ConfigError):
            settings.resolve_runtime(arguments(config=self.directory / "missing.json", model="explicit-model", reasoning_effort="high"))

    def test_caller_session_metadata_does_not_claim_native_inheritance_or_mix_profiles(self):
        session = self.directory / "session.json"
        session.write_text(json.dumps({"model": "session-model", "reasoning_effort": "low"}), encoding="utf-8")
        config, profile = settings.resolve_runtime(arguments(session_config=session, provider="deepseek"))
        self.assertEqual(config.config_source, "session_config")
        self.assertEqual((profile["provider"], profile["model"]), ("deepseek", "session-model"))
        with self.assertRaises(ConfigError):
            settings.resolve_runtime(arguments(config=self.path, session_config=session))
        with self.assertRaises(ConfigError):
            settings.resolve_runtime(arguments(session_config=session, model="different-model", reasoning_effort="low"))

    def test_environment_key_value_never_enters_runtime_profile(self):
        os.environ[PROFILE["api_key_env"]] = SECRET_SENTINEL
        config, profile = settings.resolve_runtime(arguments())
        self.assertNotIn(SECRET_SENTINEL, repr(config))
        self.assertNotIn(SECRET_SENTINEL, json.dumps(profile))


class MissingHomeResolutionTests(LocalTestCase):
    def setUp(self):
        super().setUp()
        self.home = mock.patch.object(Path, "home", side_effect=RuntimeError(SECRET_SENTINEL))
        self.home_mock = self.home.start()
        self.addCleanup(self.home.stop)

    def test_complete_explicit_settings_skip_default_location_even_with_debate_config(self):
        for default_path in (None, "~/profile-that-must-not-be-loaded.json"):
            with self.subTest(default_path=default_path):
                env = {} if default_path is None else {"DEBATE_CONFIG": default_path}
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(settings, "default_config_path", side_effect=AssertionError("runtime settings must bypass profile discovery")):
                    config, profile = settings.resolve_runtime(arguments(provider="openai", model="explicit-model", reasoning_effort="high"))
                self.assertEqual((config.model, config.reasoning_effort, config.config_source), ("explicit-model", "high", "explicit"))
                self.assertEqual(profile["provider"], "openai")
        self.home_mock.assert_not_called()

    def test_complete_environment_settings_skip_default_location_and_saved_path(self):
        os.environ.update({"DEBATE_MODEL": "environment-model", "DEBATE_REASONING_EFFORT": "low", "DEBATE_PROVIDER": "openai", "DEBATE_CONFIG": "~/unused-profile.json"})
        with mock.patch.object(settings, "default_config_path", side_effect=AssertionError("environment settings must bypass profile discovery")):
            config, profile = settings.resolve_runtime(arguments())
        self.assertEqual((config.model, config.reasoning_effort, config.config_source), ("environment-model", "low", "environment"))
        self.assertEqual(profile["provider"], "openai")
        self.home_mock.assert_not_called()

    def test_session_metadata_does_not_require_an_automatic_home(self):
        session = self.directory / "session.json"
        session.write_text(json.dumps({"model": "session-model", "reasoning_effort": "high"}), encoding="utf-8")
        with mock.patch.object(settings, "default_config_path", side_effect=AssertionError("session metadata must bypass profile discovery")):
            config, _ = settings.resolve_runtime(arguments(session_config=session))
        self.assertEqual(config.config_source, "session_config")
        self.assertEqual(config.model, "session-model")
        self.home_mock.assert_not_called()

    def test_optional_missing_home_keeps_the_normal_missing_settings_error(self):
        with self.assertRaises(ConfigError) as caught:
            settings.resolve_runtime(arguments())
        message = str(caught.exception)
        self.assertIn("--model", message)
        self.assertIn("--reasoning-effort", message)
        self.assertNotIn(SECRET_SENTINEL, message)
        self.home_mock.assert_called_once()
        with self.assertRaisesRegex(ConfigError, "together"):
            settings.resolve_runtime(arguments(model="incomplete-model"))

    def test_selected_profile_read_errors_are_not_discarded_when_home_is_missing(self):
        missing = self.directory / "missing.json"
        malformed = self.directory / "malformed.json"
        malformed.write_text("{invalid-json", encoding="utf-8")
        for path in (missing, malformed):
            for source in ("argument", "environment"):
                with self.subTest(path=path.name, source=source):
                    env = {"DEBATE_CONFIG": str(path)} if source == "environment" else {}
                    args = arguments() if source == "environment" else arguments(config=path, model="explicit-model", reasoning_effort="high")
                    with mock.patch.dict(os.environ, env, clear=True):
                        with self.assertRaisesRegex(ConfigError, "could not read a valid profile") as caught:
                            settings.resolve_runtime(args)
                    self.assertNotIn(SECRET_SENTINEL, str(caught.exception))
        self.home_mock.assert_not_called()

    def test_selected_profile_expansion_errors_are_sanitized_and_not_suppressed(self):
        for source in ("argument", "environment"):
            with self.subTest(source=source):
                env = {"DEBATE_CONFIG": "~/selected.json"} if source == "environment" else {}
                args = arguments() if source == "environment" else arguments(config=Path("~/selected.json"))
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(Path, "expanduser", side_effect=RuntimeError(SECRET_SENTINEL)):
                    with self.assertRaises(ConfigError) as caught:
                        settings.resolve_runtime(args)
                message = str(caught.exception)
                self.assertIn("DEBATE_CONFIG", message)
                self.assertIn("--config", message)
                self.assertNotIn(SECRET_SENTINEL, message)

    def test_valid_absolute_selected_profile_works_and_explicit_flag_wins(self):
        path = self.directory / "profile.json"
        settings.write_profile(path, PROFILE)
        os.environ["DEBATE_CONFIG"] = str(path)
        config, profile = settings.resolve_runtime(arguments())
        self.assertEqual(config.config_source, "saved_profile")
        self.assertEqual(profile, PROFILE)
        os.environ["DEBATE_CONFIG"] = "~/unselected-invalid-profile.json"
        config, profile = settings.resolve_runtime(arguments(config=path))
        self.assertEqual(config.config_source, "saved_profile")
        self.assertEqual(profile, PROFILE)
        self.home_mock.assert_not_called()

    def test_required_default_destination_has_guidance_and_explicit_roots_work(self):
        for platform_name in ("win32", "darwin", "linux"):
            with self.subTest(platform=platform_name), mock.patch.object(settings.sys, "platform", platform_name):
                with self.assertRaises(ConfigError) as caught:
                    settings.default_config_path()
                self.assertIn("DEBATE_CONFIG", str(caught.exception))
                self.assertIn("--config", str(caught.exception))
                self.assertNotIn(SECRET_SENTINEL, str(caught.exception))
        for platform_name, root_var in (("win32", "LOCALAPPDATA"), ("linux", "XDG_CONFIG_HOME")):
            with self.subTest(root_var=root_var):
                root = self.directory / root_var
                with mock.patch.dict(os.environ, {root_var: str(root)}, clear=True), mock.patch.object(settings.sys, "platform", platform_name):
                    self.assertEqual(settings.default_config_path(), root / "debate-direction" / "config.json")


class SkillInstallationTests(LocalTestCase):
    def setUp(self):
        super().setUp()
        self.root = self.directory / "host home" / ".agents" / "skills"
        self.target = self.root / skill_install.SKILL_NAME
        self.bundle = {
            "SKILL.md": b"---\nname: debate-direction\ndescription: Test fixture.\n---\nVersion one.\n",
            "references/protocol.md": b"Keep the two original agents.\n",
        }
        self.bundle_patch = mock.patch.object(skill_install, "bundled_skill", return_value=self.bundle)
        self.bundle_patch.start()
        self.addCleanup(self.bundle_patch.stop)

    def install(self, **options):
        return skill_install.install_skill("codex", skills_dir=self.root, **options)

    def test_host_path_routing_and_custom_kimi_home(self):
        fake_home = self.directory / "user home"
        with mock.patch.object(Path, "home", return_value=fake_home):
            for host, folder in (("codex", ".agents"), ("claude", ".claude"), ("kimi", ".kimi-code")):
                with self.subTest(host=host):
                    self.assertEqual(skill_install.skill_root(host), fake_home / folder / "skills")
                    self.assertEqual(skill_install.skill_root(host, project=self.directory), self.directory.resolve() / folder / "skills")
            os.environ["KIMI_CODE_HOME"] = str(self.directory / "isolated kimi")
            self.assertEqual(skill_install.skill_root("kimi"), self.directory / "isolated kimi" / "skills")
            self.assertEqual(skill_install.skill_root("kimi", project=self.directory), self.directory.resolve() / ".kimi-code" / "skills")

    def test_initial_install_and_safe_rerun_preserve_other_skills_and_host_settings(self):
        other = self.root / "user-owned-skill" / "SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"User-owned instructions.\n")
        host_settings = self.root.parent / "config.toml"
        host_settings.write_bytes(b'model = "keep-user-model"\n')
        first = self.install()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        second = self.install()
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(first["status"], "installed")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(first["invocation"], "$debate-direction")
        self.assertEqual(before, after)
        self.assertEqual(other.read_bytes(), b"User-owned instructions.\n")
        self.assertEqual(host_settings.read_bytes(), b'model = "keep-user-model"\n')
        self.assertNotIn("backup", second)

    def test_unowned_or_locally_modified_skill_requires_force(self):
        self.target.mkdir(parents=True)
        owned_by_user = self.target / "SKILL.md"
        owned_by_user.write_bytes(b"My own skill with the same name.\n")
        with self.assertRaises(ConfigError):
            self.install()
        self.assertEqual(owned_by_user.read_bytes(), b"My own skill with the same name.\n")
        self.install(force=True)
        owned_by_user.write_bytes(b"A local modification.\n")
        with self.assertRaises(ConfigError):
            self.install()
        self.assertEqual(owned_by_user.read_bytes(), b"A local modification.\n")

    def test_owned_upgrade_keeps_backup_outside_skill_discovery_root(self):
        self.install()
        original = (self.target / "SKILL.md").read_bytes()
        self.bundle["SKILL.md"] = b"A revised bundled skill.\n"
        result = self.install()
        backup = Path(result["backup"])
        self.assertEqual(result["status"], "updated")
        self.assertNotIn(self.root, backup.parents)
        self.assertEqual(backup.parent, self.root.parent / "debate-direction-backups")
        self.assertEqual((backup / "SKILL.md").read_bytes(), original)
        self.assertEqual((self.target / "SKILL.md").read_bytes(), self.bundle["SKILL.md"])

    def test_forced_upgrade_preserves_every_user_file_in_backup(self):
        self.install()
        user_file = self.target / "notes.txt"
        user_file.write_bytes(b"Keep my local notes.\n")
        (self.target / "SKILL.md").write_bytes(b"A user-edited skill.\n")
        result = self.install(force=True)
        backup = Path(result["backup"])
        self.assertEqual((backup / "notes.txt").read_bytes(), b"Keep my local notes.\n")
        self.assertEqual((backup / "SKILL.md").read_bytes(), b"A user-edited skill.\n")
        self.assertEqual((self.target / "SKILL.md").read_bytes(), self.bundle["SKILL.md"])

    def test_nested_marker_named_user_file_is_not_ignored_during_upgrade(self):
        self.install()
        user_file = self.target / "references" / skill_install.MARKER
        user_file.write_bytes(b"User-owned content, not the installation marker.\n")
        self.bundle["SKILL.md"] = b"An upgraded bundled skill.\n"
        with self.assertRaises(ConfigError):
            self.install()
        self.assertEqual(user_file.read_bytes(), b"User-owned content, not the installation marker.\n")

    def test_dry_run_does_not_create_or_replace_files(self):
        result = self.install(dry_run=True)
        self.assertEqual(result["status"], "would_install")
        self.assertFalse(self.root.exists())
        self.install()
        original = (self.target / "SKILL.md").read_bytes()
        self.bundle["SKILL.md"] = b"A revised skill.\n"
        result = self.install(dry_run=True)
        self.assertEqual(result["status"], "would_update")
        self.assertEqual((self.target / "SKILL.md").read_bytes(), original)
        self.assertFalse((self.root.parent / "debate-direction-backups").exists())

    def test_symlink_destination_is_preserved_even_with_force(self):
        self.root.mkdir(parents=True)
        outside = self.directory / "user skill elsewhere"
        outside.mkdir()
        (outside / "SKILL.md").write_bytes(b"Keep the original symlink target.\n")
        self.make_symlink(self.target, outside, directory=True)
        with self.assertRaises(ConfigError):
            self.install(force=True)
        self.assertTrue(self.target.is_symlink())
        self.assertEqual((outside / "SKILL.md").read_bytes(), b"Keep the original symlink target.\n")

    def test_failed_promotion_restores_previous_skill(self):
        self.install()
        original = (self.target / "SKILL.md").read_bytes()
        self.bundle["SKILL.md"] = b"An upgrade that cannot be promoted.\n"
        real_rename = Path.rename

        def fail_stage_promotion(path, destination):
            if path.name.startswith(".debate-direction-") and Path(destination) == self.target:
                raise OSError("simulated promotion failure")
            return real_rename(path, destination)

        with mock.patch.object(Path, "rename", fail_stage_promotion):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual((self.target / "SKILL.md").read_bytes(), original)
        self.assertEqual(list(self.root.glob(".debate-direction-*")), [])

    def test_destination_changed_during_staging_is_preserved(self):
        self.install()
        self.bundle["SKILL.md"] = b"A new bundled version.\n"
        original_read = skill_install._existing_files
        calls = 0

        def edit_before_recheck(target):
            nonlocal calls
            calls += 1
            if calls == 2:
                (target / "SKILL.md").write_bytes(b"A concurrent user edit.\n")
            return original_read(target)

        with mock.patch.object(skill_install, "_existing_files", side_effect=edit_before_recheck):
            with self.assertRaises(ConfigError):
                self.install()
        self.assertEqual((self.target / "SKILL.md").read_bytes(), b"A concurrent user edit.\n")
        self.assertEqual(list(self.root.glob(".debate-direction-*")), [])

    def test_destination_appearing_during_staging_is_not_overwritten(self):
        real_mkdtemp = tempfile.mkdtemp

        def create_competing_destination(*args, **kwargs):
            stage = real_mkdtemp(*args, **kwargs)
            self.target.mkdir()
            (self.target / "SKILL.md").write_bytes(b"A concurrently installed skill.\n")
            return stage

        with mock.patch.object(skill_install.tempfile, "mkdtemp", side_effect=create_competing_destination):
            with self.assertRaises(ConfigError):
                self.install()
        self.assertEqual((self.target / "SKILL.md").read_bytes(), b"A concurrently installed skill.\n")

    def test_ambiguous_or_unknown_destinations_fail_before_writing(self):
        with self.assertRaises(ConfigError):
            skill_install.install_skill("codex", project=self.directory, skills_dir=self.root)
        with self.assertRaises(ConfigError):
            skill_install.install_skill("deepseek", skills_dir=self.root)
        self.assertFalse(self.root.exists())


class SetupCommandTests(LocalTestCase):
    def setUp(self):
        super().setUp()
        from debate_direction import commands
        self.commands = commands
        self.path = self.directory / "profile.json"
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.output_context = contextlib.ExitStack()
        self.addCleanup(self.output_context.close)
        self.output_context.enter_context(contextlib.redirect_stdout(self.stdout))
        self.output_context.enter_context(contextlib.redirect_stderr(self.stderr))
        self.output_context.enter_context(mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("local setup must not contact an API")))
        self.output_context.enter_context(mock.patch.object(skill_install, "bundled_skill", return_value={
            "SKILL.md": b"---\nname: debate-direction\ndescription: Local setup test.\n---\n",
        }))
        self.output_context.enter_context(mock.patch.object(Path, "home", return_value=self.directory / "test user home"))
        self.output_context.enter_context(mock.patch.object(self.commands.shutil, "which", return_value=None))

    def setup_args(self, **overrides):
        values = dict(PROFILE, config=str(self.path))
        values.update(overrides)
        arguments = []
        for key, value in values.items():
            arguments.extend(["--" + key.replace("_", "-"), value])
        return arguments

    def test_setup_and_doctor_disclose_only_key_presence_not_value(self):
        os.environ[PROFILE["api_key_env"]] = SECRET_SENTINEL
        self.assertEqual(self.commands.setup(self.setup_args()), 0)
        self.assertNotIn(SECRET_SENTINEL, self.stdout.getvalue())
        self.assertNotIn(SECRET_SENTINEL, self.path.read_text(encoding="utf-8"))
        self.assertIn(PROFILE["api_key_env"], self.stdout.getvalue())
        self.stdout.seek(0)
        self.stdout.truncate(0)
        self.assertEqual(self.commands.doctor(["--config", str(self.path), "--json"]), 0)
        output = self.stdout.getvalue()
        report = json.loads(output)
        self.assertTrue(report["api_key_present"])
        self.assertFalse(report["network_checked"])
        self.assertEqual(report["api_key_env"], PROFILE["api_key_env"])
        self.assertNotIn(SECRET_SENTINEL, output + self.stderr.getvalue())
        self.assertTrue(all(not host["skill_present"] for host in report["hosts"].values()))

    def test_noninteractive_partial_setup_fails_without_prompting_or_writing(self):
        with mock.patch.object(self.commands.sys.stdin, "isatty", return_value=False), mock.patch("builtins.input", side_effect=AssertionError("must not prompt without a terminal")):
            with self.assertRaises(ConfigError):
                self.commands.setup(["--config", str(self.path), "--provider", "openai"])
        self.assertFalse(self.path.exists())

    def test_unsupported_provider_effort_and_missing_custom_endpoint_are_not_saved(self):
        for changes in (
            {"provider": "deepseek", "model": "deepseek-flash", "reasoning_effort": "medium"},
            {"provider": "openai-compatible", "model": "custom-model", "reasoning_effort": "high"},
        ):
            with self.subTest(provider=changes["provider"]):
                with self.assertRaises(ConfigError):
                    self.commands.setup(self.setup_args(**changes))
                self.assertFalse(self.path.exists())

    def test_setup_cannot_replace_existing_profile_without_explicit_overwrite(self):
        self.commands.setup(self.setup_args())
        before = self.path.read_bytes()
        with self.assertRaises(ConfigError):
            self.commands.setup(self.setup_args(model="a-different-model"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.commands.setup(self.setup_args(model="a-different-model") + ["--overwrite"]), 0)
        self.assertEqual(settings.read_profile(self.path)["model"], "a-different-model")

    def test_all_host_conflict_is_detected_before_any_installation(self):
        conflict = self.directory / ".claude" / "skills" / "debate-direction" / "SKILL.md"
        conflict.parent.mkdir(parents=True)
        conflict.write_bytes(b"A user-owned Claude skill.\n")
        with self.assertRaises(ConfigError):
            self.commands.install(["--host", "all", "--project", str(self.directory), "--json"])
        self.assertFalse((self.directory / ".agents").exists())
        self.assertFalse((self.directory / ".kimi-code").exists())
        self.assertEqual(conflict.read_bytes(), b"A user-owned Claude skill.\n")

    def test_later_io_failure_reports_completed_hosts(self):
        real_install = skill_install.install_skill

        def fail_second_host(host, **kwargs):
            if host == "claude" and not kwargs.get("dry_run"):
                raise OSError("simulated installation failure")
            return real_install(host, **kwargs)

        with mock.patch.object(self.commands, "install_skill", side_effect=fail_second_host):
            with self.assertRaises(ConfigError) as caught:
                self.commands.install(["--host", "all", "--project", str(self.directory), "--json"])
        self.assertIn("stopped at claude", str(caught.exception))
        self.assertIn("completed hosts: codex", str(caught.exception))
        self.assertTrue((self.directory / ".agents" / "skills" / "debate-direction" / "SKILL.md").is_file())
        self.assertFalse((self.directory / ".kimi-code").exists())

    def test_all_host_dry_run_is_json_and_has_no_filesystem_side_effects(self):
        self.assertEqual(self.commands.install(["--host", "all", "--project", str(self.directory), "--dry-run", "--json"]), 0)
        reports = json.loads(self.stdout.getvalue())
        self.assertEqual({item["host"] for item in reports}, {"codex", "claude", "kimi"})
        self.assertEqual({item["status"] for item in reports}, {"would_install"})
        self.assertEqual(list(self.directory.iterdir()), [])


    def test_setup_and_doctor_report_missing_default_home_as_configuration_error(self):
        setup_args = self.setup_args()
        config_index = setup_args.index("--config")
        del setup_args[config_index:config_index + 2]
        for command, argv in ((self.commands.setup, setup_args), (self.commands.doctor, [])):
            with self.subTest(command=command.__name__), mock.patch.object(Path, "home", side_effect=RuntimeError(SECRET_SENTINEL)):
                with self.assertRaises(ConfigError) as caught:
                    command(argv)
                self.assertIn("DEBATE_CONFIG", str(caught.exception))
                self.assertIn("--config", str(caught.exception))
                self.assertNotIn(SECRET_SENTINEL, str(caught.exception))
        self.assertFalse(self.path.exists())

    def test_commands_safely_expand_explicit_config_paths(self):
        for command, argv in (
            (self.commands.setup, self.setup_args(config="~/selected.json")),
            (self.commands.doctor, ["--config", "~/selected.json"]),
        ):
            with self.subTest(command=command.__name__), mock.patch.object(Path, "expanduser", side_effect=RuntimeError(SECRET_SENTINEL)):
                with self.assertRaises(ConfigError) as caught:
                    command(argv)
                self.assertIn("--config", str(caught.exception))
                self.assertIn("DEBATE_CONFIG", str(caught.exception))
                self.assertNotIn(SECRET_SENTINEL, str(caught.exception))
        self.assertFalse(self.path.exists())

    def test_absolute_profile_allows_setup_and_doctor_with_unavailable_host_homes(self):
        with mock.patch.object(Path, "home", side_effect=RuntimeError(SECRET_SENTINEL)):
            self.assertEqual(self.commands.setup(self.setup_args()), 0)
            self.stdout.seek(0)
            self.stdout.truncate(0)
            self.assertEqual(self.commands.doctor(["--config", str(self.path), "--json"]), 0)
            report = json.loads(self.stdout.getvalue())
            self.assertEqual(report["config_status"], "configured")
            self.assertFalse(report["network_checked"])
            for host in report["hosts"].values():
                self.assertIsNone(host["skill_path"])
                self.assertIsNone(host["skill_present"])
                self.assertIn("unavailable", host["skill_error"])
            self.assertNotIn(SECRET_SENTINEL, self.stdout.getvalue())
            self.stdout.seek(0)
            self.stdout.truncate(0)
            self.commands.doctor(["--config", str(self.path)])
            self.assertEqual(self.stdout.getvalue().count("skill unavailable"), 3)
            self.assertNotIn("skill not installed", self.stdout.getvalue())
            os.environ["KIMI_CODE_HOME"] = str(self.directory / "known kimi home")
            self.stdout.seek(0)
            self.stdout.truncate(0)
            self.commands.doctor(["--config", str(self.path), "--json"])
            report = json.loads(self.stdout.getvalue())
            self.assertFalse(report["hosts"]["kimi"]["skill_present"])
            self.assertIsNotNone(report["hosts"]["kimi"]["skill_path"])
            self.assertIsNone(report["hosts"]["codex"]["skill_present"])
            self.assertIsNone(report["hosts"]["claude"]["skill_present"])

    def test_provider_listing_is_metadata_only(self):
        os.environ["OPENAI_API_KEY"] = SECRET_SENTINEL
        os.environ["DEEPSEEK_API_KEY"] = SECRET_SENTINEL
        self.assertEqual(self.commands.providers(["--json"]), 0)
        output = self.stdout.getvalue()
        records = json.loads(output)
        self.assertTrue({"openai", "anthropic", "deepseek", "kimi"} <= {item["name"] for item in records})
        self.assertNotIn(SECRET_SENTINEL, output)
        self.assertEqual(list(self.directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
