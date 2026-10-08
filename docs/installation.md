# Installer reference

The installers create a per-user CLI environment with uv-managed Python 3.11 by default. Python and Git do not need to be installed first. They reuse an available uv executable or bootstrap a private copy, then install the project from a GitHub source archive. Network access is required for an initial online installation.

## One-command installation

macOS or Linux, from a POSIX-compatible shell:

```sh
curl -fsSL https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh
```

Windows, from PowerShell 5.1 or newer:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.ps1)))
```

These commands run downloaded code. To inspect it first, download the script, review it, and run the reviewed copy using your organization's permitted method. The installers do not change execution policy or request administrator privileges. Existing device policies and network restrictions still apply.

The scripts print the exact installed executable path, an immediately usable `doctor` command, a command for adding its directory to the current session's PATH, and uninstall instructions. They do not edit shell profiles or persistent user/machine PATH settings. Use the printed full path immediately, or add the printed directory to your user PATH for future terminals.

## Installation by operating system

| Environment | Installation flow | Platform detail |
| --- | --- | --- |
| macOS, Apple silicon or Intel | Open Terminal, run the POSIX one-command installer, then use the printed command path or PATH instruction. | uv selects a managed Python build for the available architecture. The CLI does not require Homebrew. |
| Linux desktop/server | Run the POSIX installer in a shell, then use the printed command path or PATH instruction. | A working HTTPS downloader and platform support for managed Python are required. Minimal distributions may need CA certificates and system runtime libraries. |
| Windows, native PowerShell | Run the PowerShell one-command installer, then use `& 'FULL_PATH' doctor` as printed. | PowerShell 5.1+; no execution-policy change or Python virtual-environment activation is required. |
| Windows Command Prompt | Open PowerShell and use the Windows command above. | The resulting `debate-direction.exe` also works from Command Prompt when its directory is on PATH. |
| Windows with WSL | Open the WSL distribution and use the Linux command there. | Install the skill in the same environment as the host. Windows and WSL have separate home directories and tool installations. |

With `wget` instead of `curl`:

```sh
wget -qO- https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh
```

After installation, run `debate-direction --demo` for an offline report, or `debate-direction setup` for live API configuration. Then use `debate-direction "Your question"`. See [provider setup](providers.md) for keys and exact model controls. If the short command is not yet discoverable, substitute the executable path printed by the installer.

Host application requirements remain separate: follow official [Codex](https://learn.chatgpt.com/docs/codex/cli), [Claude Code](https://code.claude.com/docs/en/setup), or [Kimi Code](https://moonshotai.github.io/kimi-code/en/guides/getting-started) setup. Current Kimi Code on Windows requires Git for Windows/Git Bash for its own shell. Debate Direction's standalone installer does not require Git.

## Optional host integration

Install a skill only when the host is explicitly selected:

```sh
curl -fsSL https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh -s -- --host codex
```

```powershell
& ([scriptblock]::Create((Invoke-RestMethod https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.ps1))) -Host claude
```

Accepted host values are `codex`, `claude`, `kimi`, and `all`. This passes the selection to `debate-direction install-skill --host ...`; it does not install the host application. The default is CLI only. Provider credentials and model settings are configured separately; provider names such as DeepSeek are not host names.

Existing conflicting skill content is preserved unless `--force-skill` or `-ForceSkill` is explicitly supplied. This option passes `--force` to the CLI's skill installer. A host-integration failure returns a nonzero exit code while leaving the successfully installed CLI available at the printed path.

## Options

| Shell | PowerShell | Purpose |
| --- | --- | --- |
| `--host HOST` | `-Host HOST` | Explicitly install one host integration or `all`. |
| `--force-skill` | `-ForceSkill` | Explicitly permit replacement of a conflicting skill; requires a host. |
| `--ref REF` | `-Ref REF` | Use a branch, tag, or commit; default `main`. |
| `--archive-url URL` | `-ArchiveUrl URL` | Use an explicit HTTPS archive URL. |
| `--source PATH` | `-Source PATH` | Use a local project directory, wheel, or source archive. |
| `--offline` | `-Offline` | Require local source; prohibit uv network access and Python downloads. |
| `--uv PATH` | `-UvPath PATH` | Use a specific existing uv executable. |
| `--python VERSION` | `-PythonVersion VERSION` | Select managed Python 3.11 or newer; default `3.11`. |
| `--help` | `-Help` | Display help without installing anything. |

Use only one source selector: ref, archive URL, or local source. Simple ref names may contain letters, digits, dots, underscores, and hyphens. Supply an archive URL for a branch name containing slashes. To pin an exact project revision, use its full commit ID with `--ref` or `-Ref`; `main` follows the current source and is not immutable.

PowerShell exposes `-Host` as an alias for `-TargetHost`. It never assigns to PowerShell's built-in read-only `$Host` variable. `-Uv` is also an alias for `-UvPath`.

## Local source and offline CI

### Existing Python installation

If Python 3.11+ is already available, an isolated virtual environment is an alternative. Download and extract the [source archive](https://github.com/Afloat16/debate-direction/archive/refs/heads/main.zip), open a terminal in its project directory, and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/debate-direction --demo
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install .
& .\.venv\Scripts\debate-direction.exe --demo
```

