"""Artifact storage independent from build and runtime environments."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from scripts.gar_lib.artifacts.manifest import fetch_codespace_artifacts, load_deploy_files
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.config import PROJECT_ROOT
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


class ArtifactStore(Protocol):
    def latest(self, kind: ArtifactKind, workspace: Workspace) -> Artifact: ...


class BuildArtifactStore(ArtifactStore, Protocol):
    """Artifact storage operations needed by build environments."""

    def capture(self, kind: ArtifactKind, workspace: Workspace) -> Artifact: ...

    def sync_from_codespaces(self, kind: ArtifactKind, workspace: Workspace) -> Artifact: ...

    def remove(self, kind: ArtifactKind, workspace: Workspace) -> None: ...


class LocalArtifactStore:
    _MANIFEST_SECTIONS = {
        ArtifactKind.SIM_APP: "app",
        ArtifactKind.SIM_RUNTIME: "sim_env",
        ArtifactKind.TARGET_APP: "app",
    }

    _LATEST_FILE = "latest.json"
    _METADATA_FILE = "gar-artifact.json"

    def __init__(
        self,
        relative_root: Path = Path("artifacts/from-codespace"),
        snapshot_root: Path | None = None,
    ):
        self.relative_root = relative_root
        self.snapshot_root = snapshot_root or PROJECT_ROOT / ".gar" / "artifacts"

    def latest(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        bundle_path = self._latest_snapshot(kind, workspace)
        if bundle_path is None:
            # Existing workspaces may still have a pre-snapshot bundle. New
            # builds always call ``capture`` and therefore do not use this
            # compatibility path.
            legacy_bundle = self.bundle_path(workspace)
            if self._contains_kind(legacy_bundle, kind):
                return Artifact(kind=kind, workspace=workspace, bundle_path=legacy_bundle)
            bundle_path = self._kind_root(kind, workspace)

        if not self._contains_kind(bundle_path, kind):
            raise GarDomainError(f"{kind.value} artifact が壊れています。もう一度 build してください: {bundle_path}")
        self._validate_snapshot_metadata(bundle_path, kind, workspace)
        return Artifact(kind=kind, workspace=workspace, bundle_path=bundle_path)

    def capture(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        """Copy the product build output into an immutable kind-specific snapshot."""

        return self._capture_directory(kind, workspace, self.bundle_path(workspace))

    def _capture_directory(
        self,
        kind: ArtifactKind,
        workspace: Workspace,
        source: Path,
    ) -> Artifact:
        self._validate_capture_source(source)
        if not self._contains_kind(source, kind):
            raise GarDomainError(f"{kind.value} build hook が期待するartifactを生成しませんでした: {source}")

        captured_at = datetime.now(UTC)
        build_id = f"{captured_at:%Y%m%dT%H%M%S%fZ}-{uuid4().hex[:8]}"
        kind_root = self._kind_root(kind, workspace)
        kind_root.mkdir(parents=True, exist_ok=True)
        destination = kind_root / build_id

        with tempfile.TemporaryDirectory(prefix=".capture-", dir=kind_root) as temporary:
            temporary_bundle = Path(temporary) / "bundle"
            shutil.copytree(source, temporary_bundle)
            metadata = {
                "schema_version": 1,
                "kind": kind.value,
                "workspace_id": workspace.id,
                "build_id": build_id,
                "captured_at": captured_at.isoformat(),
            }
            (temporary_bundle / self._METADATA_FILE).write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_bundle, destination)

        self._write_latest_pointer(kind_root, build_id)
        return Artifact(kind=kind, workspace=workspace, bundle_path=destination)

    @staticmethod
    def _validate_capture_source(source: Path) -> None:
        if source.is_symlink() or not source.is_dir():
            raise GarDomainError(f"artifact staging directoryが不正です: {source}")
        symlink = next((path for path in sorted(source.rglob("*")) if path.is_symlink()), None)
        if symlink is not None:
            raise GarDomainError(f"artifact staging directoryにsymlinkは置けません: {symlink}")

    def sync_from_codespaces(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        """Fetch the remote staging bundle, then capture the requested kind."""

        with tempfile.TemporaryDirectory(prefix="gar-codespace-artifact-") as temporary:
            staging = Path(temporary)
            result = fetch_codespace_artifacts(
                staging,
                codespace=workspace.codespace_name,
                remote_root=f"{workspace.remote_root}/{self.relative_root.as_posix()}",
            )
            if result != 0:
                raise GarDomainError(f"Codespaces artifact の取得に失敗しました (exit {result})")
            return self._capture_directory(kind, workspace, staging)

    def remove(self, kind: ArtifactKind, workspace: Workspace) -> None:
        kind_root = self._kind_root(kind, workspace)
        if kind_root.exists():
            shutil.rmtree(kind_root)

    def _contains_kind(self, bundle_path: Path, kind: ArtifactKind) -> bool:
        section = self._MANIFEST_SECTIONS[kind]
        return load_deploy_files(bundle_path, section) is not None

    def _kind_root(self, kind: ArtifactKind, workspace: Workspace) -> Path:
        return self.snapshot_root / workspace.id / kind.value

    def _latest_snapshot(self, kind: ArtifactKind, workspace: Workspace) -> Path | None:
        kind_root = self._kind_root(kind, workspace)
        latest_path = kind_root / self._LATEST_FILE
        if not latest_path.is_file():
            return None
        try:
            payload = json.loads(latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise GarDomainError(f"artifact latest pointerを読めません: {latest_path}: {error}") from error
        build_id = payload.get("build_id") if isinstance(payload, dict) else None
        if not isinstance(build_id, str) or not build_id or Path(build_id).name != build_id:
            raise GarDomainError(f"artifact latest pointerが不正です: {latest_path}")
        snapshot = kind_root / build_id
        if not snapshot.is_dir():
            raise GarDomainError(f"artifact snapshotが見つかりません: {snapshot}")
        return snapshot

    def _write_latest_pointer(self, kind_root: Path, build_id: str) -> None:
        descriptor = json.dumps({"build_id": build_id}, ensure_ascii=False, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(prefix=".latest-", suffix=".json", dir=kind_root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(descriptor)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, kind_root / self._LATEST_FILE)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _validate_snapshot_metadata(
        self,
        bundle_path: Path,
        kind: ArtifactKind,
        workspace: Workspace,
    ) -> None:
        metadata_path = bundle_path / self._METADATA_FILE
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise GarDomainError(f"artifact metadataを読めません: {metadata_path}: {error}") from error
        if not isinstance(payload, dict):
            raise GarDomainError(f"artifact metadataが不正です: {metadata_path}")
        if payload.get("kind") != kind.value or payload.get("workspace_id") != workspace.id:
            raise GarDomainError(f"artifactの種別またはworkspaceが一致しません: {metadata_path}")

    def bundle_path(self, workspace: Workspace) -> Path:
        """Return the product hook's mutable staging directory."""

        if workspace.connection_type == "local":
            return workspace.local_root / self.relative_root
        return self.snapshot_root / workspace.id / "staging"
