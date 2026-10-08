"""Installer boundary tests; never download or execute a vendor bootstrap."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SH = shutil.which("sh")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(SH and platform.system() in {"Linux", "Darwin"}, "POSIX installer requires macOS or Linux")
class ShellInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="debate installer ' $literal ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "local source"
        self.source.mkdir()
        self.binary_directory = self.directory / "command directory"
        self.binary_directory.mkdir()
        self.log = self.directory / "calls.jsonl"
        self.uv = self.directory / "fake uv"
        self.cli = self.binary_directory / "debate-direction"
        common = (
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "with Path(os.environ['DEBATE_INSTALLER_TEST_LOG']).open('a') as handle:\n"
            "    handle.write(json.dumps([Path(sys.argv[0]).name, sys.argv[1:]]) + '\\n')\n"
        )
        self.uv.write_text(
            common
            + "if sys.argv[1:3] == ['tool', 'install']:\n"
            + "    sys.exit(int(os.environ.get('DEBATE_INSTALLER_TEST_UV_EXIT', '0')))\n"
            + "if sys.argv[1:4] == ['tool', 'dir', '--bin']:\n"
            + "    print(os.environ['DEBATE_INSTALLER_TEST_BIN'])\n",
            encoding="utf-8",
        )
        self.cli.write_text(
            common
            + "if sys.argv[1:2] == ['install-skill']:\n"
            + "    sys.exit(int(os.environ.get('DEBATE_INSTALLER_TEST_SKILL_EXIT', '0')))\n",
            encoding="utf-8",
        )
        self.uv.chmod(0o700)
        self.cli.chmod(0o700)
        self.environment = dict(os.environ)
        self.environment.update({
            "DEBATE_INSTALLER_TEST_LOG": str(self.log),
            "DEBATE_INSTALLER_TEST_BIN": str(self.binary_directory),
        })

    def run_installer(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [SH, str(ROOT / "install.sh"), "--uv", str(self.uv), *arguments],
            cwd=ROOT, env=self.environment, text=True, capture_output=True,
            timeout=20, check=False,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_default_installs_named_main_archive_and_no_host(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        install_arguments = calls[0][1]
        self.assertEqual(install_arguments[:2], ["tool", "install"])
        self.assertIn("--managed-python", install_arguments)
        self.assertEqual(install_arguments[install_arguments.index("--python") + 1], "3.11")
        self.assertIn("--reinstall", install_arguments)
        self.assertNotIn("--force", install_arguments)
        self.assertEqual(install_arguments[-1], "debate-direction @ https://github.com/Afloat16/debate-direction/archive/refs/heads/main.zip")
        self.assertEqual([call for call in calls if call[0] == "debate-direction"], [["debate-direction", ["--help"]]])

    def test_offline_source_and_paths_with_spaces_are_preserved(self):
        result = self.run_installer("--source", str(self.source), "--offline", "--python", "3.12")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.calls()[0][1]
        self.assertEqual(arguments[-1], str(self.source))
        self.assertIn("--offline", arguments)
        self.assertIn("--no-python-downloads", arguments)
        self.assertIn("--managed-python", arguments)

    def test_printed_immediate_command_round_trips_shell_quoting(self):
        result = self.run_installer("--source", str(self.source))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        command = lines[lines.index("Run immediately:") + 1]
        self.assertEqual(shlex.split(command), [str(self.cli), "doctor"])
        self.assertIn(str(self.cli), result.stdout)
        self.assertIn("tool uninstall debate-direction", result.stdout)

    def test_host_is_explicit_and_not_forced(self):
        result = self.run_installer("--source", str(self.source), "--host", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1], ["debate-direction", ["install-skill", "--host", "claude"]])

    def test_force_is_forwarded_only_when_requested(self):
        result = self.run_installer("--source", str(self.source), "--host", "all", "--force-skill")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1], ["debate-direction", ["install-skill", "--host", "all", "--force"]])

    def test_uv_failure_prevents_cli_or_host_execution(self):
        self.environment["DEBATE_INSTALLER_TEST_UV_EXIT"] = "19"
        result = self.run_installer("--source", str(self.source), "--host", "codex")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertNotIn("Installed CLI:", result.stdout)

    def test_host_failure_reports_cli_as_installed_and_returns_failure(self):
        self.environment["DEBATE_INSTALLER_TEST_SKILL_EXIT"] = "4"
        result = self.run_installer("--source", str(self.source), "--host", "kimi")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Installed CLI:", result.stdout)
        self.assertIn("The CLI is installed", result.stderr)

    def test_invalid_options_fail_before_uv_runs(self):
        for arguments in (
            ("--source", str(self.source), "--ref", "main"),
            ("--offline",),
            ("--archive-url", "http://example.invalid/package.zip"),
            ("--host", "deepseek"),
            ("--force-skill",),
            ("--ref", "../main"),
            ("--python", "3.10"),
            ("--python", "3.11.1.2"),
            ("--source",),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_installer(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls(), [])

    def test_ref_and_custom_https_archive_are_literal_arguments(self):
        result = self.run_installer("--ref", "v0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0][1][-1], "debate-direction @ https://github.com/Afloat16/debate-direction/archive/v0.2.0.zip")
        self.log.unlink()
        archive = "https://example.invalid/source.zip?literal=$(not-executed)"
        result = self.run_installer("--archive-url", archive)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0][1][-1], "debate-direction @ " + archive)

    def test_help_has_no_external_side_effects(self):
        result = self.run_installer("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--offline", result.stdout)
        self.assertEqual(self.calls(), [])


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class PowerShellInstallerTests(unittest.TestCase):
    def test_installer_parses_without_errors(self):
        script_path = str(ROOT / "install.ps1").replace("'", "''")
        command = (
            "$parseTokens = $null; $parseErrors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script_path}', [ref]$parseTokens, [ref]$parseErrors) | Out-Null; "
            "if ($parseErrors.Count) { $parseErrors | Out-String | Write-Error; exit 1 }"
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
            text=True, capture_output=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_does_not_require_bootstrap_or_a_host(self):
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "install.ps1"), "-Help"],
            text=True, capture_output=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-Host", result.stdout)
        self.assertIn("-Offline", result.stdout)


if __name__ == "__main__":
    unittest.main()
