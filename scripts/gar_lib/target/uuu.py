"""Configuration-driven NXP Universal Update Utility target backend."""

from __future__ import annotations

from pathlib import Path

from scripts.gar_lib.access.serial import PySerialPatternVerifier, SerialPatternVerifier
from scripts.gar_lib.access.uuu import LocalUuuCommandChannel, UuuCommandChannel
from scripts.gar_lib.artifacts.manifest import load_deploy_files, resolve_artifact_src
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.target.environment import TargetEnvironment
from scripts.gar_lib.target.manifest import TargetManifest


class UuuTargetEnvironment(TargetEnvironment):
    """Flash a product-owned full Linux image using the selected Target recipe."""

    def __init__(
        self,
        manifest: TargetManifest,
        *,
        console_port: str | None = None,
        command_channel: UuuCommandChannel | None = None,
        serial_verifier: SerialPatternVerifier | None = None,
    ):
        self.manifest = manifest
        self.settings = manifest.provisioning_settings("uuu")
        self.console_port = console_port
        self.command_channel = command_channel or LocalUuuCommandChannel()
        self.serial_verifier = serial_verifier or PySerialPatternVerifier()

    def prepare(self) -> None:
        raise GarDomainError("UUU接続には target prepare は不要です。boot modeをserial downloaderへ切り替えてください")

    def validate_deployment(self, artifact: Artifact) -> None:
        self._image(artifact)

    def deploy(self, artifact: Artifact) -> None:
        image = self._image(artifact)
        command = self.settings.get("command")
        if not isinstance(command, list) or not command:
            raise GarDomainError(f"Target {self.manifest.id} のUUU command設定がありません")
        args = [self._expand(item, image, artifact.bundle_path) for item in command]
        result = self.command_channel.run(args, cwd=image.parent)
        if result.returncode != 0:
            raise GarDomainError(f"UUUによるイメージ書き込みに失敗しました (exit {result.returncode})")
        self._verify_serial_boot()

    def _image(self, artifact: Artifact) -> Path:
        if artifact.kind is not ArtifactKind.TARGET_APP:
            raise GarDomainError(f"UUU targetへ配置できないartifactです: {artifact.kind.value}")
        section = self.settings.get("imageSection", "image")
        if not isinstance(section, str) or not section:
            raise GarDomainError(f"Target {self.manifest.id} のimageSection設定が不正です")
        loaded = load_deploy_files(artifact.bundle_path, section)
        if loaded is None:
            raise GarDomainError(
                f"UUU artifactにはdeploy.{section}.filesでフルイメージを指定してください: {artifact.bundle_path}"
            )
        bundle_root, files = loaded
        if len(files) != 1:
            raise GarDomainError(f"UUU artifactのdeploy.{section}.filesは1つのイメージに限定してください")
        source = resolve_artifact_src(bundle_root, files[0]["src"])
        if source is None or not source.is_file():
            raise GarDomainError(f"UUU image artifactがありません: {files[0]['src']}")
        return source

    @staticmethod
    def _expand(value: str, image: Path, artifact_root: Path) -> str:
        return value.replace("{image}", str(image)).replace("{artifact}", str(artifact_root))

    def _verify_serial_boot(self) -> None:
        settings = self.settings.get("serialVerify")
        if settings is None:
            return
        if not isinstance(settings, dict):
            raise GarDomainError("UUU serialVerify設定が不正です")
        if not self.console_port:
            raise GarDomainError(
                "UUU書き込み後のserial確認にはworkspace target.serialへUSB-C debug UARTのdevice pathを設定してください"
            )
        pattern = settings.get("pattern")
        baud = settings.get("baud", 115200)
        timeout = settings.get("timeoutSeconds", 30)
        if not isinstance(pattern, str) or not isinstance(baud, int) or not isinstance(timeout, int | float):
            raise GarDomainError("UUU serialVerify設定が不正です")
        self.serial_verifier.wait(
            self.console_port,
            baud=baud,
            pattern=pattern,
            timeout_seconds=float(timeout),
        )
