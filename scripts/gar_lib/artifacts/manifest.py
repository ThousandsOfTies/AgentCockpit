"""``artifact.json`` manifest parsing and Codespace artifact fetching.

Shared by simulation and target environment deploy operations and explicit
artifact fetch commands.

artifact.json スキーマ:
  deploy.app     — target app バイナリ（VM ・実機共通）
  deploy.sim_env — VM 専用環境インフラ（CUSE stubs / web-bridge）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from scripts.gar_lib.access.codespaces import select_codespace_from_list
from scripts.gar_lib.core.config import PROJECT_ROOT

DEFAULT_CODESPACE_ARTIFACT_ROOT = "/workspaces/gar-build-env/artifacts/from-codespace"


class ArtifactManifestError(ValueError):
    """An artifact manifest is structurally invalid."""


@dataclass(frozen=True)
class DeployFile:
    """One file copied from an artifact bundle to a deployment destination."""

    src: str
    dest: str
    mode: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"src": self.src, "dest": self.dest}
        if self.mode is not None:
            payload["mode"] = self.mode
        return payload


@dataclass(frozen=True)
class DeploySection:
    """One named consumer of an artifact bundle.

    ``files`` is GAR's deploy contract. ``artifact`` is also accepted because
    product manifests use it to point at a bundle consumed by another tool.
    Both forms contribute sources when a bundle is fetched from Codespaces.
    """

    name: str
    files: tuple[DeployFile, ...] = ()
    artifact: str | None = None

    @property
    def sources(self) -> tuple[str, ...]:
        file_sources = tuple(file.src for file in self.files)
        return (*file_sources, *((self.artifact,) if self.artifact else ()))


@dataclass(frozen=True)
class ArtifactManifest:
    """Validated representation of ``artifact.json``."""

    name: str | None
    deploy: Mapping[str, DeploySection]
    target: str | None = None
    entrypoint: str | None = None

    def section(self, name: str) -> DeploySection:
        try:
            return self.deploy[name]
        except KeyError as exc:
            raise ArtifactManifestError(f"artifact manifest has no deploy.{name} section") from exc

    @property
    def sources(self) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for section in self.deploy.values():
            for source in section.sources:
                if source not in seen:
                    seen.add(source)
                    ordered.append(source)
        return tuple(ordered)


def parse_artifact_manifest(payload: object) -> ArtifactManifest:
    """Validate untrusted JSON and return the typed artifact model."""

    if not isinstance(payload, dict):
        raise ArtifactManifestError("invalid artifact manifest: root must be an object")

    raw_name = payload.get("name")
    if raw_name is not None and not isinstance(raw_name, str):
        raise ArtifactManifestError("invalid artifact manifest: name must be a string")

    raw_target = payload.get("target")
    if raw_target is not None and not (isinstance(raw_target, str) and raw_target):
        raise ArtifactManifestError("invalid artifact manifest: target must be a non-empty string or null")

    raw_entrypoint = payload.get("entrypoint")
    if raw_entrypoint is not None and not (isinstance(raw_entrypoint, str) and raw_entrypoint):
        raise ArtifactManifestError("invalid artifact manifest: entrypoint must be a non-empty string or null")

    raw_deploy = payload.get("deploy")
    if not isinstance(raw_deploy, dict):
        raise ArtifactManifestError("invalid artifact manifest: deploy must be an object")

    deploy: dict[str, DeploySection] = {}
    for section_name, raw_section in raw_deploy.items():
        if not isinstance(section_name, str) or not section_name:
            raise ArtifactManifestError("invalid artifact manifest: deploy section names must be non-empty strings")
        if not isinstance(raw_section, dict):
            raise ArtifactManifestError(f"invalid artifact manifest: deploy.{section_name} must be an object")

        has_files = "files" in raw_section
        has_artifact = "artifact" in raw_section
        if not has_files and not has_artifact:
            raise ArtifactManifestError(f"invalid artifact manifest: deploy.{section_name} requires files or artifact")

        files: list[DeployFile] = []
        if has_files:
            raw_files = raw_section["files"]
            if not isinstance(raw_files, list) or not raw_files:
                raise ArtifactManifestError(f"artifact manifest deploy.{section_name}.files must be a non-empty list")
            for index, raw_file in enumerate(raw_files):
                location = f"deploy.{section_name}.files[{index}]"
                if not isinstance(raw_file, dict):
                    raise ArtifactManifestError(f"artifact manifest {location} must be an object")
                src = raw_file.get("src")
                dest = raw_file.get("dest")
                if not isinstance(src, str) or not src or not isinstance(dest, str) or not dest:
                    raise ArtifactManifestError(f"artifact manifest {location} requires non-empty string src and dest")
                mode = raw_file.get("mode")
                if mode is not None and not (isinstance(mode, str) and re.fullmatch(r"[0-7]{3,4}", mode)):
                    raise ArtifactManifestError(f"artifact manifest {location}.mode must match [0-7]{{3,4}}")
                files.append(DeployFile(src=src, dest=dest, mode=mode))

        raw_artifact = raw_section.get("artifact")
        if raw_artifact is not None and not (isinstance(raw_artifact, str) and raw_artifact):
            raise ArtifactManifestError(
                f"artifact manifest deploy.{section_name}.artifact must be a non-empty string or null"
            )
        deploy[section_name] = DeploySection(
            name=section_name,
            files=tuple(files),
            artifact=raw_artifact,
        )

    return ArtifactManifest(
        name=raw_name,
        deploy=deploy,
        target=raw_target,
        entrypoint=raw_entrypoint,
    )


def default_artifacts_dir() -> Path:
    return PROJECT_ROOT.parent / "gar-build-env" / "artifacts" / "from-codespace"


def default_codespace_artifact_root() -> str:
    return os.environ.get("GAR_CODESPACE_ARTIFACT_ROOT", DEFAULT_CODESPACE_ARTIFACT_ROOT)


def select_codespace(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    env_value = os.environ.get("GAR_CODESPACE_NAME") or os.environ.get("CODESPACE_NAME")
    if env_value:
        return env_value

    result = subprocess.run(
        ["gh", "codespace", "list"],
        check=False,
        capture_output=True,
        text=True,
        env=gh_env(),
    )
    if result.returncode != 0:
        print("gar target fetch: failed to list Codespaces", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return None
    return select_codespace_from_list(result.stdout)


def gh_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GH_PROMPT_DISABLED", "1")
    return env


def artifact_manifest_deploy_sources(manifest: object) -> list[str] | None:
    """Return every source that must be copied with the manifest.

    This compatibility wrapper keeps the command-oriented ``None`` result,
    while all structural validation lives in ``parse_artifact_manifest``.
    """

    try:
        return list(parse_artifact_manifest(manifest).sources)
    except ArtifactManifestError as error:
        print(error, file=sys.stderr)
        return None


def fetch_codespace_artifacts(
    root: Path,
    *,
    codespace: str | None = None,
    remote_root: str | None = None,
) -> int:
    selected_codespace = select_codespace(codespace)
    if not selected_codespace:
        print("gar target fetch: pass --codespace NAME or set GAR_CODESPACE_NAME", file=sys.stderr)
        return 1

    resolved_remote_root = (remote_root or default_codespace_artifact_root()).rstrip("/")
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="gar-artifact-fetch-") as tmp:
        manifest_tmp = Path(tmp) / "artifact.json"
        result = gh_codespace_cp(
            selected_codespace,
            f"{resolved_remote_root}/artifact.json",
            manifest_tmp,
        )
        if result.returncode != 0:
            print(
                f"gar target fetch: failed to fetch {resolved_remote_root}/artifact.json",
                file=sys.stderr,
            )
            return result.returncode

        try:
            manifest = json.loads(manifest_tmp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"invalid artifact manifest JSON from Codespace: {exc}", file=sys.stderr)
            return 1
        try:
            parsed_manifest = parse_artifact_manifest(manifest)
        except ArtifactManifestError as error:
            print(error, file=sys.stderr)
            return 1

        for src in parsed_manifest.sources:
            if src.startswith("/") or ".." in Path(src).parts:
                print(f"artifact src escapes bundle root: {src}", file=sys.stderr)
                return 1
            local_dest = root / src
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            if local_dest.is_dir():
                shutil.rmtree(local_dest)
            elif local_dest.exists():
                local_dest.unlink()
            result = gh_codespace_cp(
                selected_codespace,
                f"{resolved_remote_root}/{src}",
                local_dest,
                recursive=True,
            )
            if result.returncode != 0:
                print(f"gar target fetch: failed to fetch {src}", file=sys.stderr)
                return result.returncode

        (root / "artifact.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Codespace: {selected_codespace}")
    print(f"Artifacts: {root}")
    return 0


def gh_codespace_cp(
    codespace: str,
    remote_path: str,
    local_path: Path,
    *,
    recursive: bool = False,
) -> subprocess.CompletedProcess:
    command = ["gh", "codespace", "cp", "-e", "-c", codespace]
    if recursive:
        command.append("-r")
    command.extend([f"remote:{remote_path}", str(local_path)])
    return subprocess.run(command, check=False, env=gh_env())


def find_artifact_manifest(root: Path) -> Path | None:
    direct = root / "artifact.json"
    if direct.exists():
        return direct

    candidates = sorted(path for path in root.iterdir() if (path / "artifact.json").exists()) if root.exists() else []
    if len(candidates) == 1:
        return candidates[0] / "artifact.json"
    return None


def load_artifact_manifest(root: Path) -> tuple[Path, ArtifactManifest] | None:
    manifest_path = find_artifact_manifest(root)
    if manifest_path is None:
        print(f"missing artifact manifest: {root / 'artifact.json'}", file=sys.stderr)
        return None

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid artifact manifest JSON: {manifest_path}: {exc}", file=sys.stderr)
        return None

    try:
        manifest = parse_artifact_manifest(data)
    except ArtifactManifestError as error:
        print(f"{error}: {manifest_path}", file=sys.stderr)
        return None

    return manifest_path.parent, manifest


def artifact_deploy_files(
    manifest: ArtifactManifest | object,
    target: str,
) -> list[dict[str, str]] | None:
    """Return deploy files for *target* section."""
    try:
        parsed = manifest if isinstance(manifest, ArtifactManifest) else parse_artifact_manifest(manifest)
        section = parsed.section(target)
        if not section.files:
            raise ArtifactManifestError(f"artifact manifest deploy.{target}.files must be a non-empty list")
        return [entry.as_dict() for entry in section.files]
    except ArtifactManifestError as error:
        print(error, file=sys.stderr)
        return None


def resolve_artifact_src(bundle_root: Path, src: str) -> Path | None:
    source_path = Path(src)
    if source_path.is_absolute() or ".." in source_path.parts:
        print(f"artifact src escapes bundle root: {src}", file=sys.stderr)
        return None

    current = bundle_root
    if current.is_symlink():
        print(f"artifact src uses symlink: {current}", file=sys.stderr)
        return None
    for part in source_path.parts:
        current /= part
        if current.is_symlink():
            print(f"artifact src uses symlink: {current}", file=sys.stderr)
            return None

    resolved_root = bundle_root.resolve()
    source = (resolved_root / source_path).resolve()
    try:
        source.relative_to(resolved_root)
    except ValueError:
        print(f"artifact src escapes bundle root: {src}", file=sys.stderr)
        return None

    if not source.exists():
        print(f"missing artifact: {source}", file=sys.stderr)
        return None

    if source.is_dir():
        nested_symlink = next(
            (path for path in sorted(source.rglob("*")) if path.is_symlink()),
            None,
        )
        if nested_symlink is not None:
            print(f"artifact src uses symlink: {nested_symlink}", file=sys.stderr)
            return None

    return source


def load_deploy_files(root: Path, target: str) -> tuple[Path, list[dict]] | None:
    loaded = load_artifact_manifest(root)
    if loaded is None:
        return None

    bundle_root, manifest = loaded
    files = artifact_deploy_files(manifest, target)
    if files is None:
        return None

    return bundle_root, files


def target_dest_path(manifest_dest: str, base_dest: str) -> str:
    if manifest_dest.startswith(("/", "~")):
        return manifest_dest
    return f"{base_dest.rstrip('/')}/{manifest_dest}"
