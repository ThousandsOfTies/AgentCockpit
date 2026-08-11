"""Collect reproducible build inputs for artifact snapshot metadata."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from scripts.gar_lib.artifacts.metadata import UNKNOWN_PROVENANCE, ArtifactTarget
from scripts.gar_lib.core.tools_repository import gar_tools_root
from scripts.gar_lib.core.workspace import Workspace

_REMOTE_DIRTY = "__GAR_DIRTY__"


@dataclass(frozen=True)
class CaptureProvenance:
    source_commit: str = UNKNOWN_PROVENANCE
    gar_tools_commit: str = UNKNOWN_PROVENANCE
    target: ArtifactTarget = field(default_factory=ArtifactTarget)
    target_recipe_version: str | None = None


@dataclass(frozen=True)
class TargetToolsProvenance:
    """Identity of the gar-tools copy used to operate a physical Target."""

    target_id: str | None = None
    gar_tools_commit: str = UNKNOWN_PROVENANCE
    target_recipe_version: str = UNKNOWN_PROVENANCE


def collect_capture_provenance(
    workspace: Workspace,
    target_id: str | None,
    *,
    source_commit: str | None = None,
    gar_tools_commit: str | None = None,
) -> CaptureProvenance:
    """Collect commits and the selected Target's declared compatibility."""

    tools_root = _workspace_tools_root(workspace)
    if workspace.connection_type == "local":
        if source_commit is None:
            source_commit = _git_commit(workspace.local_root)
    elif workspace.connection_type == "codespaces" and (source_commit is None or gar_tools_commit is None):
        remote_source, remote_tools = _codespaces_git_commits(workspace)
        source_commit = source_commit or remote_source
        gar_tools_commit = gar_tools_commit or remote_tools
    if gar_tools_commit is None:
        gar_tools_commit = _git_commit(tools_root)

    target = ArtifactTarget(id=target_id)
    recipe_version = None
    if target_id is not None:
        target_path = tools_root / "targets" / target_id / "target.json"
        target, recipe_version = _read_target_provenance(
            target_path,
            target_id,
            workspace.selected_environments.target,
        )

    return CaptureProvenance(
        source_commit=source_commit or UNKNOWN_PROVENANCE,
        gar_tools_commit=gar_tools_commit or UNKNOWN_PROVENANCE,
        target=target,
        target_recipe_version=recipe_version,
    )


def collect_target_tools_provenance(
    target_manifest_path: Path,
    backend_id: str | None,
    *,
    target_id: str | None = None,
) -> TargetToolsProvenance:
    """Measure the exact local gar-tools copy selected for Target operations."""

    repository_root = target_manifest_path.parent.parent.parent
    _, recipe_version = _read_target_provenance(
        target_manifest_path,
        target_manifest_path.parent.name,
        backend_id,
    )
    return TargetToolsProvenance(
        target_id=target_id or target_manifest_path.parent.name,
        gar_tools_commit=_git_commit(repository_root) or UNKNOWN_PROVENANCE,
        target_recipe_version=recipe_version,
    )


def _workspace_tools_root(workspace: Workspace) -> Path:
    if workspace.connection_type == "local":
        candidate = workspace.local_root / "sources" / "gar-tools"
        if candidate.is_dir():
            return candidate
    return gar_tools_root()


def _git_commit(root: Path) -> str | None:
    if not root.is_dir():
        return None
    status = _git_output(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
        "--ignore-submodules=none",
    )
    if status is None or status:
        return None
    value = _git_output(root, "rev-parse", "HEAD")
    return value if value is not None and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) else None


def _git_output(root: Path, *arguments: str) -> str | None:
    try:
        process = subprocess.Popen(
            ("git", "-C", str(root), *arguments),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        stdout, _ = process.communicate()
    except OSError:
        return None
    if process.returncode != 0:
        return None
    return stdout.strip()


def _codespaces_git_commits(workspace: Workspace) -> tuple[str | None, str | None]:
    remote_root = workspace.remote_root
    command = "; ".join(
        (
            _remote_git_identity_command(remote_root, "gar_source_status", 31),
            _remote_git_identity_command(
                remote_root + "/sources/gar-tools",
                "gar_tools_status",
                32,
            ),
        )
    )
    try:
        process = subprocess.Popen(
            (
                "gh",
                "codespace",
                "ssh",
                "-c",
                workspace.codespace_name,
                "--",
                command,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        stdout, _ = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return None, None
    except OSError:
        return None, None
    if process.returncode != 0:
        return None, None
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 2:
        return None, None
    return _remote_commit(lines[0]), _remote_commit(lines[1])


def _remote_git_identity_command(root: str, variable: str, failure_exit: int) -> str:
    quoted_root = shlex.quote(root)
    return (
        f"{variable}=$(git -C {quoted_root} status --porcelain=v1 "
        "--untracked-files=normal --ignore-submodules=none) "
        f"|| exit {failure_exit}; "
        f"if [ -n \"${variable}\" ]; then printf '%s\\n' {_REMOTE_DIRTY}; "
        f"else git -C {quoted_root} rev-parse HEAD; fi"
    )


def _remote_commit(value: str) -> str | None:
    if value == _REMOTE_DIRTY:
        return None
    return value if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) else None


def _read_target_provenance(
    path: Path,
    target_id: str,
    backend_id: str | None,
) -> tuple[ArtifactTarget, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ArtifactTarget(id=target_id), UNKNOWN_PROVENANCE
    if not isinstance(payload, dict):
        return ArtifactTarget(id=target_id), UNKNOWN_PROVENANCE

    raw_compatibility = payload.get("compatibility")
    compatibility = raw_compatibility if isinstance(raw_compatibility, dict) else {}
    target = ArtifactTarget(
        id=target_id,
        architecture=_string(compatibility.get("architecture")),
        abi=_string(compatibility.get("abi")),
        libc=_string(compatibility.get("libc")),
        toolchain_triple=_string(compatibility.get("toolchainTriple")),
    )

    raw_provisioning = payload.get("provisioning")
    provisioning = raw_provisioning if isinstance(raw_provisioning, dict) else {}
    raw_recipe = provisioning.get(backend_id) if backend_id is not None else None
    recipe = raw_recipe if isinstance(raw_recipe, dict) else {}
    version = recipe.get("recipeVersion")
    if isinstance(version, str | int) and not isinstance(version, bool) and str(version):
        return target, str(version)
    return target, _target_tree_digest(path.parent)


def _target_tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return UNKNOWN_PROVENANCE
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
