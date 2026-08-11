"""File-oriented physical targets composed from command and file channels."""

from __future__ import annotations

import contextlib
import io
import shlex
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from posixpath import dirname
from uuid import uuid4

from scripts.gar_lib.access.channel import CommandChannel, FileChannel
from scripts.gar_lib.artifacts.manifest import (
    load_deploy_files,
    resolve_artifact_src,
    target_dest_path,
)
from scripts.gar_lib.artifacts.metadata import (
    DEPLOYED_METADATA_FILENAME,
    METADATA_FILENAME,
    ArtifactMetadataError,
    load_artifact_metadata,
)
from scripts.gar_lib.artifacts.provenance import TargetToolsProvenance
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.target.compatibility import (
    ArtifactCompatibilityError,
    deployment_marker_destination,
    require_target_compatibility,
)
from scripts.gar_lib.target.environment import TargetEnvironment, TargetPlacementError
from scripts.gar_lib.target.ssh_prepare import prepare_ssh_target


class FileTransferTargetEnvironment(TargetEnvironment):
    def __init__(
        self,
        command_channel: CommandChannel,
        file_channel: FileChannel,
        *,
        base_destination: str = "/home/user",
        privileged_install: bool = False,
        prepare_recipe: Path | None = None,
        prepare_lifecycle: bool = False,
        app_install_action: str | None = "enable-app",
        active_tools_provenance: TargetToolsProvenance | None = None,
        require_active_tools_provenance: bool = False,
    ):
        self.command_channel = command_channel
        self.file_channel = file_channel
        self.base_destination = base_destination
        self.privileged_install = privileged_install
        self.prepare_recipe = prepare_recipe
        self.prepare_lifecycle = prepare_lifecycle
        self.app_install_action = app_install_action
        self.active_tools_provenance = active_tools_provenance
        self.require_active_tools_provenance = require_active_tools_provenance
        self._installer_prefix: str | None = None

    def deploy(self, artifact: Artifact) -> None:
        if artifact.kind is not ArtifactKind.TARGET_APP:
            raise GarDomainError(f"targetへ配置できないartifactです: {artifact.kind.value}")
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics):
            loaded = load_deploy_files(artifact.bundle_path, "app")
        if loaded is None:
            detail = diagnostics.getvalue().strip()
            suffix = f": {detail}" if detail else ""
            raise GarDomainError(f"target artifact manifestを読み込めません: {artifact.bundle_path}{suffix}")
        bundle_root, files = loaded
        metadata_source = artifact.bundle_path / METADATA_FILENAME if isinstance(artifact.bundle_path, Path) else None
        marker_parent = self._deployment_marker_parent(artifact, metadata_source)
        if marker_parent is not None and not self._has_application_directory(files, bundle_root, marker_parent):
            raise GarDomainError(
                "target artifact entrypointの親directoryを一括配置するdeploy fileがありません: " f"{marker_parent}"
            )

        placed_destinations: list[str] = []
        try:
            for entry in files:
                source, source_error = self._resolve_source(bundle_root, entry["src"])
                if source is None:
                    detail = f": {source_error}" if source_error else ""
                    raise GarDomainError(f"target artifact sourceがありません: {entry['src']}{detail}")
                destination = self._destination(entry["dest"])
                mode = entry.get("mode")
                if (
                    metadata_source is not None
                    and metadata_source.is_file()
                    and source.is_dir()
                    and destination == marker_parent
                ):
                    try:
                        with tempfile.TemporaryDirectory(prefix="gar-target-app-") as temporary:
                            composed_source = Path(temporary) / source.name
                            shutil.copytree(source, composed_source)
                            source_mode = stat.S_IMODE(composed_source.stat().st_mode)
                            marker = composed_source / DEPLOYED_METADATA_FILENAME
                            try:
                                composed_source.chmod(source_mode | stat.S_IWUSR)
                                shutil.copy2(metadata_source, marker)
                                marker.chmod(0o444)
                            finally:
                                composed_source.chmod(source_mode)
                            self._install_source(composed_source, destination, mode)
                    except OSError as error:
                        raise GarDomainError(f"target deploy markerを一時bundleへ配置できません: {error}") from error
                else:
                    self._install_source(source, destination, mode)
                placed_destinations.append(destination)

            if self.privileged_install and self.app_install_action is not None:
                self._install_deployed_apps(files, self.app_install_action)
        except Exception as error:
            if not placed_destinations:
                raise
            raise TargetPlacementError(
                str(error),
                placed_destinations=tuple(placed_destinations),
                placement_complete=len(placed_destinations) == len(files),
            ) from error

    def validate_deployment(self, artifact: Artifact) -> None:
        """Reject corrupt or incompatible Linux artifacts before any file transfer."""

        if self.require_active_tools_provenance and self.active_tools_provenance is None:
            raise ArtifactCompatibilityError("target tools provenanceを解決できないため転送前にdeployを拒否しました")
        require_target_compatibility(
            artifact,
            self.command_channel,
            active_tools=self.active_tools_provenance,
        )

    def prepare(self) -> None:
        if not self.privileged_install:
            raise GarDomainError("この実機接続方式には target prepare は不要です")
        if self.prepare_recipe is None:
            raise GarDomainError("選択したTargetには実機環境用のprepare recipeがありません")
        provenance = self.active_tools_provenance
        if provenance is None or provenance.target_id is None:
            raise GarDomainError("target prepare: active gar-tools provenanceを解決できません")
        host = getattr(self.command_channel, "host", None)
        if not isinstance(host, str) or not host:
            raise GarDomainError("target prepare: SSH hostが未設定です")
        config_path = getattr(self.command_channel, "config_path", None)
        prepare_ssh_target(
            host,
            self.prepare_recipe,
            target_id=provenance.target_id,
            recipe_version=provenance.target_recipe_version,
            gar_tools_commit=provenance.gar_tools_commit,
            config_path=config_path if isinstance(config_path, Path) else None,
            include_lifecycle=self.prepare_lifecycle,
        )

    def _install_source(self, source: Path, destination: str, mode: object) -> None:
        if self._requires_privilege(destination):
            self._install_privileged(source, destination, mode)
        else:
            self._install_unprivileged(source, destination, mode)

    def _install_unprivileged(self, source: Path, destination: str, mode: object) -> None:
        parent = dirname(destination)
        if parent:
            prepared = self.command_channel.run(f"mkdir -p {shlex.quote(parent)}")
            self._require_success(prepared, "target artifact配置先を作成できません")
        transferred = self.file_channel.push(source, destination)
        self._require_success(transferred, "target artifact転送に失敗しました")
        if isinstance(mode, str):
            result = self.command_channel.run(f"chmod {shlex.quote(mode)} {shlex.quote(destination)}")
            self._require_success(result, "target artifactのmode設定に失敗しました")

    def _install_privileged(self, source: Path, destination: str, mode: object) -> None:
        """Stage via the SSH user, then install system files through sudo.

        scp cannot write an arbitrary root-owned path.  Keeping the transfer
        and the privileged installation separate also avoids root SSH login.
        ``sudo -n`` deliberately fails with a useful error until the target
        has been provisioned for non-interactive GAR deployment.
        """
        stage = self._staging_path()
        prepared = self.command_channel.run(f"mkdir -p {shlex.quote(stage)}")
        self._require_success(prepared, "target artifact一時配置先を作成できません")

        staged_source = f"{stage}/payload"
        try:
            transferred = self.file_channel.push(source, staged_source)
            self._require_success(transferred, "target artifactの一時転送に失敗しました")

            normalized_mode = mode if isinstance(mode, str) else "0755"
            installer = self._installer_command()
            installed = self.command_channel.run(
                f"{installer} install "
                f"{shlex.quote(staged_source)} {shlex.quote(destination)} {shlex.quote(normalized_mode)}"
            )
            self._require_success(installed, "target artifactを限定installerで配置できません")
        finally:
            self.command_channel.run(f"rm -rf -- {shlex.quote(stage)}")

    def _install_deployed_apps(self, files: list[dict], action: str) -> None:
        app_prefix = "/opt/gar/apps/"
        apps = [
            entry["dest"][len(app_prefix) :]
            for entry in files
            if entry["dest"].startswith(app_prefix) and "/" not in entry["dest"][len(app_prefix) :]
        ]
        if not apps:
            return
        installer = self._installer_command()
        for app in apps:
            result = self.command_channel.run(f"{installer} {shlex.quote(action)} " + shlex.quote(app))
            self._require_success(result, "target applicationをruntimeへ登録できません")

    def _installer_command(self) -> str:
        """Use the constrained installer directly for root SSH targets.

        Raspberry Pi OS normally connects as an unprivileged user and needs
        ``sudo -n``.  Small Buildroot boards commonly expose only a root SSH
        account and do not ship sudo at all.  Both still use the same
        Target-owned installer contract.
        """

        if self._installer_prefix is None:
            result = self.command_channel.run("id -u")
            stdout = getattr(result, "stdout", "")
            is_root = getattr(result, "returncode", 1) == 0 and isinstance(stdout, str) and stdout.strip() == "0"
            self._installer_prefix = "" if is_root else "sudo -n "
        return f"{self._installer_prefix}/usr/local/lib/gar/gar-target-install"

    def _staging_path(self) -> str:
        return f"/tmp/gar-stage-{uuid4().hex}"

    def _requires_privilege(self, destination: str) -> bool:
        return self.privileged_install and not destination.startswith("/home/")

    def _deployment_marker_parent(self, artifact: Artifact, metadata_source: Path | None) -> str | None:
        if metadata_source is None or not metadata_source.is_file():
            return None
        try:
            metadata = load_artifact_metadata(artifact.bundle_path)
        except ArtifactMetadataError as error:
            raise GarDomainError(str(error)) from error
        if metadata is None:
            return None
        return str(PurePosixPath(deployment_marker_destination(metadata)).parent)

    def _has_application_directory(
        self,
        files: list[dict],
        bundle_root: Path,
        marker_parent: str,
    ) -> bool:
        for entry in files:
            if self._destination(entry["dest"]) != marker_parent:
                continue
            source, _ = self._resolve_source(bundle_root, entry["src"])
            if source is not None and source.is_dir():
                return True
        return False

    @staticmethod
    def _resolve_source(bundle_root: Path, source: str) -> tuple[Path | None, str]:
        diagnostics = io.StringIO()
        with contextlib.redirect_stderr(diagnostics):
            resolved = resolve_artifact_src(bundle_root, source)
        return resolved, diagnostics.getvalue().strip()

    def _require_success(self, result: object, message: str) -> None:
        returncode = getattr(result, "returncode", 1)
        if returncode == 0:
            return
        detail = (getattr(result, "stderr", "") or getattr(result, "stdout", "")).strip()
        lowered = detail.lower()
        if self._installer_prefix and any(
            marker in lowered
            for marker in (
                "a password is required",
                "not in the sudoers",
                "not allowed to execute",
                "may not run sudo",
            )
        ):
            host = getattr(self.command_channel, "host", "target")
            raise AccessConnectionError(
                channel="ssh",
                endpoint=host if isinstance(host, str) else "target",
                reason="target_prepare_required",
                returncode=int(returncode),
            )
        suffix = f": {detail}" if detail else ""
        raise GarDomainError(f"{message} (exit {returncode}){suffix}")

    def _destination(self, destination: str) -> str:
        if destination == "~":
            return self.base_destination
        if destination.startswith("~/"):
            return f"{self.base_destination.rstrip('/')}/{destination[2:]}"
        return target_dest_path(destination, self.base_destination)
