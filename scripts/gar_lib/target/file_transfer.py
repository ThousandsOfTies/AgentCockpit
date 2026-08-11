"""File-oriented physical targets composed from command and file channels."""

from __future__ import annotations

import shlex
from pathlib import Path
from posixpath import dirname
from uuid import uuid4

from scripts.gar_lib.access.channel import CommandChannel, FileChannel
from scripts.gar_lib.artifacts.manifest import (
    load_deploy_files,
    resolve_artifact_src,
    target_dest_path,
)
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.target.environment import TargetEnvironment
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
    ):
        self.command_channel = command_channel
        self.file_channel = file_channel
        self.base_destination = base_destination
        self.privileged_install = privileged_install
        self.prepare_recipe = prepare_recipe
        self._installer_prefix: str | None = None

    def deploy(self, artifact: Artifact) -> None:
        if artifact.kind is not ArtifactKind.TARGET_APP:
            raise GarDomainError(f"targetへ配置できないartifactです: {artifact.kind.value}")
        loaded = load_deploy_files(artifact.bundle_path, "app")
        if loaded is None:
            raise GarDomainError(f"target artifact manifestを読み込めません: {artifact.bundle_path}")
        bundle_root, files = loaded

        for entry in files:
            source = resolve_artifact_src(bundle_root, entry["src"])
            if source is None:
                raise GarDomainError(f"target artifact sourceがありません: {entry['src']}")
            destination = self._destination(entry["dest"])
            mode = entry.get("mode")
            if self._requires_privilege(destination):
                self._install_privileged(source, destination, mode)
            else:
                self._install_unprivileged(source, destination, mode)

        if self.privileged_install:
            self._enable_deployed_apps(files)

    def prepare(self) -> None:
        if not self.privileged_install:
            raise GarDomainError("この実機接続方式には target prepare は不要です")
        if self.prepare_recipe is None:
            raise GarDomainError("選択したTargetには実機環境用のprepare recipeがありません")
        host = getattr(self.command_channel, "host", None)
        if not isinstance(host, str) or not host:
            raise GarDomainError("target prepare: SSH hostが未設定です")
        config_path = getattr(self.command_channel, "config_path", None)
        prepare_ssh_target(
            host,
            self.prepare_recipe,
            config_path=config_path if isinstance(config_path, Path) else None,
        )

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

    def _enable_deployed_apps(self, files: list[dict]) -> None:
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
            result = self.command_channel.run(f"{installer} enable-app " + shlex.quote(app))
            self._require_success(result, "target application serviceを有効化できません")

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

    @staticmethod
    def _require_success(result: object, message: str) -> None:
        returncode = getattr(result, "returncode", 1)
        if returncode == 0:
            return
        detail = (getattr(result, "stderr", "") or getattr(result, "stdout", "")).strip()
        suffix = f": {detail}" if detail else ""
        raise GarDomainError(f"{message} (exit {returncode}){suffix}")

    def _destination(self, destination: str) -> str:
        if destination == "~":
            return self.base_destination
        if destination.startswith("~/"):
            return f"{self.base_destination.rstrip('/')}/{destination[2:]}"
        return target_dest_path(destination, self.base_destination)