Check that the selected Python is at least 3.11. Using full executable paths avoids activation scripts. These commands install from source; this project is not claiming a published PyPI package. Developers can use `pip install -e .` inside the environment instead.

### Installer checks and offline preparation

CI can exercise the real installation before a commit is published:

```sh
sh install.sh --source . --python 3.11
```

```powershell
.\install.ps1 -Source . -PythonVersion 3.11
```

For offline installation, first prepare uv, a uv-managed Python installation, and either a local wheel or cached source-build requirements. A fresh machine cannot bootstrap from no dependencies while offline. For example, an online preparation step can install managed Python and build the wheel; the actual installer step then uses `--source path/to/debate_direction-VERSION-py3-none-any.whl --offline` or the equivalent PowerShell options. The installer never silently falls back to system Python.

Set uv's documented `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_CACHE_DIR`, and `UV_PYTHON_INSTALL_DIR` variables to temporary CI directories when isolation is needed. Do not replace the runner's home directory. Reuse those same directories for any later upgrade or uninstall command.

The installer boundary tests mock uv and the CLI to check argument handling, quoting, explicit host selection, and failure propagation without downloading a vendor installer. The configured Windows/macOS/Linux matrix also installs from real local source on Python 3.11, invokes the installed CLI, checks host-skill idempotency, and uninstalls the isolated tool. Those jobs begin with an existing uv executable; they do not exercise a fresh uv bootstrap.

## Updates and removal

Rerun the same installation command to refresh the source and reinstall the tool. Pass a different ref or archive URL to select another version. The installer uses `uv tool install --reinstall`; it does not use uv's `--force`, so an executable owned by another installation method is not silently overwritten. A direct archive installation should be updated by rerunning the installer with the desired source rather than assuming an unconstrained package-index upgrade.

To remove only the CLI, run the exact uv path printed by the installer followed by:

```text
tool uninstall debate-direction
```

This leaves optional host skills, provider configuration, uv itself, and shared managed Python installations intact. Remove a host integration separately using its documented location or host workflow. Do not delete shared uv/Python directories while other installed tools depend on them.

If uv was already present, it remains managed by its original installation method. A private bootstrap lives under `${XDG_DATA_HOME:-$HOME/.local/share}/debate-direction/uv` on macOS/Linux or `%LOCALAPPDATA%\debate-direction\uv` on Windows. The installer currently bootstraps uv `0.12.23` and reuses existing uv on subsequent runs. Manage or replace that private copy separately if uv itself needs upgrading.

## Bootstrap details and primary references

On macOS/Linux, the script uses Astral's versioned standalone installer with `UV_UNMANAGED_INSTALL` and `UV_NO_MODIFY_PATH=1`, preventing profile changes. On Windows, it downloads the official uv release ZIP for x64, ARM64, or x86, checks a pinned SHA256 checksum, and copies `uv.exe` into the private directory. This avoids the upstream PowerShell script's execution-policy prerequisite without changing any policy. Source archives and managed Python still depend on upstream platform support.

- [uv installation methods](https://docs.astral.sh/uv/getting-started/installation/)
- [uv installer path and profile options](https://docs.astral.sh/uv/reference/installer/)
- [uv Python installation and automatic downloads](https://docs.astral.sh/uv/guides/install-python/)
- [uv tool environments, upgrades, and executable handling](https://docs.astral.sh/uv/concepts/tools/)
- [uv command reference](https://docs.astral.sh/uv/reference/cli/)
- [Official uv 0.12.23 release and platform checksums](https://github.com/astral-sh/uv/releases/tag/0.12.23)
- [Microsoft PowerShell execution policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies)
