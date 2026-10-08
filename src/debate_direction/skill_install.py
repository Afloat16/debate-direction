"""Install the bundled portable skill without changing host model settings."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from . import __version__
from .config import ConfigError

HOSTS = ("codex", "claude", "kimi")
SKILL_NAME = "debate-direction"
MARKER = ".debate-direction-install.json"
INVOCATIONS = {"codex": "$debate-direction", "claude": "/debate-direction", "kimi": "/skill:debate-direction"}


def skill_root(host: str, *, project: Path | None = None) -> Path:
    if host not in HOSTS:
        raise ConfigError("host must be codex, claude or kimi")
    folder = {"codex": ".agents", "claude": ".claude", "kimi": ".kimi-code"}[host]
    if project is not None:
        return project.expanduser().resolve() / folder / "skills"
    if host == "kimi" and os.environ.get("KIMI_CODE_HOME"):
        return Path(os.environ["KIMI_CODE_HOME"]).expanduser() / "skills"
    return Path.home() / folder / "skills"


def bundled_skill() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    root = resources.files("debate_direction").joinpath("_skill")

    def visit(directory, prefix=""):
        for child in directory.iterdir():
            name = prefix + child.name
            if child.is_dir():
                visit(child, name + "/")
            elif child.name.endswith((".md", ".yaml", ".yml")):
                files[name] = child.read_bytes()

    try:
        visit(root)
    except (FileNotFoundError, NotADirectoryError):
        raise ConfigError("the installed package is missing its skill bundle; reinstall debate-direction") from None
    if "SKILL.md" not in files:
        raise ConfigError("the installed package has no SKILL.md; reinstall debate-direction")
    return files


def _hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}


def _existing_files(target: Path) -> dict[str, bytes]:
    files = {}
    if target.is_symlink() or not target.is_dir():
        raise ConfigError(f"skill destination is not a regular directory: {target}")
    for item in target.rglob("*"):
        if item.is_symlink():
            raise ConfigError(f"skill installation contains a symbolic link; select a different --skills-dir: {target}")
        if item.is_file() and item != target / MARKER:
            if item.stat().st_size > 1024 * 1024:
                raise ConfigError(f"skill installation contains an unexpected large file: {target}")
            files[item.relative_to(target).as_posix()] = item.read_bytes()
    return files


def _owned_and_unmodified(target: Path, files: dict[str, bytes]) -> bool:
    try:
        raw = (target / MARKER).read_bytes()
        if len(raw) > 65536:
            return False
        marker = json.loads(raw)
        return marker.get("tool") == SKILL_NAME and marker.get("files") == _hashes(files)
    except (OSError, ValueError, AttributeError):
        return False


def install_skill(host: str, *, project: Path | None = None,
                  skills_dir: Path | None = None, force: bool = False,
                  dry_run: bool = False) -> dict:
    """Copy only this skill. Differing local content requires explicit force.

    Every replaced directory is retained outside the scanned skills root. An unchanged
    installation is a no-op; an unmodified owned installation can be upgraded.
    """
    if host not in HOSTS:
        raise ConfigError("host must be codex, claude or kimi")
    if skills_dir is not None and project is not None:
        raise ConfigError("use --skills-dir or --project, not both")
    root = skills_dir.expanduser().absolute() if skills_dir is not None else skill_root(host, project=project)
    target = root / SKILL_NAME
    files = bundled_skill()
    result = {"host": host, "path": str(target), "invocation": INVOCATIONS[host], "status": "installed"}
    exists = target.exists() or target.is_symlink()
    if exists:
        current = _existing_files(target)
        if current == files:
            result["status"] = "unchanged"
            return result
        if not force and not _owned_and_unmodified(target, current):
            raise ConfigError(f"preserved an existing or modified skill at {target}; use --force to replace it with a backup")
        result["status"] = "updated"
    if dry_run:
        result["status"] = "would_update" if exists else "would_install"
        return result
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".debate-direction-", dir=root))
    backup = None
    try:
        for name, body in files.items():
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
        (stage / MARKER).write_text(json.dumps({"tool": SKILL_NAME, "version": __version__, "files": _hashes(files)}, indent=2) + "\n", encoding="utf-8")
        # Recheck before mutation so a changed destination is never silently lost.
        if exists:
            if _existing_files(target) != current:
                raise ConfigError("skill destination changed during installation; retry after reviewing it")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_root = root.parent / "debate-direction-backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / (f"{host}-{stamp}-" + uuid.uuid4().hex[:8])
            target.rename(backup)
            result["backup"] = str(backup)
        elif target.exists() or target.is_symlink():
            raise ConfigError("skill destination appeared during installation; no files were overwritten")
        try:
            stage.rename(target)
        except OSError:
            if backup is not None and not target.exists():
                backup.rename(target)
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return result
