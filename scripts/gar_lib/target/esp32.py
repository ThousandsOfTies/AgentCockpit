"""ESP32 physical target environment."""

from __future__ import annotations

from pathlib import Path

from scripts.gar_lib.artifacts.manifest import load_deploy_files, resolve_artifact_src
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.target.esp32_firmware import FLASH_LAYOUT
from scripts.gar_lib.target.esptool import run_esp32_flash_command


class Esp32TargetEnvironment:
    def __init__(self, port: str):
        self.port = port

    def prepare(self) -> None:
        raise GarDomainError("ESP32 esptool接続には target prepare は不要です")

    def deploy(self, artifact: Artifact) -> None:
        if artifact.kind is not ArtifactKind.TARGET_APP:
            raise GarDomainError(f"ESP32 targetへ配置できないartifactです: {artifact.kind.value}")
        artifact_dir = self._artifact_dir(artifact)
        returncode = run_esp32_flash_command(
            artifact_dir=str(artifact_dir),
            port=self.port,
        )
        if returncode != 0:
            raise GarDomainError(f"ESP32 targetへの書き込みに失敗しました (exit {returncode})")

    @staticmethod
    def _artifact_dir(artifact: Artifact) -> Path:
        required = {name for _, name in FLASH_LAYOUT}
        if all((artifact.bundle_path / name).is_file() for name in required):
            return artifact.bundle_path

        loaded = load_deploy_files(artifact.bundle_path, "app")
        if loaded is None:
            raise GarDomainError(f"ESP32 artifact manifestを読み込めません: {artifact.bundle_path}")
        bundle_root, files = loaded
        candidates: list[Path] = []
        for entry in files:
            source = resolve_artifact_src(bundle_root, entry["src"])
            if source is None:
                continue
            candidates.append(source if source.is_dir() else source.parent)
        for candidate in candidates:
            if all((candidate / name).is_file() for name in required):
                return candidate
        raise GarDomainError("ESP32 artifactにfirmware一式がありません。")
